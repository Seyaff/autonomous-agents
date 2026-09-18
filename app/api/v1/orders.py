import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.order import Order, OrderItem
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.services.whatsapp_service import whatsapp_service
from app.services.marketing_service import marketing_service
from app.api.v1.ws_orders import ws_manager
from app.config import settings

router = APIRouter(prefix="/orders", tags=["Orders & Kitchen"])

class OrderStatusUpdate(BaseModel):
    status: str # confirmed, preparing, out_for_delivery, delivered, cancelled

def serialize_order(o: Order) -> dict:
    items_data = []
    if hasattr(o, "items") and o.items:
        for item in o.items:
            items_data.append({
                "id": str(item.id),
                "name": item.item_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
                "notes": item.special_instructions
            })

    return {
        "id": str(o.id),
        "order_number": o.order_number,
        "status": o.status,
        "total_amount": float(o.total_amount),
        "payment_status": o.payment_status,
        "payment_method": o.payment_method,
        "delivery_type": o.delivery_type,
        "delivery_address": o.delivery_address,
        "customer_notes": o.customer_notes,
        "items": items_data,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }

@router.get("")
async def list_orders_query(tenant_id: Optional[str] = Query(None)):
    """List recent orders with items via query parameter."""
    async with AsyncSessionLocal() as db:
        stmt = select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc()).limit(50)
        if tenant_id:
            try:
                stmt = stmt.where(Order.tenant_id == uuid.UUID(tenant_id))
            except ValueError:
                return []
        res = await db.execute(stmt)
        orders = res.scalars().all()
        return [serialize_order(o) for o in orders]

@router.get("/{tenant_id}")
async def list_orders_path(tenant_id: str):
    """List recent orders for the restaurant kitchen display via path parameter."""
    async with AsyncSessionLocal() as db:
        try:
            t_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant UUID")

        stmt = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.tenant_id == t_uuid)
            .order_by(Order.created_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        orders = res.scalars().all()
        return [serialize_order(o) for o in orders]

@router.patch("/{order_id}/status")
async def update_order_status(order_id: str, payload: OrderStatusUpdate):
    """
    Update order status (e.g. from Kitchen Display or Rider),
    notify customer via WhatsApp, broadcast to KDS WebSockets,
    and trigger autonomous post-delivery viral loops.
    """
    async with AsyncSessionLocal() as db:
        try:
            o_uuid = uuid.UUID(order_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order UUID")

        res = await db.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == o_uuid)
        )
        order = res.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        old_status = order.status
        order.status = payload.status
        await db.commit()
        await db.refresh(order)

        # Broadcast live status update over WebSockets to KDS tablets
        tenant_str = str(order.tenant_id)
        await ws_manager.broadcast_order_event(
            tenant_id=tenant_str,
            event_type="STATUS_UPDATED",
            data={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "old_status": old_status,
                "new_status": order.status,
            }
        )

        # Fetch Customer and Tenant to send WhatsApp status alert
        c_res = await db.execute(select(Customer).where(Customer.id == order.customer_id))
        customer = c_res.scalar_one_or_none()

        t_res = await db.execute(select(Tenant).where(Tenant.id == order.tenant_id))
        tenant = t_res.scalar_one_or_none()

        if customer and tenant and customer.whatsapp_phone:
            restaurant_name = tenant.name or "Da Pakhtun Dera"
            status_messages = {
                "preparing": f"🍳 *Order Update ({order.order_number})*\nAapka khana {restaurant_name} kitchen mein fresh tayyar ho raha hai!",
                "out_for_delivery": f"🛵 *Rider Nikal Chuka Hai! ({order.order_number})*\nAapka garam khana rider ke pass hai aur kuch hi dair mein pohanchne wala hai!",
                "delivered": f"🎉 *Order Delivered! ({order.order_number})*\nAapka khana pohanch gaya hai. Garam enjoy karein! {restaurant_name} choose karne ka shukriya! 🍽️",
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

        # If delivered, trigger the 45-minute viral UGC loop (Instagram Story / WhatsApp Status tag prompt)
        if payload.status == "delivered":
            await marketing_service.schedule_post_delivery_viral_prompt(order_id=str(order.id))

        return {
            "status": "updated",
            "order_id": str(order.id),
            "old_status": old_status,
            "new_status": order.status
        }
