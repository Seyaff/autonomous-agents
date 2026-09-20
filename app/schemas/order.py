from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone

class OrderItem(BaseModel):
    name: str = Field(description="Name of the item or dish")
    quantity: int = Field(default=1, ge=1, description="Quantity ordered")
    price: float = Field(ge=0.0, description="Price per unit")
    notes: Optional[str] = Field(default=None, description="Special instructions for this specific item")

class OrderCreate(BaseModel):
    tenant_id: str
    customer_phone: str
    delivery_address: str
    items: List[OrderItem]
    total_amount: float
    payment_method: str = "cod"
    customer_notes: Optional[str] = None