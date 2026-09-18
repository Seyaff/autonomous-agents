import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.order import Order, OrderItem

router = APIRouter(prefix="/orders", tags=["Orders & Kitchen"])

class OrderStatusUpdate(BaseModel):
    status: str # confirmed, preparing, out_for_delivery, delivered, cancelled

@router.get("/{tenant_id}")
async def list_orders(tenant_id: str):
    """List recent orders for the restaurant kitchen display."""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Order)
            .where(Order.tenant_id == uuid.UUID(tenant_id))
            .order_by(Order.created_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        orders = res.scalars().all()
        return [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": float(o.total_amount),
                "payment_status": o.payment_status,
                "delivery_type": o.delivery_type,
                "delivery_address": o.delivery_address,
                "customer_notes": o.customer_notes,
                "created_at": o.created_at.isoformat() if o.created_at else None
            }
            for o in orders
        ]

from app.models.customer import Customer
from app.models.tenant import Tenant
from app.services.whatsapp_service import whatsapp_service
from app.config import settings

@router.patch("/{order_id}/status")
async def update_order_status(order_id: str, payload: OrderStatusUpdate):
    """Update order status (e.g. from Kitchen Display or Rider) and notify customer via WhatsApp."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        order = res.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        old_status = order.status
        order.status = payload.status
        await db.commit()

        # Fetch Customer and Tenant to send WhatsApp status alert
        c_res = await db.execute(select(Customer).where(Customer.id == order.customer_id))
        customer = c_res.scalar_one_or_none()

        t_res = await db.execute(select(Tenant).where(Tenant.id == order.tenant_id))
        tenant = t_res.scalar_one_or_none()

        if customer and tenant and customer.whatsapp_phone:
            status_messages = {
                "preparing": f"🍳 *Order Update ({order.order_number})*\nAapka khana Da Pakhtun Dera kitchen mein fresh tayyar ho raha hai!",
                "out_for_delivery": f"🛵 *Rider Nikal Chuka Hai! ({order.order_number})*\nAapka garam khana rider ke pass hai aur kuch hi dair mein pohanchne wala hai!",
                "delivered": f"🎉 *Order Delivered! ({order.order_number})*\nAapka khana pohanch gaya hai. Garam enjoy karein! Da Pakhtun Dera choose karne ka shukriya! 🍽️",
                "cancelled": f"❌ *Order Cancelled ({order.order_number})*\nAapka order cancel kar diya gaya hai. Mazeed maloomat ke liye humein rabta karein."
            }
            alert_text = status_messages.get(payload.status)
            if alert_text:
                await whatsapp_service.send_text_message(
                    to_phone=customer.whatsapp_phone,
                    text=alert_text,
                    phone_number_id=tenant.phone_number_id,
                    access_token=settings.META_ACCESS_TOKEN or tenant.meta_access_token
                )

        return {"status": "updated", "order_id": str(order.id), "old_status": old_status, "new_status": order.status}
