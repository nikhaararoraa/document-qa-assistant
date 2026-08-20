"""Stubbed chat turn: a canned reply streamed through the real AI-SDK wire format.

Uses `FunctionModel` (a plain Python function standing in for a model) so this
requires no OpenAI credentials. Phase 6 replaces `stub_agent` with the real
grounded PydanticAI agent; the streaming/persistence plumbing here stays the same.
"""

from collections.abc import AsyncIterator, Sequence
from uuid import UUID

from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart, UIMessage

from app.database import chats
from app.database.supabase import get_service_role_client

STUB_REPLY = (
    "This is a stubbed response — retrieval and grounding aren't wired up yet. "
    "Once ingestion and the document agent are in place, this will be a cited answer "
    "from the SEC filing corpus."
)


async def _stub_stream(messages: list[ModelMessage], agent_info: AgentInfo) -> AsyncIterator[str]:
    # The AI-SDK adapter always drives the agent through its streaming path, so the
    # stub needs a `stream_function`, not just `function` (non-streamed requests only).
    words = STUB_REPLY.split(" ")
    for index, word in enumerate(words):
        yield word if index == 0 else f" {word}"


stub_agent: Agent[None, str] = Agent(FunctionModel(stream_function=_stub_stream))


def _message_text(message: UIMessage) -> str:
    return "".join(part.text for part in message.parts if isinstance(part, TextUIPart))


def _latest_user_message(messages: Sequence[UIMessage]) -> UIMessage | None:
    for message in reversed(messages):
        if message.role == "user":
            return message
    return None


def build_on_complete(*, thread_id: UUID, incoming_messages: Sequence[UIMessage]):
    """Build the `on_complete` callback for `adapter.run_stream(...)`.

    Persists the user's new message and the assistant's reply to `chat_messages`
    once the run finishes successfully, then bumps the thread's `updated_at`.
    """

    async def on_complete(result: AgentRunResult[str]) -> None:
        client = await get_service_role_client()

        user_message = _latest_user_message(incoming_messages)
        if user_message is not None:
            await chats.insert_message(
                client,
                thread_id=thread_id,
                role="user",
                content=_message_text(user_message),
                message_json=user_message.model_dump(by_alias=True),
            )

        for assistant_message in VercelAIAdapter.dump_messages(result.new_messages()):
            await chats.insert_message(
                client,
                thread_id=thread_id,
                role=assistant_message.role,
                content=_message_text(assistant_message),
                message_json=assistant_message.model_dump(by_alias=True),
            )

        await chats.touch_thread(client, thread_id)

    return on_complete
