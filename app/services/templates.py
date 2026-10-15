"""
WhatsApp message templates: the owner's own templates, kept in step with Meta, and sending them.

Meta only lets a business message a customer freely for 24 hours after the customer last wrote.
After that, only an approved template can be sent. Templates are written here, submitted to Meta
for review, and their approval status comes back through the webhook and the sync.

The checks below follow Meta's rules, so most mistakes are caught before Meta rejects the template.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

from core.whatsapp_utils import (
    SendResult,
    create_template,
    delete_template,
    list_templates,
    resolve_tenant_whatsapp_credentials,
    send_template,
)

logger = logging.getLogger(__name__)

TEMPLATES = "wa_templates"

NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,512}$")
VARIABLE = re.compile(r"\{\{\s*(\d+)\s*\}\}")
# A variable followed by nothing but punctuation still counts as the end of the message.
VARIABLE_AT_END = re.compile(r"\{\{\s*\d+\s*\}\}[\s.,!?]*$")
LANGUAGES: Dict[str, str] = {
    "en": "English",
    "en_US": "English (US)",
    "en_GB": "English (UK)",
    "ur": "Urdu",
    "ar": "Arabic",
}

# The standard template for order and booking updates once the 24-hour window has closed.
ORDER_UPDATE_TEMPLATE = "order_update"
ORDER_UPDATE_BODY = (
    "Hi {{1}}, here is an update on your order {{2}} from {{3}}: {{4}}. "
    "Reply to this message if you have any questions."
)
ORDER_UPDATE_EXAMPLES = ["Sana", "ORD-1A2B3C4D", "Glow Studio", "it has been accepted"]

# What {{4}} says for each status.
ORDER_UPDATE_PHRASES = {
    "accepted": "it has been accepted",
    "preparing": "it is being prepared",
    "out_for_delivery": "it is on the way",
    "delivered": "it is complete",
    "cancelled": "it has been cancelled",
}
HANDOVER_PHRASES = {**ORDER_UPDATE_PHRASES, "out_for_delivery": "it is ready"}
BOOKING_PHRASES = {
    "accepted": "your booking is confirmed",
    "delivered": "your booking is complete",
    "cancelled": "your booking has been cancelled",
}


class TemplateButton(BaseModel):
    type: Literal["QUICK_REPLY", "URL", "PHONE_NUMBER"]
    text: str = Field(min_length=1, max_length=25)
    url: Optional[str] = Field(None, max_length=2000)
    phone_number: Optional[str] = Field(None, max_length=20)

    @model_validator(mode="after")
    def _target(self) -> "TemplateButton":
        if self.type == "URL" and not (self.url or "").startswith("https://"):
            raise ValueError("A link button needs a web address starting with https://")
        if self.type == "PHONE_NUMBER" and not re.fullmatch(r"\+?\d{7,15}", (self.phone_number or "").replace(" ", "")):
            raise ValueError("A call button needs a phone number with the country code, e.g. +923001234567")
        return self


def variables_in(text: str) -> List[int]:
    return [int(n) for n in VARIABLE.findall(text or "")]


def _check_variables(text: str, where: str) -> int:
    """Variables must be {{1}}, {{2}}, ... in order, with no gaps. Returns how many there are."""
    found = variables_in(text)
    if found != list(range(1, len(found) + 1)):
        raise ValueError(f"The {where} variables must be {{{{1}}}}, {{{{2}}}} and so on, in order, each used once.")
    return len(found)


class TemplateDraft(BaseModel):
    """A template the owner wrote, before it goes to Meta."""

    name: str = Field(min_length=1, max_length=512)
    category: Literal["MARKETING", "UTILITY"]
    language: str = "en"
    header_text: Optional[str] = Field(None, max_length=60)
    header_example: Optional[str] = Field(None, max_length=60)
    body: str = Field(min_length=1, max_length=1024)
    body_examples: List[str] = Field(default_factory=list)
    footer: Optional[str] = Field(None, max_length=60)
    buttons: List[TemplateButton] = Field(default_factory=list, max_length=10)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: Any) -> Any:
        if not isinstance(v, str):
            return v
        name = re.sub(r"[\s-]+", "_", v.strip().lower())
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError("Use only lowercase letters, numbers and underscores in the name, e.g. eid_offer")
        return name

    @field_validator("language")
    @classmethod
    def _language(cls, v: str) -> str:
        if v not in LANGUAGES:
            raise ValueError(f"Pick a language: {', '.join(LANGUAGES)}")
        return v

    @model_validator(mode="after")
    def _rules(self) -> "TemplateDraft":
        body = self.body.strip()
        count = _check_variables(body, "message")
        if count:
            if VARIABLE.match(body) or VARIABLE_AT_END.search(body):
                raise ValueError("Meta doesn't allow a variable at the very start or end of the message. Add words around it.")
            if not VARIABLE.sub("", body).strip(" .,!?:;-"):
                raise ValueError("The message needs words, not only variables.")
            if len(self.body_examples) != count or any(not (e or "").strip() for e in self.body_examples):
                raise ValueError(f"Give an example for each of the {count} variables, so Meta can review the template.")
        elif self.body_examples:
            self.body_examples = []
        if self.header_text:
            header_count = _check_variables(self.header_text, "header")
            if header_count > 1:
                raise ValueError("The header can have at most one variable, {{1}}.")
            if header_count and not (self.header_example or "").strip():
                raise ValueError("Give an example for the header variable.")
        if self.footer and variables_in(self.footer):
            raise ValueError("The footer can't have variables.")
        kinds = [b.type for b in self.buttons]
        if kinds.count("URL") > 2 or kinds.count("PHONE_NUMBER") > 1:
            raise ValueError("Use at most two link buttons and one call button.")
        return self


def build_components(draft: TemplateDraft) -> List[Dict[str, Any]]:
    """The template in Meta's format. Quick replies come first: Meta needs buttons of one kind grouped."""
    components: List[Dict[str, Any]] = []
    if draft.header_text:
        header: Dict[str, Any] = {"type": "HEADER", "format": "TEXT", "text": draft.header_text}
        if variables_in(draft.header_text):
            header["example"] = {"header_text": [draft.header_example]}
        components.append(header)
    body: Dict[str, Any] = {"type": "BODY", "text": draft.body.strip()}
    if draft.body_examples:
        body["example"] = {"body_text": [draft.body_examples]}
    components.append(body)
    if draft.footer:
        components.append({"type": "FOOTER", "text": draft.footer})
    if draft.buttons:
        ordered = sorted(draft.buttons, key=lambda b: 0 if b.type == "QUICK_REPLY" else 1)
        buttons = []
        for b in ordered:
            entry: Dict[str, Any] = {"type": b.type, "text": b.text}
            if b.type == "URL":
                entry["url"] = b.url
            if b.type == "PHONE_NUMBER":
                entry["phone_number"] = b.phone_number.replace(" ", "")
            buttons.append(entry)
        components.append({"type": "BUTTONS", "buttons": buttons})
    return components


