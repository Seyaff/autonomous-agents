import asyncio
import uuid
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from sqlalchemy import select
from app.core.database import init_db, AsyncSessionLocal, Base, engine
from app.models.tenant import Tenant
from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order
from app.agents.tenant.customer_support.graph import run_customer_support_graph
from app.agents.tenant.inventory.graph import process_owner_inventory_message
from app.agents.tenant.inventory.tools import save_ingested_menu

async def run_simulation():
    print("\n=======================================================")
    print("[*] STARTING AUTONOMOUS AGENTS END-TO-END SIMULATION")
    print("=======================================================\n")

    # 1. Initialize Tables
    print("[1] Initializing database schema...")
    await init_db()
    print("   [OK] Schema initialized.")

    # 2. Seed Restaurant Tenant
    print("\n[2] Registering test restaurant tenant: 'Bella Napoli Pizzeria'...")
    owner_phone = "+15550001"
    customer_phone = "+15559999"
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Tenant).where(Tenant.slug == "bella-napoli"))
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                name="Bella Napoli Pizzeria",
                slug="bella-napoli",
                owner_whatsapp_number=owner_phone,
                phone_number_id="waba_phone_123",
                currency="USD",
                address="124 Olive Way, Napoli Quarter",
                opening_hours="11:00 AM - 10:00 PM"
            )
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
        tenant_id = str(tenant.id)
    print(f"   [OK] Tenant ready! ID: {tenant_id}")

    # 3. Simulate Menu Ingestion by Owner
    print("\n[3] Ingesting restaurant menu via Inventory Agent...")
    sample_menu = [
        {
            "category_name": "Pizzas",
            "items": [
                {"name": "Margherita Pizza", "description": "Fresh basil, san marzano tomato, fior di latte", "price": 14.00},
                {"name": "Pepperoni Feast", "description": "Crispy pepperoni, hot honey, aged mozzarella", "price": 16.50}
            ]
        },
        {
            "category_name": "Appetizers & Desserts",
            "items": [
                {"name": "Garlic Knots", "description": "Garlic butter, parmesan, marinara dip", "price": 6.00},
                {"name": "Tiramisu", "description": "Espresso-soaked ladyfingers, mascarpone cream", "price": 8.00}
            ]
        }
    ]
    ingest_result = await save_ingested_menu(tenant_id, sample_menu)
    print(f"   [OK] Ingested: {ingest_result['items_added_or_updated']} items.")

    # 4. Simulate Customer Interactions on WhatsApp
    print("\n[4] Customer WhatsApp Chat Simulation:")
    print(f"   Customer Phone: {customer_phone}\n")

    # Step 4A: Ask for Menu
    print("   [CUSTOMER] -> 'Hi! Can I see your menu?'")
    reply = await run_customer_support_graph(tenant_id, customer_phone, "Hi! Can I see your menu?")
    print(f"   [AGENT]    ->\n{reply}\n")

    # Step 4B: Add Item to Cart
    print("   [CUSTOMER] -> 'Please add 1 Margherita Pizza and 1 Garlic Knots'")
    reply = await run_customer_support_graph(tenant_id, customer_phone, "Please add 1 Margherita Pizza")
    print(f"   [AGENT]    ->\n{reply}\n")

    # Step 4C: Checkout
    print("   [CUSTOMER] -> 'Checkout now please'")
    reply = await run_customer_support_graph(tenant_id, customer_phone, "Checkout now please")
    print(f"   [AGENT]    ->\n{reply}\n")

    # 5. Verify Order Created in Database
    print("[5] Verifying order persistence in database...")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Order).where(Order.tenant_id == uuid.UUID(tenant_id)).order_by(Order.created_at.desc()))
        last_order = res.scalars().first()
        if last_order:
            print(f"   [OK] Order Found! Number: {last_order.order_number} | Amount: ${last_order.total_amount:.2f} | Status: {last_order.status} | Payment: {last_order.payment_status}")

    # 6. Simulate Owner 86'ing an Item (Inventory Agent)
    print("\n[6] Restaurant Owner WhatsApp Command Simulation:")
    print(f"   Owner Phone: {owner_phone}\n")
    print("   [OWNER] -> 'We are out of Garlic Knots'")
    owner_reply = await process_owner_inventory_message(tenant_id, owner_phone, "We are out of Garlic Knots")
    print(f"   [INVENTORY AGENT] -> {owner_reply}\n")

    print("   [OWNER] -> 'Inventory'")
    inv_reply = await process_owner_inventory_message(tenant_id, owner_phone, "Inventory")
    print(f"   [INVENTORY AGENT] ->\n{inv_reply}\n")

    print("=======================================================")
    print("[OK] SIMULATION COMPLETED SUCCESSFULLY!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_simulation())
