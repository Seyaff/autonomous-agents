import uuid
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import String, Boolean, DateTime, func, Text, Numeric, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant = relationship("Tenant", back_populates="categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    # 86'd / Inventory availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    
    # Allergens, dietary badges (e.g. ['vegan', 'gluten-free', 'contains nuts'])
    allergens: Mapped[Optional[Any]] = mapped_column(JSON, default=list)
    
    # Modifiers (e.g. [{'name': 'Extra Cheese', 'price': 1.50}])
    modifiers: Mapped[Optional[Any]] = mapped_column(JSON, default=list)

    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="menu_items")
    category = relationship("MenuCategory", back_populates="items")
    embeddings = relationship("MenuItemEmbedding", back_populates="menu_item", cascade="all, delete-orphan")


from sqlalchemy.types import TypeDecorator, JSON

class SafeVector(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(768))
        return dialect.type_descriptor(JSON())

class MenuItemEmbedding(Base):
    __tablename__ = "menu_item_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 768 dimensions for Gemini Embeddings / dense vectors on Postgres, JSON fallback on SQLite
    embedding = mapped_column(SafeVector, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    menu_item = relationship("MenuItem", back_populates="embeddings")
