import logging

from fastapi import APIRouter, Depends

from schemas.agent import AgentResponse, QueryAgent
from agents.central_agent import run_master_turn
from middlewares.auth_middleware import require_owner

logger = logging.getLogger(__name__)

agent_router = APIRouter(prefix="/agent", tags=["Agent Routes"])


@agent_router.post("/query", response_model=AgentResponse)
async def query(
    payload: QueryAgent, current_user: dict = Depends(require_owner)
) -> AgentResponse:
    """Dev/testing endpoint: runs a turn through the support graph directly,
    without needing a real WhatsApp round-trip."""
    result = await run_master_turn(
        tenant=payload.tenant.model_dump(),
        customer_phone=payload.customer_phone,
        user_message=payload.user_message,
    )

    return AgentResponse(
        success=True,
        response=result.get("final_reply", ""),
        intent=None,
        actions=[],
        metadata={"next_agents": result.get("next_agents", [])},
    )
