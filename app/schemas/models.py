from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class CreateUser(BaseModel):
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="The full name of the user to create",
    )
    email: EmailStr = Field(..., description="The unique email address of the user")
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=128,
        description="User account password (None for OAuth users)",
    )
    google_id: Optional[str] = Field(
        None, description="The Google ID of the user being logged in"
    )
    profile_picture: Optional[str] = None
    role: str = "OWNER"
    active_tenant_id: Optional[str] = None
    tenants: List[str] = []
    is_onboarded: bool = False
    
    
    




class OperatingHours(BaseModel):
    day: str = Field(..., description="e.g. Monday, Tuesday")
    open_time: str = Field(default="09:00", description="24hr format HH:MM")
    close_time: str = Field(default="22:00", description="24hr format HH:MM")
    is_closed: bool = Field(default=False)


class DeliverySettings(BaseModel):
    supports_delivery: bool = Field(default=True)
    supports_takeaway: bool = Field(default=True)
    supports_reservations: bool = Field(default=True)
    flat_delivery_fee: float = Field(default=0.0)
    avg_prep_time_minutes: int = Field(default=30)


class CreateTenantRequest(BaseModel):
    business_name: str = Field(..., description="The name of the business")
    business_phone: Optional[str] = Field(None)
    address: Optional[str] = Field(None)
    currency: str = Field(default="USD")
    timezone: str = Field(default="UTC")
    whatsapp_business_id: Optional[str] = Field(None)
    phone_number_id: Optional[str] = Field(None)
    whatsapp_access_token: Optional[str] = Field(None)
    operating_hours: List[OperatingHours] = Field(default_factory=list)