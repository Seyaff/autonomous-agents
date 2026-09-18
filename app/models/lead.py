import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, DateTime, func, Text, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    restaurant_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    cuisine_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Audit & Gap Analysis
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    has_online_ordering: Mapped[bool] = mapped_column(default=False)
    has_whatsapp_ordering: Mapped[bool] = mapped_column(default=False)
    google_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    google_reviews_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audit_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pipeline status
    status: Mapped[str] = mapped_column(String(50), default="new", index=True) # new, pitched, engaged, qualified, closed_won, closed_lost
    outreach_channel: Mapped[Optional[str]] = mapped_column(String(50), default="whatsapp") # whatsapp, email, phone
    outreach_count: Mapped[int] = mapped_column(Integer, default=0)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
