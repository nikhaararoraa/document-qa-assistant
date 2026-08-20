"""Chat thread and message persistence.

`list_threads`, `create_thread`, and `list_messages` take a user-scoped Supabase
client so Postgres RLS enforces ownership. `get_thread` and `insert_message` /
`touch_thread` take the service-role client: `get_thread` is used to check
ownership *before* RLS would apply (to tell "not found" apart from "not yours"),
and the write helpers are backend-owned persistence tied to an already-verified
thread/user.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import AsyncClient

_THREADS_TABLE = "chat_threads"
_MESSAGES_TABLE = "chat_messages"


async def list_threads(client: AsyncClient, user_id: UUID) -> list[dict[str, Any]]:
    response = (
        await client.table(_THREADS_TABLE)
        .select("*")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data


async def create_thread(client: AsyncClient, user_id: UUID, title: str | None) -> dict[str, Any]:
    response = (
        await client.table(_THREADS_TABLE).insert({"user_id": str(user_id), "title": title}).execute()
    )
    return response.data[0]


async def get_thread(client: AsyncClient, thread_id: UUID) -> dict[str, Any] | None:
    response = await client.table(_THREADS_TABLE).select("*").eq("id", str(thread_id)).execute()
    return response.data[0] if response.data else None


async def touch_thread(client: AsyncClient, thread_id: UUID) -> None:
    await (
        client.table(_THREADS_TABLE)
        .update({"updated_at": datetime.now(UTC).isoformat()})
        .eq("id", str(thread_id))
        .execute()
    )


async def list_messages(client: AsyncClient, thread_id: UUID) -> list[dict[str, Any]]:
    response = (
        await client.table(_MESSAGES_TABLE)
        .select("*")
        .eq("thread_id", str(thread_id))
        .order("created_at")
        .execute()
    )
    return response.data


async def insert_message(
    client: AsyncClient,
    *,
    thread_id: UUID,
    role: str,
    content: str,
    message_json: dict[str, Any],
) -> dict[str, Any]:
    response = (
        await client.table(_MESSAGES_TABLE)
        .insert(
            {
                "thread_id": str(thread_id),
                "role": role,
                "content": content,
                "message_json": message_json,
            }
        )
        .execute()
    )
    return response.data[0]
