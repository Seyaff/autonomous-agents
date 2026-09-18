import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    # Meta WhatsApp credentials & IDs
    waba_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    phone_number_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    display_phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    meta_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Operational numbers
    owner_whatsapp_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    kitchen_whatsapp_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Business settings
    currency: Mapped[str] = mapped_column(String(10), default="PKR")
    cuisine: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    opening_hours: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_step: Mapped[str] = mapped_column(String(50), default="DRAFT")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    categories = relationship("MenuCategory", back_populates="tenant", cascade="all, delete-orphan")
    menu_items = relationship("MenuItem", back_populates="tenant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
