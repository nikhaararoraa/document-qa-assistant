"""Supabase client construction for server-side database and auth access."""

from supabase import AsyncClient, acreate_client
from supabase.lib.client_options import AsyncClientOptions

from app.config import settings

_service_role_client: AsyncClient | None = None


def _server_client_options(*, access_token: str | None = None) -> AsyncClientOptions:
    """Options for server-side clients: no browser session to persist or auto-refresh."""
    headers: dict[str, str] = {}
    if access_token is not None:
        bearer = access_token if access_token.startswith("Bearer ") else f"Bearer {access_token}"
        headers["Authorization"] = bearer

    return AsyncClientOptions(
        headers=headers,
        auto_refresh_token=False,
        persist_session=False,
    )


async def get_service_role_client() -> AsyncClient:
    """Privileged client for backend-only writes that must bypass RLS.

    Cached as a singleton. Never expose the service-role key to the browser.
    """
    global _service_role_client
    if _service_role_client is None:
        _service_role_client = await acreate_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=_server_client_options(),
        )
    return _service_role_client


async def create_user_client(access_token: str) -> AsyncClient:
    """Fresh per-request client using the user's JWT so Postgres RLS policies apply.

    Accepts either a raw token or an already-prefixed `Bearer <token>` value.
    """
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=_server_client_options(access_token=access_token),
    )
