"""
Email through Resend. Off until RESEND_API_KEY is set: nothing is sent, and the attempt is logged.

Every email is for one event and carries a dedupe key, so the same event never emails twice
(for example, a trial reminder runs once, even though the daily job runs every day).
Sending never blocks or breaks the request that caused it.
"""

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from pymongo.errors import DuplicateKeyError

from core.settings import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
EMAIL_LOG = "email_log"
_background: set = set()


def enabled() -> bool:
    return bool(settings.RESEND_API_KEY)


async def ensure_email_indexes(db) -> None:
    await db[EMAIL_LOG].create_index([("key", 1)], unique=True, name="uniq_email_key")


def render(title: str, lines: list, button_text: Optional[str] = None, button_path: Optional[str] = None) -> tuple:
    """(html, text) for a short transactional email."""
    frontend = settings.frontend_origin
    body = "".join(f"<p style='margin:0 0 12px'>{html.escape(line)}</p>" for line in lines)
    button = ""
    text_lines = [title, "", *lines]
    if button_text and button_path:
        url = f"{frontend}{button_path}"
        button = (f"<p><a href='{url}' style='display:inline-block;padding:10px 16px;background:#131925;"
                  f"color:#fff;border-radius:8px;text-decoration:none'>{html.escape(button_text)}</a></p>")
        text_lines += ["", f"{button_text}: {url}"]
    doc = (
        "<div style='font-family:Helvetica,Arial,sans-serif;font-size:15px;color:#131925;max-width:560px'>"
        f"<h2 style='font-size:18px;margin:0 0 16px'>{html.escape(title)}</h2>{body}{button}"
        "<p style='margin-top:24px;font-size:12px;color:#5b6475'>Siyaf · You're getting this because of your Siyaf account.</p>"
        "</div>"
    )
    return doc, "\n".join(text_lines)


async def send(to: str, subject: str, html_body: str, text_body: str, dedupe_key: Optional[str] = None) -> bool:
    """Sends one email. Returns True if it was sent. Never raises."""
    if not to:
        return False
    if not enabled():
        logger.info(f"[email] not sent (RESEND_API_KEY not set): '{subject}' to {to}")
        return False

    try:
        from core.database import get_database

        db = get_database()
        if dedupe_key:
            try:
                await db[EMAIL_LOG].insert_one({"key": dedupe_key, "to": to, "subject": subject, "created_at": datetime.now(timezone.utc)})
            except DuplicateKeyError:
                return False

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html_body, "text": text_body},
            )
        if response.status_code >= 300:
            logger.error(f"[email] Resend refused '{subject}' to {to}: {response.status_code} {response.text[:200]}")
            if dedupe_key:
                await db[EMAIL_LOG].delete_one({"key": dedupe_key})
            return False
        logger.info(f"[email] sent '{subject}' to {to}")
        return True
    except Exception as e:
        logger.error(f"[email] could not send '{subject}' to {to}: {e}")
        return False


def send_later(to: str, subject: str, html_body: str, text_body: str, dedupe_key: Optional[str] = None) -> None:
    """Sends in the background, so the request that caused it returns straight away."""
    task = asyncio.create_task(send(to, subject, html_body, text_body, dedupe_key))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def owner_email(db, tenant_id: str) -> Optional[str]:
    user = await db["users"].find_one({"tenants": tenant_id, "role": "OWNER"}, {"email": 1})
    return (user or {}).get("email")


def _tenant_name(tenant: Optional[Dict[str, Any]]) -> str:
    return (tenant or {}).get("business_name") or "your restaurant"


def _date(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:10]
    return value.strftime("%d %b %Y")


