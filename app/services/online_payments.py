"""
Online payments for orders (JazzCash and Easypaisa), behind one interface.

How it works:
- After the customer confirms an order, they choose how to pay: online, or cash on delivery.
- Online: we create a payment link, send it in WhatsApp, and the order waits as
  `awaiting_payment`. The provider calls our webhook when the payment is done. Only that
  call marks the order paid. The browser's return page is never trusted for it.
- Cash on delivery goes straight to the kitchen.
- If the link isn't paid within PAYMENT_WAIT, the order expires and the customer is offered
  cash on delivery.

The provider adapters below are not finished. Each one raises ProviderNotConfigured until its
merchant credentials and the provider's documented request and signature formats are added.
Nothing is guessed: a half-built signature check would accept forged payments.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Protocol

from pymongo.errors import DuplicateKeyError

from core.settings import settings

logger = logging.getLogger(__name__)

PAYMENT_WAIT = timedelta(minutes=15)
PAYMENTS = "order_payments"
PAY_PREFIX = "order_pay:"
AWAITING_PAYMENT = "awaiting_payment"
PAYMENT_EXPIRED = "payment_expired"
CHOOSING_PAYMENT = "choosing_payment"


class ProviderNotConfigured(Exception):
    pass


class OnlineProvider(Protocol):
    name: str

    def configured(self) -> bool: ...

    async def create_payment_link(self, *, reference: str, amount_pkr: int, description: str, return_url: str) -> str: ...

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """Returns {'reference', 'amount_pkr', 'status'} only if the signature is valid. Raises otherwise."""
        ...


class JazzCashProvider:
    name = "jazzcash"

    def configured(self) -> bool:
        return bool(settings.JAZZCASH_MERCHANT_ID and settings.JAZZCASH_PASSWORD and settings.JAZZCASH_INTEGRITY_SALT)

    async def create_payment_link(self, *, reference: str, **_: Any) -> str:
        # The customer opens this link. It builds and posts the signed form to JazzCash.
        return f"{settings.PUBLIC_API_BASE.rstrip('/')}/payments/jazzcash/checkout/{reference}"

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        from services import jazzcash

        fields = jazzcash.parse_callback(body)
        jazzcash.verify_callback(fields, settings.JAZZCASH_INTEGRITY_SALT)
        code = fields.get("pp_ResponseCode", "")
        if code == jazzcash.SUCCESS_CODE:
            status = "paid"
        elif code in jazzcash.PENDING_CODES:
            status = "pending"
        else:
            status = "failed"
        return {
            "reference": fields.get("pp_TxnRefNo", ""),
            "amount_pkr": int(fields.get("pp_Amount", "0")) // 100,
            "status": status,
            "response_code": fields.get("pp_ResponseCode", ""),
            "response_message": fields.get("pp_ResponseMessage", ""),
        }


class EasypaisaProvider:
    name = "easypaisa"

    def configured(self) -> bool:
        return bool(settings.EASYPAISA_STORE_ID and settings.EASYPAISA_HASH_KEY)

    async def create_payment_link(self, **_: Any) -> str:
        raise ProviderNotConfigured("Easypaisa request format isn't implemented yet.")

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        raise ProviderNotConfigured("Easypaisa signature check isn't implemented yet.")


PROVIDERS: Dict[str, OnlineProvider] = {"jazzcash": JazzCashProvider(), "easypaisa": EasypaisaProvider()}


def provider_for(tenant: Dict[str, Any]) -> Optional[OnlineProvider]:
    """The provider this restaurant chose, if it's set up. None means cash on delivery only."""
    name = (tenant or {}).get("online_payment_provider")
    provider = PROVIDERS.get(name) if name else None
    return provider if provider and provider.configured() else None


def parse_pay_button(button_id: str) -> tuple:
    """'order_pay:ORD-1:cod' -> ('ORD-1', 'cod'). Unknown ids -> (None, None)."""
    if not button_id.startswith(PAY_PREFIX):
        return None, None
    order_id, _, method = button_id[len(PAY_PREFIX):].rpartition(":")
    return (order_id, method) if order_id and method else (None, None)


def expired(order: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    deadline = order.get("payment_expires_at")
    if not deadline:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) >= deadline


