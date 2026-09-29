import logging

from fastapi import APIRouter

from schemas.agent import AgentResponse, QueryAgent
from agents.central_agent import run_master_turn


agent_router = APIRouter(prefix="/agent", tags=["Agent Routes"])


@agent_router.post("/query", response_model=AgentResponse)
async def query(payload: QueryAgent) -> AgentResponse:
   
    result = await run_master_turn(
        tenant=payload.tenant.model_dump(),
        customer_phone=payload.customer_phone,
        user_message=payload.user_message,
    )
    
    print(f"result is : {result}")

    return AgentResponse(
        success=True,
        response=result.get("final_reply", ""),
        intent=None,
        actions=[],
        metadata={
            "tenant_id": payload.tenant_id,
            "next_agents": result.get("next_agents", []),
            "agent_replies": result.get("agent_replies", {}),
        },
    )