def _safe(fn):
    """An email must never break the request that caused it. A formatting problem is logged, not raised."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"[email] could not prepare {fn.__name__}: {e}")
            return None

    return wrapper


def _mail(to: str, subject: str, title: str, lines: list, dedupe_key: str, button_text: Optional[str] = None, button_path: Optional[str] = None) -> None:
    html_body, text_body = render(title, lines, button_text, button_path)
    send_later(to, subject, html_body, text_body, dedupe_key)


# ---------------------------------------------------------------------------
# Events. Each one names the email it sends and the key that stops a repeat.
# ---------------------------------------------------------------------------

@_safe
def welcome(to: str, name: str, user_id: str) -> None:
    _mail(to, "Welcome to Siyaf",
          "Welcome to Siyaf", [f"Hi {name}, your account is ready.",
                               "Next, set up your restaurant. Your 3-day free trial starts now."],
          f"welcome:{user_id}", "Set up my restaurant", "/setup")


@_safe
def password_changed(to: str, user_id: str, when: datetime) -> None:
    _mail(to, "Your Siyaf password was changed",
          "Your password was changed", [f"Your password was changed on {_date(when)}.",
                                        "If that wasn't you, reset your password straight away and sign out of other devices."],
          f"password_changed:{user_id}:{when.isoformat()}", "Reset password", "/login")


@_safe
def new_sign_in(to: str, user_id: str, when: datetime, device: str) -> None:
    _mail(to, "New sign-in to Siyaf",
          "New sign-in to your account", [f"Someone signed in on {_date(when)} from: {device or 'an unknown device'}.",
                                          "If that wasn't you, change your password and sign out everywhere."],
          f"new_sign_in:{user_id}:{when.isoformat()}", "Check my devices", "/dashboard/settings")


@_safe
def trial_ending(to: str, tenant: Optional[Dict[str, Any]], tenant_id: str, days_left: int) -> None:
    _mail(to, f"Your free trial ends in {days_left} day{'s' if days_left != 1 else ''}",
          "Your free trial is ending", [f"{_tenant_name(tenant)} has {days_left} day{'s' if days_left != 1 else ''} left in its free trial.",
                                        "Choose a plan to keep your agent replying to customers. No payment is taken until you choose."],
          f"trial_ending:{tenant_id}:{days_left}", "Choose a plan", "/dashboard/billing")


@_safe
def trial_ended(to: str, tenant: Optional[Dict[str, Any]], tenant_id: str) -> None:
    _mail(to, "Your free trial has ended",
          "Your free trial has ended", [f"{_tenant_name(tenant)}'s free trial has ended, so the agent has stopped replying to customers.",
                                        "Choose a plan to start it again."],
          f"trial_ended:{tenant_id}", "Choose a plan", "/dashboard/billing")


@_safe
def invoice_created(to: str, tenant: Optional[Dict[str, Any]], invoice: Dict[str, Any]) -> None:
    _mail(to, f"Invoice {invoice['invoice_id']} for {_tenant_name(tenant)}",
          "New invoice", [f"Invoice {invoice['invoice_id']} for PKR {invoice['amount_pkr']:,} is ready.",
                          f"Please pay it by {_date(invoice.get('due_at'))}."],
          f"invoice_created:{invoice['invoice_id']}", "Pay invoice", "/dashboard/billing")


@_safe
def payment_received(to: str, tenant: Optional[Dict[str, Any]], invoice: Dict[str, Any], active_until: Optional[str]) -> None:
    lines = [f"We received PKR {invoice['amount_pkr']:,} for invoice {invoice['invoice_id']}. Thank you."]
    if active_until:
        lines.append(f"Your plan is active until {_date(active_until)}.")
    _mail(to, f"Payment received, {invoice['invoice_id']}",
          "Payment received", lines, f"payment_received:{invoice['invoice_id']}", "View invoices", "/dashboard/billing")


@_safe
def payment_failed(to: str, tenant: Optional[Dict[str, Any]], invoice: Dict[str, Any], reason: str) -> None:
    _mail(to, f"Payment didn't go through, {invoice['invoice_id']}",
          "Payment didn't go through", [f"The payment of PKR {invoice['amount_pkr']:,} for {invoice['invoice_id']} didn't go through.",
                                        f"Reason: {reason}", "Nothing was charged. Try again from the Billing page."],
          f"payment_failed:{invoice['invoice_id']}:{datetime.now(timezone.utc).date()}", "Try again", "/dashboard/billing")


@_safe
def past_due(to: str, tenant: Optional[Dict[str, Any]], invoice: Dict[str, Any]) -> None:
    _mail(to, f"Payment overdue for {_tenant_name(tenant)}",
          "Payment overdue", [f"Invoice {invoice['invoice_id']} for PKR {invoice['amount_pkr']:,} is past due.",
                              "Your agent keeps replying for now, but it will pause if the invoice stays unpaid for a week."],
          f"past_due:{invoice['invoice_id']}", "Pay now", "/dashboard/billing")


@_safe
def paused(to: str, tenant: Optional[Dict[str, Any]], invoice: Dict[str, Any]) -> None:
    _mail(to, f"Your agent is paused for {_tenant_name(tenant)}",
          "Your agent is paused", ["Your agent has stopped replying to customers because invoice "
                                   f"{invoice['invoice_id']} is still unpaid.",
                                   "Pay the invoice and it starts again straight away."],
          f"paused:{invoice['invoice_id']}", "Pay now", "/dashboard/billing")


@_safe
def plan_changed(to: str, tenant: Optional[Dict[str, Any]], plan_name: str, starts: Optional[str], invoice_id: Optional[str]) -> None:
    if starts:
        lines = [f"Your plan changes to {plan_name} on {_date(starts)}. You keep your current plan until then."]
    else:
        lines = [f"Your plan is now {plan_name}." + (f" Invoice {invoice_id} covers the difference." if invoice_id else "")]
    key = f"plan_changed:{invoice_id or ('scheduled:' + plan_name + ':' + (starts or ''))}"
    _mail(to, f"Plan change for {_tenant_name(tenant)}", "Your plan changed", lines, key, "View plans", "/dashboard/billing")


@_safe
def subscription_canceled(to: str, tenant: Optional[Dict[str, Any]], tenant_id: str, ends: Optional[str]) -> None:
    _mail(to, f"Cancellation scheduled for {_tenant_name(tenant)}",
          "Your plan will end", [f"Your plan ends on {_date(ends)}. Everything keeps working until then.",
                                 "Changed your mind? Keep your plan from the Billing page."],
          f"canceled:{tenant_id}:{_date(ends)}", "Keep my plan", "/dashboard/billing")


@_safe
def whatsapp_disconnected(to: str, tenant: Optional[Dict[str, Any]], tenant_id: str, detail: str) -> None:
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    _mail(to, f"WhatsApp disconnected for {_tenant_name(tenant)}",
          "WhatsApp disconnected", [f"{_tenant_name(tenant)} lost its WhatsApp connection, so customers can't reach the agent.",
                                    detail or "Reconnect the number in Settings."],
          f"whatsapp_disconnected:{tenant_id}:{hour}", "Reconnect WhatsApp", "/dashboard/settings")


@_safe
def founder_new_restaurant(founder_email: str, tenant: Dict[str, Any], owner: str) -> None:
    _mail(founder_email, f"New restaurant: {_tenant_name(tenant)}",
          "New restaurant signed up", [f"{_tenant_name(tenant)} was created by {owner}.",
                                       "They're on a 3-day trial."],
          f"founder_new_restaurant:{tenant['tenant_id']}", "Open operations", "/founder")


async def owner_context(db, tenant_id: str) -> tuple:
    """(owner's email, restaurant) for a tenant. The email is None if the owner can't be found."""
    tenant = await db["tenants"].find_one({"tenant_id": tenant_id}, {"business_name": 1, "tenant_id": 1, "subscription": 1}) or {"tenant_id": tenant_id}
    return await owner_email(db, tenant_id), tenant
