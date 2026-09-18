import operator
from typing import Annotated, Sequence, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

class CartItem(TypedDict):
    menu_item_id: str
    name: str
    price: float
    quantity: int
    notes: Optional[str]

class CustomerSupportState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tenant_id: str
    customer_id: Optional[str]
    sender_phone: str
    cart: List[CartItem]
    delivery_address: Optional[str]
    delivery_type: str # delivery or pickup
    order_id: Optional[str]
    escalation_needed: bool
    escalation_reason: Optional[str]
