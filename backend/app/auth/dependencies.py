"""Supabase JWT verification and the `get_current_user` request dependency."""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AsyncClient, AuthApiError

from app.database import create_user_client

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    email: str
    client: AsyncClient
    """User-scoped Supabase client (RLS applies) for this request."""


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Extract the bearer token from the `Authorization` header, or raise `401`."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    return credentials.credentials


async def get_current_user(access_token: str = Depends(get_access_token)) -> CurrentUser:
    """Verify the bearer token against Supabase Auth. Raises `401` if invalid or expired."""
    client = await create_user_client(access_token)

    try:
        response = await client.auth.get_user(access_token)
    except AuthApiError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    if response is None or response.user.email is None:
        raise _unauthorized("Invalid or expired token")

    return CurrentUser(id=UUID(response.user.id), email=response.user.email, client=client)