async def record_payment(db, *, provider: str, reference: str, order_id: str, amount_pkr: int, status: str) -> bool:
    """Records a payment once. Returns False if this reference was already recorded (a repeated callback)."""
    try:
        await db[PAYMENTS].insert_one({
            "provider": provider,
            "reference": reference,
            "order_id": order_id,
            "amount_pkr": amount_pkr,
            "status": status,
            "created_at": datetime.now(timezone.utc),
        })
        return True
    except DuplicateKeyError:
        return False


async def ensure_payment_indexes(db) -> None:
    await db[PAYMENTS].create_index([("provider", 1), ("reference", 1)], unique=True, name="uniq_payment_reference")


# ---------------------------------------------------------------------------
# The order steps
# ---------------------------------------------------------------------------

async def _reply(tenant: Dict[str, Any], customer_phone: str, text: str) -> None:
    from core.whatsapp_utils import resolve_tenant_whatsapp_credentials, send_text

    token, phone_id = resolve_tenant_whatsapp_credentials(tenant)
    await send_text(to_phone=customer_phone, text=text, token=token, phone_number_id=phone_id)


async def _buttons(tenant: Dict[str, Any], customer_phone: str, body: str, buttons: list) -> None:
    from core.whatsapp_utils import resolve_tenant_whatsapp_credentials, send_buttons

    token, phone_id = resolve_tenant_whatsapp_credentials(tenant)
    await send_buttons(to_phone=customer_phone, body=body, buttons=buttons, token=token, phone_number_id=phone_id)


async def ask_how_to_pay(db, tenant: Dict[str, Any], order: Dict[str, Any], provider: OnlineProvider) -> None:
    """Called after the customer confirms. Offers online payment or cash on delivery."""
    order_id = order["order_id"]
    await db["orders"].update_one({"order_id": order_id}, {"$set": {"status": CHOOSING_PAYMENT, "updated_at": datetime.now(timezone.utc)}})
    await _buttons(
        tenant, order["customer_phone"],
        f"Order {order_id} ka payment kaise karein?",
        [
            {"id": f"{PAY_PREFIX}{order_id}:{provider.name}", "title": provider.name.capitalize()},
            {"id": f"{PAY_PREFIX}{order_id}:cod", "title": "Cash on delivery"},
        ],
    )


async def handle_payment_choice(db, tenant: Dict[str, Any], customer_phone: str, order_id: str, method: str) -> str:
    """The customer picked a way to pay. Returns what happened, for logs."""
    from core.events import broadcast_order_update

    order = await db["orders"].find_one({"tenant_id": tenant["tenant_id"], "customer_phone": customer_phone, "order_id": order_id})
    if not order:
        await _reply(tenant, customer_phone, "Ye order mil nahi raha. Dobara order karein.")
        return "order not found"
    if order.get("status") not in (CHOOSING_PAYMENT, PAYMENT_EXPIRED):
        return f"ignored: order is {order.get('status')}"

    now = datetime.now(timezone.utc)
    if method == "cod":
        await db["orders"].update_one({"order_id": order_id}, {
            "$set": {"status": "pending", "payment_method": "cod", "updated_at": now},
            "$push": {"status_history": {"status": "pending", "at": now, "by": "customer", "by_user_id": None, "customer_notified": True}},
        })
        await _reply(tenant, customer_phone, f"Thek hai, cash on delivery. Order {order_id} restaurant ko chala gaya.")
        order["status"] = "pending"
        order.pop("_id", None)
        await broadcast_order_update(tenant_id=tenant["tenant_id"], event_type="order.created", order_data=order)
        return "cod"

    provider = PROVIDERS.get(method)
    if provider is None or not provider.configured():
        await _reply(tenant, customer_phone, "Online payment abhi available nahi. Cash on delivery chunein.")
        return "provider unavailable"

    from services.jazzcash import txn_ref

    reference = txn_ref(order_id, now)
    try:
        link = await provider.create_payment_link(
            reference=reference,
            amount_pkr=int(round(float(order.get("total_amount", 0)))),
            description=f"Order {order_id}",
            return_url=settings.PAYMENT_RETURN_URL,
        )
    except ProviderNotConfigured as e:
        logger.error(f"[payments] {provider.name} not ready: {e}")
        await _reply(tenant, customer_phone, "Online payment abhi set up nahi hua. Cash on delivery chunein.")
        return "provider not ready"

    await db["orders"].update_one({"order_id": order_id}, {"$set": {
        "status": AWAITING_PAYMENT,
        "payment_method": provider.name,
        "payment_reference": reference,
        "payment_expires_at": now + PAYMENT_WAIT,
        "updated_at": now,
    }})
    await _reply(tenant, customer_phone, f"Payment ke liye yeh link kholein (15 minute tak valid): {link}")
    return "payment link sent"


