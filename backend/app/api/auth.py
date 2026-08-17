"""Auth-related routes: verifying a bearer token reaches the backend."""

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(current_user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    """Return the authenticated user, syncing their row into `users` on first sign-in."""
    await current_user.client.table("users").upsert(
        {"id": str(current_user.id), "email": current_user.email}
    ).execute()

    return {"id": str(current_user.id), "email": current_user.email}
