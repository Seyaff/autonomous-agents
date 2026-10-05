"""A rate-limited turn moves to the fallback provider. Other errors don't.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio

from agents.customer_support import agent as support


class RateLimitError(Exception):
    pass


class FakeAgent:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    async def ainvoke(self, state, config=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def _use(monkeypatch, agents, primary="groq", fallback="openai"):
    monkeypatch.setattr(support.settings, "LLM_PROVIDER", primary)
    monkeypatch.setattr(support.settings, "LLM_FALLBACK_PROVIDER", fallback)
    monkeypatch.setattr(support, "get_customer_support_agent", lambda provider=None: agents[provider])


def test_rate_limits_are_recognised():
    assert support._is_rate_limit(RateLimitError("Rate limit reached"))
    assert support._is_rate_limit(Exception("Error code: 429 - too many requests"))
    assert not support._is_rate_limit(ValueError("bad input"))


def test_rate_limited_turn_is_retried_on_the_fallback(monkeypatch):
    agents = {"groq": FakeAgent(error=RateLimitError("rate limit")), "openai": FakeAgent(result={"messages": ["ok"]})}
    _use(monkeypatch, agents)
    result = asyncio.run(support._invoke_with_fallback({"messages": []}, {}))
    assert result == {"messages": ["ok"]}
    assert agents["groq"].calls == 1 and agents["openai"].calls == 1


def test_other_errors_are_not_retried(monkeypatch):
    agents = {"groq": FakeAgent(error=ValueError("boom")), "openai": FakeAgent(result={})}
    _use(monkeypatch, agents)
    try:
        asyncio.run(support._invoke_with_fallback({"messages": []}, {}))
        raised = None
    except ValueError as e:
        raised = e
    assert raised is not None
    assert agents["openai"].calls == 0


def test_no_fallback_means_the_error_is_raised(monkeypatch):
    agents = {"groq": FakeAgent(error=RateLimitError("rate limit")), "openai": FakeAgent(result={})}
    _use(monkeypatch, agents, fallback="")
    try:
        asyncio.run(support._invoke_with_fallback({"messages": []}, {}))
        raised = None
    except RateLimitError as e:
        raised = e
    assert raised is not None
    assert agents["openai"].calls == 0
