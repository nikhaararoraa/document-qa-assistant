"""Chat thread CRUD and the stubbed AI-SDK streaming endpoint."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.streaming import build_on_complete, stub_agent
from app.database import chats
from app.database.supabase import get_service_role_client

router = APIRouter(prefix="/chat", tags=["chat"])


class ThreadCreate(BaseModel):
    title: str | None = None


class ThreadOut(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


async def require_thread_owner(
    thread_id: UUID, current_user: CurrentUser = Depends(get_current_user)
) -> UUID:
    """Verify `thread_id` belongs to `current_user`.

    `404` if the thread doesn't exist at all, `403` if it belongs to someone else.
    Uses the service-role client so this check happens before RLS would silently
    filter out another user's row, which would otherwise be indistinguishable
    from "not found".
    """
    service_client = await get_service_role_client()
    thread = await chats.get_thread(service_client, thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thread not found")
    if UUID(thread["user_id"]) != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your thread")
    return thread_id


@router.get("/threads")
async def list_threads(current_user: CurrentUser = Depends(get_current_user)) -> list[ThreadOut]:
    rows = await chats.list_threads(current_user.client, current_user.id)
    return [ThreadOut(**row) for row in rows]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    body: ThreadCreate, current_user: CurrentUser = Depends(get_current_user)
) -> ThreadOut:
    row = await chats.create_thread(current_user.client, current_user.id, body.title)
    return ThreadOut(**row)


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: UUID = Depends(require_thread_owner),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    rows = await chats.list_messages(current_user.client, thread_id)
    return [row["message_json"] for row in rows]


@router.post("/threads/{thread_id}/stream")
async def stream_reply(
    request: Request,
    thread_id: UUID = Depends(require_thread_owner),
) -> Response:
    """Accept an AI-SDK request body and stream a stubbed assistant reply.

    Persistence of the user + assistant messages happens in the `on_complete`
    callback once the stream finishes successfully (see `app/chat/streaming.py`).
    """
    adapter = await VercelAIAdapter.from_request(request, agent=stub_agent)
    on_complete = build_on_complete(thread_id=thread_id, incoming_messages=adapter.run_input.messages)
    return adapter.streaming_response(adapter.run_stream(on_complete=on_complete))