async def handle_payment_webhook(db, provider_name: str, headers: Dict[str, str], body: bytes) -> str:
    """The provider says a payment finished. Only a valid signature, the right amount and an
    order still waiting for payment can mark it paid. A repeated callback changes nothing."""
    from core.events import broadcast_order_update

    provider = PROVIDERS.get(provider_name)
    if provider is None:
        return "unknown provider"
    event = provider.verify_webhook(headers, body)  # raises if the signature is wrong
    if event.get("status") == "pending":
        logger.info(f"[payments] JazzCash payment {event.get('reference')} is pending: code {event.get('response_code')}")
        return "payment pending"
    if event.get("status") != "paid":
        logger.warning(f"[payments] JazzCash payment {event.get('reference')} not successful: code {event.get('response_code')}, {event.get('response_message')}")
        return "not a successful payment"

    order = await db["orders"].find_one({"payment_reference": event["reference"]})
    if not order:
        return await _complete_hosted_invoice(db, provider_name, event)
    if int(round(float(order.get("total_amount", 0)))) != int(event["amount_pkr"]):
        logger.error(f"[payments] amount mismatch for {order['order_id']}: expected {order.get('total_amount')}, got {event['amount_pkr']}")
        return "amount mismatch"
    if not await record_payment(db, provider=provider_name, reference=event["reference"], order_id=order["order_id"],
                                amount_pkr=int(event["amount_pkr"]), status="paid"):
        return "already recorded"
    if order.get("status") not in (AWAITING_PAYMENT, PAYMENT_EXPIRED):
        return f"ignored: order is {order.get('status')}"

    now = datetime.now(timezone.utc)
    await db["orders"].update_one({"order_id": order["order_id"]}, {
        "$set": {"status": "pending", "paid_at": now, "updated_at": now},
        "$push": {"status_history": {"status": "pending", "at": now, "by": "payment", "by_user_id": None, "customer_notified": True}},
    })
    tenant = await db["tenants"].find_one({"tenant_id": order["tenant_id"]}) or {"tenant_id": order["tenant_id"]}
    await _reply(tenant, order["customer_phone"], f"Payment mil gayi. Order {order['order_id']} restaurant ko chala gaya.")
    order["status"] = "pending"
    order.pop("_id", None)
    await broadcast_order_update(tenant_id=order["tenant_id"], event_type="order.created", order_data=order)
    return "marked paid"


async def _complete_hosted_invoice(db, provider_name: str, event: Dict[str, Any]) -> str:
    """A subscription or renewal invoice paid through the hosted page."""
    from services.invoices import INVOICES, complete_invoice

    invoice = await db[INVOICES].find_one({"payment_reference": event["reference"]})
    if not invoice:
        return "no order or invoice for this payment"
    if invoice.get("status") != "open":
        return f"ignored: invoice is {invoice.get('status')}"
    if int(round(float(invoice.get("amount_pkr", 0)))) != int(event["amount_pkr"]):
        logger.error(f"[payments] amount mismatch for {invoice['invoice_id']}")
        return "amount mismatch"
    if not await record_payment(db, provider=provider_name, reference=event["reference"], order_id=invoice["invoice_id"],
                                amount_pkr=int(event["amount_pkr"]), status="paid"):
        return "already recorded"
    await complete_invoice(db, invoice, provider_name, event["reference"])
    return "invoice paid"


async def expire_stale_payments(db, now: Optional[datetime] = None) -> int:
    """Orders whose payment link ran out. The customer is offered cash on delivery instead."""
    now = now or datetime.now(timezone.utc)
    stale = db["orders"].find({"status": AWAITING_PAYMENT, "payment_expires_at": {"$lte": now}})
    count = 0
    async for order in stale:
        await db["orders"].update_one({"order_id": order["order_id"]}, {"$set": {"status": PAYMENT_EXPIRED, "updated_at": now}})
        tenant = await db["tenants"].find_one({"tenant_id": order["tenant_id"]}) or {"tenant_id": order["tenant_id"]}
        await _buttons(
            tenant, order["customer_phone"],
            f"Order {order['order_id']} ka online payment nahi aaya. Cash on delivery karein?",
            [{"id": f"{PAY_PREFIX}{order['order_id']}:cod", "title": "Cash on delivery"}],
        )
        count += 1
    return count