def stored_template(tenant_id: str, meta: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """What we keep of one template from Meta: enough to list it, fill it and preview it."""
    by_type = {c.get("type", "").upper(): c for c in meta.get("components") or []}
    header = by_type.get("HEADER") or {}
    header_text = header.get("text") if (header.get("format") or "TEXT").upper() == "TEXT" else None
    body_text = (by_type.get("BODY") or {}).get("text") or ""
    return {
        "tenant_id": tenant_id,
        "meta_id": meta.get("id"),
        "name": meta.get("name"),
        "language": meta.get("language"),
        "status": (meta.get("status") or "PENDING").upper(),
        "category": (meta.get("category") or "").upper(),
        "rejected_reason": meta.get("rejected_reason") if meta.get("rejected_reason") not in (None, "NONE") else None,
        "header_text": header_text,
        # A media header (image, video, document) needs a file at send time, which isn't supported yet.
        "header_format": (header.get("format") or "").upper() or None,
        "body_text": body_text,
        "footer_text": (by_type.get("FOOTER") or {}).get("text"),
        "buttons": (by_type.get("BUTTONS") or {}).get("buttons") or [],
        "body_variables": len(variables_in(body_text)),
        "header_variables": len(variables_in(header_text or "")),
        "components": meta.get("components") or [],
        "synced_at": now or datetime.now(timezone.utc),
    }


def public_template(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in ("_id", "components", "tenant_id")}


def sendable(doc: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Whether this template can be sent now, and why not."""
    if not doc:
        return False, "That template doesn't exist. Sync your templates and try again."
    if doc.get("status") != "APPROVED":
        return False, f"The template {doc.get('name')} isn't approved by Meta yet (it is {str(doc.get('status')).lower()})."
    if doc.get("header_format") not in (None, "TEXT"):
        return False, f"The template {doc.get('name')} has a picture or file header, which can't be sent from here yet."
    return True, ""


def clean_param(value: Any, fallback: str = "-") -> str:
    """Meta refuses parameters with new lines, tabs or more than four spaces in a row, and empty ones."""
    text = re.sub(r"[\r\n\t]+", " ", str(value if value is not None else ""))
    text = re.sub(r" {4,}", "   ", text).strip()
    return text[:1000] or fallback


def send_components(doc: Dict[str, Any], body_params: List[str], header_params: List[str]) -> List[Dict[str, Any]]:
    """The parameters for one send. Raises ValueError if the counts don't match the template."""
    if len(body_params) != doc.get("body_variables", 0):
        raise ValueError(f"The template {doc.get('name')} needs {doc.get('body_variables', 0)} value(s), got {len(body_params)}.")
    if len(header_params) != doc.get("header_variables", 0):
        raise ValueError(f"The template {doc.get('name')} header needs {doc.get('header_variables', 0)} value(s).")
    components: List[Dict[str, Any]] = []
    if header_params:
        components.append({"type": "header", "parameters": [{"type": "text", "text": clean_param(p)} for p in header_params]})
    if body_params:
        components.append({"type": "body", "parameters": [{"type": "text", "text": clean_param(p)} for p in body_params]})
    return components


def render(doc: Dict[str, Any], body_params: List[str], header_params: Optional[List[str]] = None) -> str:
    """The template as the customer reads it, for the inbox."""
    def fill(text: str, params: List[str]) -> str:
        return VARIABLE.sub(lambda m: clean_param(params[int(m.group(1)) - 1]) if int(m.group(1)) <= len(params) else m.group(0), text)

    parts = []
    if doc.get("header_text"):
        parts.append(f"*{fill(doc['header_text'], header_params or [])}*")
    parts.append(fill(doc.get("body_text") or "", body_params))
    if doc.get("footer_text"):
        parts.append(doc["footer_text"])
    buttons = [b.get("text") for b in doc.get("buttons") or [] if b.get("text")]
    if buttons:
        parts.append(" · ".join(f"[{b}]" for b in buttons))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Meta round trips
# ---------------------------------------------------------------------------
def account_of(tenant: Dict[str, Any]) -> Tuple[str, str]:
    """(token, waba_id) for the business's WhatsApp account. Raises ValueError if it isn't connected."""
    token, _ = resolve_tenant_whatsapp_credentials(tenant)
    waba_id = tenant.get("whatsapp_business_id")
    if not token or not waba_id:
        raise ValueError("Connect WhatsApp first. Templates live on your WhatsApp business account.")
    return token, waba_id


async def sync_templates(db, tenant: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Replaces our copy of the business's templates with what Meta has now."""
    token, waba_id = account_of(tenant)
    remote = await list_templates(token, waba_id)
    now = datetime.now(timezone.utc)
    docs = [stored_template(tenant["tenant_id"], t, now) for t in remote if t.get("name")]
    await db[TEMPLATES].delete_many({"tenant_id": tenant["tenant_id"]})
    if docs:
        await db[TEMPLATES].insert_many([dict(d) for d in docs])
    await db["tenants"].update_one({"tenant_id": tenant["tenant_id"]}, {"$set": {"templates_synced_at": now}})
    return docs


async def submit_template(db, tenant: Dict[str, Any], draft: TemplateDraft) -> Dict[str, Any]:
    """Sends a new template to Meta for review and keeps a copy. Raises ValueError with a reason the owner can read."""
    token, waba_id = account_of(tenant)
    components = build_components(draft)
    created = await create_template(
        token, waba_id,
        {"name": draft.name, "language": draft.language, "category": draft.category, "components": components},
    )
    doc = stored_template(
        tenant["tenant_id"],
        {"id": created.get("id"), "name": draft.name, "language": draft.language, "status": created.get("status"),
         "category": created.get("category") or draft.category, "components": components},
    )
    await db[TEMPLATES].update_one(
        {"tenant_id": tenant["tenant_id"], "name": draft.name, "language": draft.language},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def remove_template(db, tenant: Dict[str, Any], name: str, language: str) -> None:
    token, waba_id = account_of(tenant)
    doc = await db[TEMPLATES].find_one({"tenant_id": tenant["tenant_id"], "name": name, "language": language})
    await delete_template(token, waba_id, name, (doc or {}).get("meta_id"))
    await db[TEMPLATES].delete_one({"tenant_id": tenant["tenant_id"], "name": name, "language": language})


async def apply_status_update(db, waba_id: Optional[str], value: Dict[str, Any]) -> bool:
    """Meta's webhook for a template's review result. Returns whether a stored template changed."""
    if not waba_id:
        return False
    tenant = await db["tenants"].find_one({"whatsapp_business_id": waba_id}, {"tenant_id": 1})
    if not tenant:
        return False
    event = (value.get("event") or "").upper()
    if not event:
        return False
    query: Dict[str, Any] = {"tenant_id": tenant["tenant_id"]}
    if value.get("message_template_id"):
        query["meta_id"] = str(value["message_template_id"])
    else:
        query["name"] = value.get("message_template_name")
        query["language"] = value.get("message_template_language")
    reason = value.get("reason")
    result = await db[TEMPLATES].update_one(
        query,
        {"$set": {
            "status": event,
            "rejected_reason": reason if reason not in (None, "NONE") else None,
            "synced_at": datetime.now(timezone.utc),
        }},
    )
    return bool(getattr(result, "matched_count", 0))


async def find_template(db, tenant_id: str, name: str, language: str) -> Optional[Dict[str, Any]]:
    return await db[TEMPLATES].find_one({"tenant_id": tenant_id, "name": name, "language": language})


async def send_template_message(
    db,
    tenant: Dict[str, Any],
    to_phone: str,
    doc: Dict[str, Any],
    body_params: List[str],
    header_params: Optional[List[str]] = None,
    sender: str = "human",
) -> Tuple[SendResult, Optional[Any]]:
    """Sends an approved template and records it in the customer's conversation, if they have one.
    Raises ValueError if the template can't be sent or the values don't fit it."""
    from services.message_service import message_service

    ok, why = sendable(doc)
    if not ok:
        raise ValueError(why)
    header_params = header_params or []
    components = send_components(doc, body_params, header_params)
    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)
    result = await send_template(to_phone, doc["name"], doc["language"], components, token=token, phone_number_id=phone_number_id)

    message = None
    conversation = await db["conversations"].find_one(
        {"tenant_id": tenant["tenant_id"], "customer_phone": to_phone}, {"conversation_id": 1}
    )
    if conversation:
        message = await message_service.persist_outbound(
            conversation_id=conversation["conversation_id"],
            tenant_id=tenant["tenant_id"],
            content=render(doc, body_params, header_params),
            message_type="template",
            sender=sender,
        )
        if message:
            await message_service.update_outbound_status(
                message_id=message.message_id,
                wamid=result.message_id or "",
                status="sent" if result.ok else "failed",
            )
    return result, message


def order_update_phrase(order: Dict[str, Any], new_status: str) -> Optional[str]:
    kind = order.get("order_type") or "delivery"
    table = BOOKING_PHRASES if kind == "booking" else ORDER_UPDATE_PHRASES if kind == "delivery" else HANDOVER_PHRASES
    return table.get(new_status)


def order_update_draft(language: str = "en") -> TemplateDraft:
    return TemplateDraft(
        name=ORDER_UPDATE_TEMPLATE,
        category="UTILITY",
        language=language,
        body=ORDER_UPDATE_BODY,
        body_examples=ORDER_UPDATE_EXAMPLES,
    )


async def order_update_template(db, tenant: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The template the business uses for order updates after 24 hours, if it has set one up."""
    chosen = ((tenant.get("template_settings") or {}).get("order_updates")) or {}
    if not chosen.get("name"):
        return None
    return await find_template(db, tenant["tenant_id"], chosen["name"], chosen.get("language") or "en")


async def ensure_template_indexes(db) -> None:
    await db[TEMPLATES].create_index(
        [("tenant_id", 1), ("name", 1), ("language", 1)], unique=True, name="uniq_tenant_template"
    )
    await db["messages"].create_index("wamid", sparse=True, name="messages_by_wamid")
