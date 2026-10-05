"""The owner's chat streams its reply, shows tool steps, and saves the conversation.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
from types import SimpleNamespace

from services import owner_assistant
from tests.test_owner_assistant import FakeCollection, FakeDB, TENANT_ID


class Chunk:
    def __init__(self, content):
        self.content = content


class ScriptedAgent:
    def __init__(self, events):
        self.events = events

    async def astream_events(self, state, version):
        for event in self.events:
            yield event


class Transcript(FakeCollection):
    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    def find(self, query, projection=None):
        rows = [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        return SimpleNamespace(sort=lambda *_: SimpleNamespace(to_list=_async_list(rows)))


def _async_list(rows):
    async def to_list(length=None):
        return list(rows)[-(length or len(rows)):]
    return to_list


def make_db():
    tenant = {"tenant_id": TENANT_ID, "business_name": "Test Kitchen", "agent_enabled": True}
    return FakeDB(tenants=FakeCollection([tenant]), assistant_messages=Transcript([]),
                  settings_changes=FakeCollection([]), menu_items=FakeCollection([]))


def collect(db, message="hello"):
    async def run():
        return [event async for event in owner_assistant.stream_owner_turn(db, TENANT_ID, "u1", message)]
    return asyncio.run(run())


def test_reply_streams_in_pieces_with_tool_steps_and_is_saved(monkeypatch):
    events = [
        {"event": "on_tool_start", "name": "list_menu", "data": {}},
        {"event": "on_chat_model_stream", "data": {"chunk": Chunk("Here ")}},
        {"event": "on_chat_model_stream", "data": {"chunk": Chunk("is the menu.")}},
    ]
    monkeypatch.setattr(owner_assistant, "_agent", lambda provider, tools: ScriptedAgent(events))
    db = make_db()

    emitted = collect(db)

    assert [e["type"] for e in emitted] == ["tool", "token", "token", "done"]
    assert emitted[-1]["reply"] == "Here is the menu."
    saved = db.assistant_messages.docs
    assert [m["role"] for m in saved] == ["owner", "assistant"]
    assert saved[0]["content"] == "hello" and saved[1]["content"] == "Here is the menu."


def test_a_failed_turn_says_so_and_is_still_saved(monkeypatch):
    class Broken:
        async def astream_events(self, state, version):
            raise ValueError("boom")
            yield  # pragma: no cover

    monkeypatch.setattr(owner_assistant, "_agent", lambda provider, tools: Broken())
    monkeypatch.setattr(owner_assistant.settings, "LLM_FALLBACK_PROVIDER", "")
    db = make_db()

    emitted = collect(db)

    assert emitted[0]["type"] == "error"
    assert emitted[-1]["type"] == "done"
    assert db.assistant_messages.docs[-1]["content"] == owner_assistant.APOLOGY


def test_rate_limit_before_any_output_moves_to_the_fallback(monkeypatch):
    class RateLimited:
        async def astream_events(self, state, version):
            raise RuntimeError("Rate limit reached for tokens per day")
            yield  # pragma: no cover

    fallback_events = [{"event": "on_chat_model_stream", "data": {"chunk": Chunk("On the backup model.")}}]

    def pick(provider, tools):
        return RateLimited() if provider == "groq" else ScriptedAgent(fallback_events)

    monkeypatch.setattr(owner_assistant, "_agent", pick)
    monkeypatch.setattr(owner_assistant.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(owner_assistant.settings, "LLM_FALLBACK_PROVIDER", "openai")
    db = make_db()

    emitted = collect(db)

    assert emitted[-1]["reply"] == "On the backup model."
    assert not any(e["type"] == "error" for e in emitted)
