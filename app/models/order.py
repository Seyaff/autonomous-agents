import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, DateTime, func, Text, Numeric, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True) # pending, confirmed, preparing, out_for_delivery, delivered, cancelled
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Payment details
    payment_status: Mapped[str] = mapped_column(String(50), default="pending") # pending, dummy_paid, cod, completed
    payment_method: Mapped[str] = mapped_column(String(50), default="dummy_payment")
    
    # Delivery info
    delivery_type: Mapped[str] = mapped_column(String(50), default="delivery") # delivery, pickup
    delivery_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    customer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    menu_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    modifiers: Mapped[Optional[Any]] = mapped_column(JSON, default=list)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="items")
