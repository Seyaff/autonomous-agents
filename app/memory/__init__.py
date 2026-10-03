"""Customer memory: derived order stats, durable facts, and the per-turn context window."""

from .customer_card import build_customer_card, render_card
from .facts import FactChange, apply_fact_changes, ensure_fact_indexes, list_active_facts
from .context_builder import build_agent_context, remember_exchange

__all__ = [
    "build_customer_card",
    "render_card",
    "FactChange",
    "apply_fact_changes",
    "ensure_fact_indexes",
    "list_active_facts",
    "build_agent_context",
    "remember_exchange",
]
