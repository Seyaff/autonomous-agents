"""
Single place that decides which LLM powers the agents.

Every agent should get its chat model from `get_chat_model()` instead of
constructing `ChatGroq`/`ChatOpenAI` directly. Switching the whole platform
from dev (Groq) to prod (OpenAI) is then a single env var
(`LLM_PROVIDER=groq|openai`), not a hunt through every agent file.
"""

import logging
from typing import Optional

from core.settings import settings

logger = logging.getLogger(__name__)


def get_chat_model(
    purpose: str = "agent",
    temperature: float = 0.1,
    model: Optional[str] = None,
    provider: Optional[str] = None,
):
    """
    Returns a LangChain chat model chosen by `settings.LLM_PROVIDER`.

    Args:
        purpose: short label for logging only (e.g. "customer_support",
            "router", "lead_research") — does not change behavior today,
            but keeps call sites self-documenting if per-purpose model
            overrides are added later.
        temperature: sampling temperature.
        model: explicit model name override; defaults to the provider's
            configured model in settings.
        provider: "groq" or "openai". Defaults to settings.LLM_PROVIDER.
    """
    provider = (provider or settings.LLM_PROVIDER or "groq").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model_name = model or settings.OPENAI_MODEL
        logger.debug(f"[llm:{purpose}] provider=openai model={model_name}")
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        model_name = model or settings.GROQ_MODEL
        logger.debug(f"[llm:{purpose}] provider=groq model={model_name}")
        return ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=settings.GROQ_API_KEY,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}' (purpose={purpose}). "
        "Expected 'groq' or 'openai'."
    )
