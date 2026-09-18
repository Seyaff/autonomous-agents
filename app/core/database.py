import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import text
from app.config import settings

# Setup Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables, extensions, and auto-provision default restaurant if configured."""
    import app.models  # Register all models with Base.metadata
    async with engine.begin() as conn:
        if "postgresql" in settings.DATABASE_URL:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)

    # Auto-seed default restaurant if test phone number ID is present
    await seed_default_restaurant()

async def seed_default_restaurant():
    """Seed the default restaurant from environment variables for instant WhatsApp testing."""
    if not settings.META_PHONE_NUMBER_ID:
        return

    from sqlalchemy import select
    from app.models.tenant import Tenant
    from app.models.menu import MenuCategory, MenuItem

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Tenant).where(Tenant.phone_number_id == settings.META_PHONE_NUMBER_ID))
        tenant = res.scalar_one_or_none()
        if not tenant:
            restaurant_name = settings.DEFAULT_RESTAURANT_ID.replace("-", " ").title()
            tenant = Tenant(
                name=restaurant_name,
                slug=settings.DEFAULT_RESTAURANT_ID,
                waba_id=settings.META_WABA_ID,
                phone_number_id=settings.META_PHONE_NUMBER_ID,
                meta_access_token=settings.META_ACCESS_TOKEN,
                owner_whatsapp_number=settings.OWNER_WHATSAPP_PHONE or "923417268523",
                currency="USD",
                address="Peshawar / Islamabad Highway",
                opening_hours="12:00 PM - 12:00 AM",
                is_active=True
            )
            db.add(tenant)
            await db.flush()

            # Seed authentic menu items
            cat_special = MenuCategory(tenant_id=tenant.id, name="House Specialties")
            cat_bbq = MenuCategory(tenant_id=tenant.id, name="Karahi & BBQ")
            cat_sides = MenuCategory(tenant_id=tenant.id, name="Sides & Beverages")
            db.add_all([cat_special, cat_bbq, cat_sides])
            await db.flush()

            items = [
                MenuItem(
                    tenant_id=tenant.id, category_id=cat_special.id,
                    name="Peshawari Chapli Kabab",
                    description="Traditional spiced minced beef patties fried in tallow with pomegranate seeds",
                    price=12.00, is_available=True
                ),
                MenuItem(
                    tenant_id=tenant.id, category_id=cat_special.id,
                    name="Kabuli Pulao",
                    description="Fragrant sella rice with tender mutton shanks, caramelized carrots & raisins",
                    price=15.00, is_available=True
                ),
                MenuItem(
                    tenant_id=tenant.id, category_id=cat_bbq.id,
                    name="Shinwari Mutton Karahi",
                    description="Fresh young lamb cooked in black pepper, fresh tomatoes, and green chillies",
                    price=24.00, is_available=True
                ),
                MenuItem(
                    tenant_id=tenant.id, category_id=cat_sides.id,
                    name="Roghani Naan",
                    description="Fluffy tandoori bread brushed with butter and sesame seeds",
                    price=2.50, is_available=True
                ),
                MenuItem(
                    tenant_id=tenant.id, category_id=cat_sides.id,
                    name="Peshawari Kahwa Green Tea",
                    description="Traditional green tea infused with cardamom and saffron",
                    price=3.00, is_available=True
                )
            ]
            db.add_all(items)
            await db.commit()

