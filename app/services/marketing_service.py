import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy import select, and_, or_
from app.core.database import AsyncSessionLocal
from app.models.order import Order
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.services.whatsapp_service import whatsapp_service
from app.config import settings

logger = logging.getLogger(__name__)

class MarketingService:
    @staticmethod
    async def schedule_post_delivery_viral_prompt(order_id: str, delay_seconds: int = 2700):
        """
        Schedules a 45-minute post-delivery message asking diner to share on
        Instagram Stories or WhatsApp Status for a free complimentary item (Naan / Kahwa).
        """
        async def _send_prompt():
            try:
                # In development/test, allow quick verification if delay_seconds is short
                await asyncio.sleep(delay_seconds)
                async with AsyncSessionLocal() as db:
                    res = await db.execute(select(Order).where(Order.id == order_id))
                    order = res.scalar_one_or_none()
                    if not order or order.status != "delivered":
                        return

                    c_res = await db.execute(select(Customer).where(Customer.id == order.customer_id))
                    customer = c_res.scalar_one_or_none()

                    t_res = await db.execute(select(Tenant).where(Tenant.id == order.tenant_id))
                    tenant = t_res.scalar_one_or_none()

                    if not customer or not tenant or not customer.whatsapp_phone:
                        return

                    restaurant_name = tenant.name or "Da Pakhtun Dera"
                    prompt_text = (
                        f"Assalam-o-Alaikum! Umeed hai aapka {restaurant_name} ka khana garam aur lazeez laga hoga! 🌟\n\n"
                        f"Agar aapko hamara khana aur service pasand aayi, to apne *Instagram Story* ya *WhatsApp Status* "
                        f"par khane ki tasveer laga kar humein tag karein! 📸\n\n"
                        f"🎁 *Screenshot share karne par aglay order par hamari taraf se complimentary Roghani Naan ya Peshawari Kahwa free enjoy karein!*"
                    )

                    await whatsapp_service.send_text_message(
                        to_phone=customer.whatsapp_phone,
                        text=prompt_text,
                        phone_number_id=tenant.phone_number_id,
                        access_token=settings.META_ACCESS_TOKEN or tenant.meta_access_token
                    )
                    logger.info(f"Post-delivery viral prompt dispatched to {customer.whatsapp_phone} for order {order.order_number}")
            except Exception as e:
                logger.error(f"Error in post-delivery viral loop prompt: {e}")

        # Fire as background task without blocking
        asyncio.create_task(_send_prompt())

    @staticmethod
    async def run_win_back_campaign(tenant_id: Optional[str] = None) -> List[dict]:
        """
        Scans customers who ordered 6 to 7 days ago and haven't ordered since.
        Dispatches a personalized re-engagement nudge in Pakistani Roman Urdu.
        """
        dispatched = []
        now = datetime.now(timezone.utc)
        six_days_ago = now - timedelta(days=7)
        seven_days_ago = now - timedelta(days=6)

        async with AsyncSessionLocal() as db:
            # Find customers who ordered around 6-7 days ago
            query = select(Order).where(
                and_(
                    Order.created_at >= six_days_ago,
                    Order.created_at <= seven_days_ago,
                    Order.status.in_(["delivered", "confirmed"])
                )
            )
            if tenant_id:
                query = query.where(Order.tenant_id == tenant_id)

            res = await db.execute(query)
            eligible_orders = res.scalars().all()

            for ord_obj in eligible_orders:
                c_res = await db.execute(select(Customer).where(Customer.id == ord_obj.customer_id))
                cust = c_res.scalar_one_or_none()

                t_res = await db.execute(select(Tenant).where(Tenant.id == ord_obj.tenant_id))
                ten = t_res.scalar_one_or_none()

                if not cust or not ten or not cust.whatsapp_phone:
                    continue

                cust_name = cust.name or "Janab"
                ten_name = ten.name or "Da Pakhtun Dera"

                re_engage_msg = (
                    f"Assalam-o-Alaikum {cust_name}! 🥩\n\n"
                    f"Lagbhag ek hafta ho gaya aapko {ten_name} ka lazeez khana chakhay huway!\n\n"
                    f"Aaj shaam ke khane ke liye hamara fresh Shinwari Karahi & BBQ ka batch tayyar hai. "
                    f"Kya aapke liye garam delivery lagwayein? Reply karein to menu aur deals pesh karein! 🍽️"
                )

                try:
                    await whatsapp_service.send_text_message(
                        to_phone=cust.whatsapp_phone,
                        text=re_engage_msg,
                        phone_number_id=ten.phone_number_id,
                        access_token=settings.META_ACCESS_TOKEN or ten.meta_access_token
                    )
                    dispatched.append({
                        "customer_phone": cust.whatsapp_phone,
                        "customer_name": cust.name,
                        "last_order_number": ord_obj.order_number,
                        "timestamp": now.isoformat()
                    })
                except Exception as ex:
                    logger.error(f"Failed to send win-back to {cust.whatsapp_phone}: {ex}")

        return dispatched

marketing_service = MarketingService()
