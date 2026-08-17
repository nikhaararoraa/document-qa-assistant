"""Chat thread CRUD, ownership enforcement, and the stubbed stream endpoint.

No network / no DB: `app.database.chats` functions and the service-role client
constructor are monkeypatched, and auth is bypassed via a FastAPI dependency
override, per backend/CLAUDE.md's fast-suite requirements.
"""

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.chat import require_thread_owner
from app.auth.dependencies import CurrentUser, get_current_user
from app.chat import streaming as streaming_module
from app.chat.streaming import STUB_REPLY
from app.database import chats
from app.main import app

USER_ID = uuid4()
OTHER_USER_ID = uuid4()
THREAD_ID = uuid4()


def _current_user() -> CurrentUser:
    return CurrentUser(id=USER_ID, email="analyst@example.com", client=object())


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = _current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _no_service_role_client(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_service_role_client() -> object:
        return object()

    monkeypatch.setattr(chat_api, "get_service_role_client", fake_get_service_role_client)
    monkeypatch.setattr(streaming_module, "get_service_role_client", fake_get_service_role_client)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestRequireThreadOwner:
    """No async test plugin (pytest-asyncio/anyio) is installed, so coroutines are
    driven with `asyncio.run` from plain sync test functions."""

    def test_404_when_thread_missing(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_get_thread(_client: object, _thread_id: UUID) -> None:
            return None

        monkeypatch.setattr(chats, "get_thread", fake_get_thread)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_thread_owner(THREAD_ID, current_user=_current_user()))
        assert exc_info.value.status_code == 404

    def test_403_when_owned_by_someone_else(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_get_thread(_client: object, _thread_id: UUID) -> dict:
            return {"id": str(THREAD_ID), "user_id": str(OTHER_USER_ID)}

        monkeypatch.setattr(chats, "get_thread", fake_get_thread)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_thread_owner(THREAD_ID, current_user=_current_user()))
        assert exc_info.value.status_code == 403

    def test_passes_through_for_owner(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_get_thread(_client: object, _thread_id: UUID) -> dict:
            return {"id": str(THREAD_ID), "user_id": str(USER_ID)}

        monkeypatch.setattr(chats, "get_thread", fake_get_thread)

        result = asyncio.run(require_thread_owner(THREAD_ID, current_user=_current_user()))
        assert result == THREAD_ID


def test_list_threads(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(UTC).isoformat()

    async def fake_list_threads(_client: object, user_id: UUID) -> list[dict]:
        assert user_id == USER_ID
        return [{"id": str(THREAD_ID), "title": "Apple 10-K", "created_at": now, "updated_at": now}]

    monkeypatch.setattr(chats, "list_threads", fake_list_threads)

    response = client.get("/chat/threads")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Apple 10-K"


def test_create_thread(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(UTC).isoformat()

    async def fake_create_thread(_client: object, user_id: UUID, title: str | None) -> dict:
        assert user_id == USER_ID
        return {"id": str(THREAD_ID), "title": title, "created_at": now, "updated_at": now}

    monkeypatch.setattr(chats, "create_thread", fake_create_thread)

    response = client.post("/chat/threads", json={"title": "New thread"})
    assert response.status_code == 201
    assert response.json()["title"] == "New thread"


def test_list_messages_forbidden_for_other_users_thread(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_get_thread(_client: object, _thread_id: UUID) -> dict:
        return {"id": str(THREAD_ID), "user_id": str(OTHER_USER_ID)}

    monkeypatch.setattr(chats, "get_thread", fake_get_thread)

    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.status_code == 403


def test_list_messages_returns_stored_ui_messages(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_get_thread(_client: object, _thread_id: UUID) -> dict:
        return {"id": str(THREAD_ID), "user_id": str(USER_ID)}

    stored_message = {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "Hello"}]}

    async def fake_list_messages(_client: object, _thread_id: UUID) -> list[dict]:
        return [{"message_json": stored_message}]

    monkeypatch.setattr(chats, "get_thread", fake_get_thread)
    monkeypatch.setattr(chats, "list_messages", fake_list_messages)

    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.status_code == 200
    assert response.json() == [stored_message]


def test_stream_reply_streams_stub_and_persists_both_messages(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_get_thread(_client: object, _thread_id: UUID) -> dict:
        return {"id": str(THREAD_ID), "user_id": str(USER_ID)}

    inserted: list[dict] = []
    touched: list[UUID] = []

    async def fake_insert_message(_client: object, *, thread_id: UUID, role: str, content: str, message_json: dict):
        inserted.append({"thread_id": thread_id, "role": role, "content": content})
        return {}

    async def fake_touch_thread(_client: object, thread_id: UUID) -> None:
        touched.append(thread_id)

    monkeypatch.setattr(chats, "get_thread", fake_get_thread)
    monkeypatch.setattr(chats, "insert_message", fake_insert_message)
    monkeypatch.setattr(chats, "touch_thread", fake_touch_thread)

    body = {
        "id": str(THREAD_ID),
        "trigger": "submit-message",
        "messages": [
            {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "What was Apple's 2023 revenue?"}]}
        ],
    }

    with client.stream("POST", f"/chat/threads/{THREAD_ID}/stream", json=body) as response:
        assert response.status_code == 200
        response.read()
        body_text = response.text

    # SSE data-stream protocol: reassemble the streamed text from its `text-delta` chunks.
    streamed_text = "".join(
        json.loads(line.removeprefix("data: "))["delta"]
        for line in body_text.splitlines()
        if line.startswith("data: ") and '"type":"text-delta"' in line
    )
    assert streamed_text == STUB_REPLY

    assert touched == [THREAD_ID]
    assert len(inserted) == 2
    assert inserted[0]["role"] == "user"
    assert inserted[0]["content"] == "What was Apple's 2023 revenue?"
    assert inserted[1]["role"] == "assistant"
    assert inserted[1]["content"] == STUB_REPLY
