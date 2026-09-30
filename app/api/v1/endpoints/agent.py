import logging

from fastapi import APIRouter

from schemas.agent import AgentResponse, QueryAgent
from agents.central_agent import run_master_turn
from agents.leads.agent import agent
from agents.leads.tools import scrape_leads


agent_router = APIRouter(prefix="/agent", tags=["Agent Routes"])



@agent_router.post("/query", response_model=AgentResponse)
async def query(payload: QueryAgent) -> AgentResponse:
   
    # result = await run_master_turn(
    #     tenant=payload.tenant.model_dump(),
    #     customer_phone=payload.customer_phone,
    #     user_message=payload.user_message,
    # )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": payload.user_message}]}
    )
    
    bro = await scrape_leads.ainvoke({"query": "real estate agencies in australia"})
    print(f"bro is bro: { bro}")
    
    print(f"result is : {result}")

    return AgentResponse(
        success=True,
        response="bro",
        intent=None,
        actions=[],
        metadata={
            
        },
    )