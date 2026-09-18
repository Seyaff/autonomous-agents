import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, DateTime, func, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    whatsapp_phone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    preferences: Mapped[Optional[Any]] = mapped_column(JSON, default=dict)
    
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    last_order_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Feedback & Marketing status
    last_review_prompt_sent: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_opted_out_marketing: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="customers")
    orders = relationship("Order", back_populates="customer")
