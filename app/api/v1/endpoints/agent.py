import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from core.database import get_database
from schemas.agent import AgentResponse, QueryAgent
from agents.central_agent import run_master_turn
from agents.customer_support.agent import run_agent_turn
from middlewares.auth_middleware import require_owner

logger = logging.getLogger(__name__)

agent_router = APIRouter(prefix="/agent", tags=["Agent Routes"])

TEST_CHATS = "test_chats"
TEST_WINDOW = 12          # messages the agent sees from the test chat
TEST_KEEP = 40            # messages kept in the stored transcript


class TestMessagePayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


def _to_message(entry: Dict[str, Any]) -> BaseMessage:
    if entry.get("role") == "customer":
        return HumanMessage(content=entry["content"])
    return AIMessage(content=entry["content"])


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


@agent_router.get("/test")
async def get_test_chat(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """The owner's test transcript, so the chat survives a page reload."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    doc = await db[TEST_CHATS].find_one(
        {"tenant_id": tenant_id, "owner_id": current_user["user_id"]}, {"_id": 0, "messages": 1}
    )
    return {"messages": (doc or {}).get("messages", [])}


@agent_router.post("/test")
async def send_test_message(
    payload: TestMessagePayload,
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Runs the real customer support agent in test mode for the owner.

    Nothing is saved to the inbox, sent on WhatsApp, or written to customer
    memory. Orders come back with a TEST reference and aren't stored. The
    chat is kept only in test_chats and isn't counted toward usage."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant record not found.")

    owner_id = current_user["user_id"]
    doc = await db[TEST_CHATS].find_one({"tenant_id": tenant_id, "owner_id": owner_id}) or {}
    history = [_to_message(m) for m in (doc.get("messages") or [])[-TEST_WINDOW:]]

    turn = await run_agent_turn(
        db,
        tenant,
        customer_phone=f"test:{owner_id}",
        user_message=payload.message,
        test_mode=True,
        test_history=history,
    )

    now = datetime.now(timezone.utc)
    entries: List[Dict[str, Any]] = [
        {"role": "customer", "content": payload.message, "at": now},
        {
            "role": "agent",
            "content": turn["reply"],
            "trace": turn["trace"],
            "escalated": turn["escalated"],
            "at": now,
        },
    ]
    await db[TEST_CHATS].update_one(
        {"tenant_id": tenant_id, "owner_id": owner_id},
        {
            "$push": {"messages": {"$each": entries, "$slice": -TEST_KEEP}},
            "$set": {"updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    return {"reply": turn["reply"], "trace": turn["trace"], "escalated": turn["escalated"]}


@agent_router.delete("/test")
async def reset_test_chat(
    current_user: dict = Depends(require_owner),
    db=Depends(get_database),
):
    """Clears the owner's test conversation."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant found.")
    await db[TEST_CHATS].delete_one(
        {"tenant_id": tenant_id, "owner_id": current_user["user_id"]}
    )
    return {"status": "success"}
