from datetime import datetime
from typing import List, Literal, Optional
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
    
    
    




class CreateTenantRequest(BaseModel):
    business_name: str = Field(..., description="The name of the business")
    business_phone: Optional[str] = Field(None)
    address: Optional[str] = Field(None)
    country: str = Field(..., description="ISO country code: PK, AE, SA, GB or US. Currency and timezone are derived from it.")
    city: Optional[str] = Field(None)
    order_types: List[Literal["delivery", "takeaway", "dine_in"]] = Field(..., min_length=1)
    whatsapp_business_id: Optional[str] = Field(None)
    phone_number_id: Optional[str] = Field(None)
    whatsapp_access_token: Optional[str] = Field(None)