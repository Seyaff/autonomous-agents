import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from langchain_core.tools import tool
from app.core.database import AsyncSessionLocal
from app.models.menu import MenuItem, MenuCategory
from app.models.order import Order, OrderItem
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.services.dummy_payment import dummy_payment_service
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

async def search_menu_items(tenant_id: str, query: str = "") -> List[Dict[str, Any]]:
    """Query available menu items for a tenant."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(MenuItem)
            .where(MenuItem.tenant_id == uuid.UUID(tenant_id))
            .where(MenuItem.is_available == True)
        )
        if query:
            stmt = stmt.where(MenuItem.name.ilike(f"%{query}%") | MenuItem.description.ilike(f"%{query}%"))
        
        result = await db.execute(stmt)
        items = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description or "",
                "price": float(item.price),
                "allergens": item.allergens or [],
                "is_available": item.is_available
            }
            for item in items
        ]

async def create_confirmed_order(
    tenant_id: str,
    customer_phone: str,
    cart_items: List[Dict[str, Any]],
    delivery_address: Optional[str],
    delivery_type: str = "delivery",
    customer_notes: Optional[str] = None
) -> Dict[str, Any]:
    """Persist an order and trigger dummy payment."""
    if not cart_items:
        return {"error": "Cart is empty. Please add items before placing an order."}

    async with AsyncSessionLocal() as db:
        # 1. Get or create Customer
        stmt = (
            select(Customer)
            .where(Customer.tenant_id == uuid.UUID(tenant_id))
            .where(Customer.whatsapp_phone == customer_phone)
        )
        res = await db.execute(stmt)
        customer = res.scalar_one_or_none()
        if not customer:
            customer = Customer(
                tenant_id=uuid.UUID(tenant_id),
                whatsapp_phone=customer_phone,
                delivery_address=delivery_address
            )
            db.add(customer)
            await db.flush()
        elif delivery_address:
            customer.delivery_address = delivery_address

        customer.order_count += 1

        # 2. Calculate Total
        total_amount = sum(item["price"] * item["quantity"] for item in cart_items)
        order_number = f"#{uuid.uuid4().hex[:6].upper()}"

        # 3. Create Order
        order = Order(
            tenant_id=uuid.UUID(tenant_id),
            customer_id=customer.id,
            order_number=order_number,
            status="confirmed",
            total_amount=total_amount,
            payment_status="dummy_paid",
            payment_method="dummy_instant",
            delivery_type=delivery_type,
            delivery_address=delivery_address,
            customer_notes=customer_notes
        )
        db.add(order)
        await db.flush()

        # 4. Create Order Items
        for item in cart_items:
            item_id = uuid.UUID(item["menu_item_id"]) if "menu_item_id" in item and item["menu_item_id"] else None
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item_id,
                item_name=item["name"],
                quantity=item["quantity"],
                unit_price=item["price"],
                total_price=item["price"] * item["quantity"],
                special_instructions=item.get("notes")
            )
            db.add(order_item)

        await db.commit()

        # 5. Process simulated dummy payment
        payment_info = dummy_payment_service.process_instant_dummy_payment(
            order_id=str(order.id),
            amount=float(total_amount)
        )

        # 6. Notify Kitchen / Staff
        tenant_stmt = select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
        tenant_res = await db.execute(tenant_stmt)
        tenant = tenant_res.scalar_one_or_none()

        if tenant and tenant.owner_whatsapp_number:
            items_summary = "\n".join([f"- {it['quantity']}x {it['name']}" for it in cart_items])
            alert_msg = (
                f"🔔 *NEW ORDER {order_number}*\n"
                f"Customer: {customer_phone}\n"
                f"Type: {delivery_type.capitalize()}\n"
                f"Address: {delivery_address or 'Pickup at counter'}\n"
                f"Total: Rs. {total_amount:.0f} (Paid)\n\n"
                f"Items:\n{items_summary}"
            )
            await whatsapp_service.send_text_message(
                to_phone=tenant.owner_whatsapp_number,
                text=alert_msg,
                phone_number_id=tenant.phone_number_id,
                access_token=tenant.meta_access_token
            )

        return {
            "order_number": order_number,
            "order_id": str(order.id),
            "total_amount": float(total_amount),
            "payment_status": "dummy_paid",
            "delivery_type": delivery_type,
            "delivery_address": delivery_address,
            "items": cart_items,
            "estimated_delivery_minutes": 35
        }

async def get_active_customer_order(tenant_id: str, customer_phone: str) -> Optional[Dict[str, Any]]:
    """Fetch the most recent active or recent order for the customer from the database."""
    async with AsyncSessionLocal() as db:
        # Check for non-delivered active order first
        stmt = (
            select(Order)
            .join(Customer, Order.customer_id == Customer.id)
            .where(Order.tenant_id == uuid.UUID(tenant_id))
            .where(Customer.whatsapp_phone == customer_phone)
            .order_by(Order.created_at.desc())
        )
        res = await db.execute(stmt)
        order = res.scalars().first()
        if not order:
            return None

        # Fetch items
        items_stmt = select(OrderItem).where(OrderItem.order_id == order.id)
        i_res = await db.execute(items_stmt)
        items = i_res.scalars().all()

        return {
            "order_number": order.order_number,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "payment_status": order.payment_status,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at.strftime("%I:%M %p") if order.created_at else "Recently",
            "items": [{"name": it.item_name, "quantity": it.quantity, "total": float(it.total_price)} for it in items]
        }
