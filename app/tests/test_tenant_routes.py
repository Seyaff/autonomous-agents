"""The tenant endpoints load, and their routes are where the frontend expects them.
A broken endpoints file would otherwise pass every other test.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""


def test_tenant_routes_load_and_include_the_assistant_and_agent_toggle():
    from api.v1.endpoints import tenant

    paths = {r.path for r in tenant.tenant_routes.routes}
    assert "/tenant/current/assistant/stream" in paths
    assert "/tenant/current/assistant/history" in paths
    assert "/tenant/current/agent" in paths
    assert "/tenant/current/agent-settings" in paths
