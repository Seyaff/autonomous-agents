from typing import Any

from pydantic import BaseModel, Field


# ---------- Request ----------

class TenantContext(BaseModel):
    tenant_id: str
    user_id: str
    role: str
    
    


class QueryAgent(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    tenant_id: str
    tenant: TenantContext
    customer_phone: str
    user_message: str


# ---------- Response ----------

class AgentResponse(BaseModel):
    success: bool = True
    response: str
    intent: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)