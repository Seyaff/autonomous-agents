from core.setup_state import setup_of


def setup_is_complete(tenant: dict) -> bool:
    """True once the owner has finished setup (the same rule the auth gate uses)."""
    return setup_of(tenant).completed_at is not None
