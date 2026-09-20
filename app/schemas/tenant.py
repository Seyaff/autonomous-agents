from pydantic import BaseModel , ConfigDict, Field


class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, example="Flavor Fusion Cafe")
    slug: str = Field(..., example="flavor-fusion-cafe")
    waba_id: Optional[str] = Field(None, example="100293847562810")
    phone_number_id: Optional[str] = Field(None, example="109823746501928")
    display_phone_number: Optional[str] = Field(None, example="+923001234567")
    meta_access_token: Optional[str] = Field(None, example="EAAX...token_value...")
    owner_whatsapp_number: str = Field(..., example="+923001234567")
    kitchen_whatsapp_number: Optional[str] = Field(None, example="+923017654321")
    currency: str = Field(default="PKR", example="PKR")
    city: Optional[str] = Field(None, example="Lahore")
    address: Optional[str] = Field(None, example="123 Main Boulevard, Gulberg III")
    opening_hours: Optional[str] = Field(None, example="09:00 AM - 11:00 PM")
    
    
class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    meta_access_token: Optional[str] = None
    owner_whatsapp_number: Optional[str] = None
    kitchen_whatsapp_number: Optional[str] = None
    currency: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    opening_hours: Optional[str] = None
    
    
class TenantResponse(TenantBase):
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )