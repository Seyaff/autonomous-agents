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

@router.patch("/{order_id}/status")
async def update_order_status(order_id: str, payload: OrderStatusUpdate):
    """Update order status (e.g. from Kitchen Display)."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        order = res.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        order.status = payload.status
        await db.commit()
        return {"status": "updated", "order_id": str(order.id), "new_status": order.status}
