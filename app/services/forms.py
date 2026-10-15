"""
Forms the owner builds, sent to customers as WhatsApp Flows.

The owner lays out screens and fields in the dashboard. That layout is turned into Meta's Flow
JSON here, uploaded and published on the business's WhatsApp account. The agent sends a form
when it fits the conversation, and the customer's answers come back through the webhook as a
message the agent carries on from.

These are static forms: everything they need is in the layout, and nothing calls back to our
server while the customer fills one in. Limits below follow Meta's component limits.
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

from core.whatsapp_utils import (
    SendResult,
    create_flow,
    flow_preview_url,
    publish_flow,
    resolve_tenant_whatsapp_credentials,
    retire_flow,
    send_flow,
    upload_flow_json,
)

logger = logging.getLogger(__name__)

FORMS = "wa_forms"
FORM_SENDS = "wa_form_sends"
FORM_RESPONSES = "wa_form_responses"

# The Flow JSON version the layout is written in. Global references to other screens'
# answers (${screen.X.form.y}) need 4.0 or later.
FLOW_JSON_VERSION = "7.0"

FieldKind = Literal["short_text", "long_text", "email", "phone", "number", "date", "dropdown", "choice", "checkboxes", "opt_in"]
OPTION_KINDS = {"dropdown", "choice", "checkboxes"}
# Meta's label limits differ by component.
LABEL_LIMIT = {"choice": 30, "checkboxes": 30, "date": 40, "opt_in": 120}
OPTION_LIMIT = {"dropdown": 200, "choice": 20, "checkboxes": 20}
INPUT_TYPES = {"short_text": "text", "email": "email", "phone": "phone", "number": "number"}

CATEGORIES = ["APPOINTMENT_BOOKING", "LEAD_GENERATION", "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "SIGN_UP", "OTHER"]
SCREEN_LETTERS = "ABCDEFGH"


class FormField(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    kind: FieldKind = "short_text"
    required: bool = True
    options: List[str] = Field(default_factory=list)
    helper: Optional[str] = Field(None, max_length=80)
    # Set from the label when the form is saved. Stable, so answers keep their keys.
    name: Optional[str] = None

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _limits(self) -> "FormField":
        limit = LABEL_LIMIT.get(self.kind, 20)
        if len(self.label) > limit:
            raise ValueError(f"\"{self.label}\" is too long for WhatsApp. Keep it to {limit} characters.")
        if self.kind in OPTION_KINDS:
            options = [o.strip() for o in self.options if o.strip()]
            if not options:
                raise ValueError(f"\"{self.label}\" needs at least one option.")
            if len(options) > OPTION_LIMIT[self.kind]:
                raise ValueError(f"\"{self.label}\" can have at most {OPTION_LIMIT[self.kind]} options.")
            if any(len(o) > 30 for o in options):
                raise ValueError(f"Options in \"{self.label}\" must be 30 characters or less.")
            if len({o.lower() for o in options}) != len(options):
                raise ValueError(f"\"{self.label}\" has the same option twice.")
            self.options = options
        else:
            self.options = []
        return self


class FormScreen(BaseModel):
    title: str = Field(min_length=1, max_length=30)
    intro: Optional[str] = Field(None, max_length=300)
    fields: List[FormField] = Field(min_length=1, max_length=10)


class FormDraft(BaseModel):
    """A form as the owner builds it."""

    name: str = Field(min_length=1, max_length=60)
    purpose: str = Field(min_length=5, max_length=300, description="When the agent should send it, in plain words.")
    body: str = Field("Please fill in this short form.", min_length=1, max_length=1024)
    cta: str = Field("Open form", min_length=1, max_length=20)
    submit_label: str = Field("Submit", min_length=1, max_length=35)
    category: Literal["APPOINTMENT_BOOKING", "LEAD_GENERATION", "CONTACT_US", "CUSTOMER_SUPPORT", "SURVEY", "SIGN_UP", "OTHER"] = "OTHER"
    screens: List[FormScreen] = Field(min_length=1, max_length=len(SCREEN_LETTERS))

    @model_validator(mode="after")
    def _names(self) -> "FormDraft":
        assign_field_names(self)
        return self


def _slug(label: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "answer"
    return f"f_{name}" if name[0].isdigit() else name


def assign_field_names(draft: FormDraft) -> None:
    """Every field gets a unique name made from its label. A name already set is kept."""
    taken: set = set()
    for screen in draft.screens:
        for f in screen.fields:
            base = f.name if f.name and re.fullmatch(r"[a-z][a-z0-9_]{0,59}", f.name) else _slug(f.label)
            name, n = base, 2
            while name in taken:
                name, n = f"{base}_{n}", n + 1
            f.name = name
            taken.add(name)


def screen_id(index: int) -> str:
    """Meta's screen ids are letters and underscores."""
    return f"STEP_{SCREEN_LETTERS[index]}"


def option_id(index: int) -> str:
    return f"opt_{index}"


def _component(f: FormField) -> Dict[str, Any]:
    if f.kind in INPUT_TYPES:
        c: Dict[str, Any] = {"type": "TextInput", "name": f.name, "label": f.label, "input-type": INPUT_TYPES[f.kind], "required": f.required}
    elif f.kind == "long_text":
        c = {"type": "TextArea", "name": f.name, "label": f.label, "required": f.required}
    elif f.kind == "date":
        c = {"type": "DatePicker", "name": f.name, "label": f.label, "required": f.required}
    elif f.kind == "opt_in":
        return {"type": "OptIn", "name": f.name, "label": f.label, "required": f.required}
    else:
        component = {"dropdown": "Dropdown", "choice": "RadioButtonsGroup", "checkboxes": "CheckboxGroup"}[f.kind]
        c = {
            "type": component,
            "name": f.name,
            "label": f.label,
            "required": f.required,
            "data-source": [{"id": option_id(i), "title": o} for i, o in enumerate(f.options)],
        }
    if f.helper and c["type"] in ("TextInput", "TextArea", "DatePicker"):
        c["helper-text"] = f.helper
    return c


def build_flow_json(draft: FormDraft) -> Dict[str, Any]:
    """The form as Meta's Flow JSON. Each screen but the last has a Continue button; the last one
    sends every answer, from every screen, back to the business."""
    screens = []
    last = len(draft.screens) - 1
    for i, screen in enumerate(draft.screens):
        children: List[Dict[str, Any]] = []
        if screen.intro:
            children.append({"type": "TextBody", "text": screen.intro})
        children.extend(_component(f) for f in screen.fields)
        if i < last:
            action = {"name": "navigate", "next": {"type": "screen", "name": screen_id(i + 1)}, "payload": {}}
            label = "Continue"
        else:
            payload = {}
            for j, earlier in enumerate(draft.screens):
                for f in earlier.fields:
                    payload[f.name] = f"${{form.{f.name}}}" if j == last else f"${{screen.{screen_id(j)}.form.{f.name}}}"
            action = {"name": "complete", "payload": payload}
            label = draft.submit_label
        children.append({"type": "Footer", "label": label, "on-click-action": action})
        entry: Dict[str, Any] = {
            "id": screen_id(i),
            "title": screen.title,
            "layout": {"type": "SingleColumnLayout", "children": children},
        }
        if i == last:
            entry["terminal"] = True
            entry["success"] = True
        screens.append(entry)
    return {"version": FLOW_JSON_VERSION, "screens": screens}


def layout_hash(draft: FormDraft) -> str:
    return hashlib.sha256(json.dumps(build_flow_json(draft), sort_keys=True).encode()).hexdigest()[:16]


def draft_of(doc: Dict[str, Any]) -> FormDraft:
    return FormDraft(**{k: doc[k] for k in FormDraft.model_fields if k in doc})


def public_form(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in ("_id", "tenant_id")}


# ---------------------------------------------------------------------------
# Saving and publishing
# ---------------------------------------------------------------------------
async def save_form(db, tenant_id: str, draft: FormDraft, form_id: Optional[str] = None) -> Dict[str, Any]:
    """Saves the layout. A form that was published keeps working as it was until it's published again."""
    now = datetime.now(timezone.utc)
    fields = {**draft.model_dump(), "updated_at": now, "layout_hash": layout_hash(draft)}
    if form_id:
        existing = await db[FORMS].find_one({"tenant_id": tenant_id, "form_id": form_id})
        if not existing:
            raise LookupError("Form not found.")
        # The message and button text go with each send, so only the layout needs publishing again.
        fields["has_unpublished_changes"] = (
            existing.get("meta_status") == "PUBLISHED" and existing.get("published_hash") != fields["layout_hash"]
        )
        await db[FORMS].update_one({"tenant_id": tenant_id, "form_id": form_id}, {"$set": fields})
        return {**existing, **fields}
    doc = {
        **fields,
        "tenant_id": tenant_id,
        "form_id": f"form_{uuid.uuid4().hex[:10]}",
        "status": "draft",
        "meta_flow_id": None,
        "meta_status": None,
        "version": 0,
        "validation_errors": [],
        "published_hash": None,
        "published_at": None,
        "has_unpublished_changes": False,
        "responses": 0,
        "created_at": now,
    }
    await db[FORMS].insert_one(dict(doc))
    return doc


def _account(tenant: Dict[str, Any]) -> Tuple[str, str]:
    token, _ = resolve_tenant_whatsapp_credentials(tenant)
    waba_id = tenant.get("whatsapp_business_id")
    if not token or not waba_id:
        raise ValueError("Connect WhatsApp first. Forms are published on your WhatsApp business account.")
    return token, waba_id


async def publish_form(db, tenant: Dict[str, Any], form_id: str) -> Dict[str, Any]:
    """Uploads the layout to Meta and publishes it. A published Flow can't change, so publishing
    after an edit makes a new Flow and retires the old one once the new one is live.
    Raises ValueError with what went wrong, including Meta's validation errors."""
    tenant_id = tenant["tenant_id"]
    doc = await db[FORMS].find_one({"tenant_id": tenant_id, "form_id": form_id})
    if not doc:
        raise LookupError("Form not found.")
    token, waba_id = _account(tenant)
    draft = draft_of(doc)
    flow_json = json.dumps(build_flow_json(draft))
    now = datetime.now(timezone.utc)

    old_flow = doc.get("meta_flow_id")
    old_published = doc.get("meta_status") == "PUBLISHED"
    if old_published and not doc.get("has_unpublished_changes"):
        return doc  # nothing new to publish

    # A draft Flow on Meta is reused until it publishes: the form's own draft before its first
    # publish, or the pending draft of an edit to a published form.
    if old_published:
        flow_id = doc.get("pending_flow_id")
        version = int(doc.get("pending_version") or (int(doc.get("version") or 0) + 1))
    else:
        flow_id = old_flow
        version = int(doc.get("version") or 0) or 1
    if not flow_id:
        flow_id = await create_flow(token, waba_id, f"{draft.name} v{version}", [draft.category])

    errors = await upload_flow_json(token, flow_id, flow_json)
    if errors:
        # A failed edit leaves the published version working; the draft waits for the next try.
        where = {"pending_flow_id": flow_id, "pending_version": version} if old_published else {
            "meta_flow_id": flow_id, "meta_status": "DRAFT", "version": version}
        await db[FORMS].update_one({"form_id": form_id}, {"$set": {
            "status": "published" if old_published else "error",
            "validation_errors": errors,
            "updated_at": now,
            **where,
        }})
        raise ValueError("WhatsApp found problems with the form: " + "; ".join(errors[:3]))
    await publish_flow(token, flow_id)
    if old_published and old_flow and old_flow != flow_id:
        await retire_flow(token, old_flow, published=True)

    fields = {
        "status": "published",
        "meta_flow_id": flow_id,
        "meta_status": "PUBLISHED",
        "version": version,
        "validation_errors": [],
        "published_hash": doc.get("layout_hash") or layout_hash(draft),
        "published_layout": draft.model_dump()["screens"],
        "published_at": now,
        "has_unpublished_changes": False,
        "updated_at": now,
    }
    await db[FORMS].update_one({"form_id": form_id}, {"$set": fields, "$unset": {"pending_flow_id": "", "pending_version": ""}})
    return {**doc, **fields}


async def delete_form(db, tenant: Dict[str, Any], form_id: str) -> None:
    doc = await db[FORMS].find_one({"tenant_id": tenant["tenant_id"], "form_id": form_id})
    if not doc:
        raise LookupError("Form not found.")
    token, _ = resolve_tenant_whatsapp_credentials(tenant)
    if token:
        for flow_id, published in ((doc.get("meta_flow_id"), doc.get("meta_status") == "PUBLISHED"), (doc.get("pending_flow_id"), False)):
            if flow_id:
                await retire_flow(token, flow_id, published=published)
    await db[FORMS].delete_one({"tenant_id": tenant["tenant_id"], "form_id": form_id})


async def preview_link(tenant: Dict[str, Any], doc: Dict[str, Any]) -> Optional[str]:
    token, _ = resolve_tenant_whatsapp_credentials(tenant)
    flow_id = doc.get("pending_flow_id") or doc.get("meta_flow_id")
    if not token or not flow_id:
        return None
    return await flow_preview_url(token, flow_id)


# ---------------------------------------------------------------------------
# Sending, and the customer's answers
# ---------------------------------------------------------------------------
async def published_forms(db, tenant_id: str) -> List[Dict[str, Any]]:
    return await db[FORMS].find(
        {"tenant_id": tenant_id, "meta_status": "PUBLISHED"}, {"_id": 0, "form_id": 1, "name": 1, "purpose": 1}
    ).to_list(length=50)


async def find_published(db, tenant_id: str, name_or_id: str) -> Optional[Dict[str, Any]]:
    wanted = (name_or_id or "").strip().lower()
    for doc in await db[FORMS].find({"tenant_id": tenant_id, "meta_status": "PUBLISHED"}).to_list(length=50):
        if wanted in (doc["form_id"].lower(), doc["name"].strip().lower()):
            return doc
    return None


async def send_form_to(db, tenant: Dict[str, Any], phone: str, doc: Dict[str, Any], body: Optional[str] = None) -> SendResult:
    """Sends a published form and remembers which form went to whom, so the answers can be read back."""
    token, phone_number_id = resolve_tenant_whatsapp_credentials(tenant)
    flow_token = f"{doc['form_id']}.{uuid.uuid4().hex[:12]}"
    result = await send_flow(
        to_phone=phone,
        flow_id=doc["meta_flow_id"],
        flow_token=flow_token,
        first_screen=screen_id(0),
        body=body or doc.get("body") or "Please fill in this short form.",
        cta=doc.get("cta") or "Open form",
        token=token,
        phone_number_id=phone_number_id,
    )
    if result.ok:
        await db[FORM_SENDS].insert_one({
            "flow_token": flow_token,
            "tenant_id": tenant["tenant_id"],
            "form_id": doc["form_id"],
            "customer_phone": phone,
            "wamid": result.message_id,
            "layout": doc.get("published_layout") or doc.get("screens"),
            "sent_at": datetime.now(timezone.utc),
        })
    return result


def readable_answers(layout: List[Dict[str, Any]], raw: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(label, answer) for each field in the layout the customer saw. Option ids become their titles."""
    out: List[Tuple[str, str]] = []
    for screen in layout or []:
        for f in screen.get("fields") or []:
            name = f.get("name")
            if not name or name not in raw:
                continue
            value = raw[name]
            options = f.get("options") or []

            def title(v: Any) -> str:
                m = re.fullmatch(r"opt_(\d+)", str(v))
                return options[int(m.group(1))] if m and int(m.group(1)) < len(options) else str(v)

            if isinstance(value, list):
                text = ", ".join(title(v) for v in value)
            elif isinstance(value, bool):
                text = "Yes" if value else "No"
            elif f.get("kind") in OPTION_KINDS:
                text = title(value)
            else:
                text = str(value)
            if text.strip():
                out.append((f.get("label") or name, text.strip()))
    return out


async def record_response(db, tenant_id: str, phone: str, response_json: str, wamid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Saves a submitted form. Returns the saved response, or None if it isn't one of our forms."""
    try:
        raw = json.loads(response_json or "{}")
    except (TypeError, ValueError):
        logger.warning(f"Form reply from {phone} had unreadable answers")
        return None
    flow_token = raw.pop("flow_token", None)
    send = await db[FORM_SENDS].find_one({"flow_token": flow_token, "tenant_id": tenant_id}) if flow_token else None
    if not send:
        # Some clients drop the token. Fall back to the last form sent to this customer.
        send = await db[FORM_SENDS].find_one({"tenant_id": tenant_id, "customer_phone": phone}, sort=[("sent_at", -1)])
    if not send:
        return None
    form = await db[FORMS].find_one({"tenant_id": tenant_id, "form_id": send["form_id"]}) or {}
    answers = readable_answers(send.get("layout") or form.get("screens") or [], raw)
    doc = {
        "response_id": f"resp_{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "form_id": send["form_id"],
        "form_name": form.get("name") or "Form",
        "customer_phone": phone,
        "answers": [{"label": label, "value": value} for label, value in answers],
        "raw": raw,
        "wamid": wamid,
        "received_at": datetime.now(timezone.utc),
    }
    await db[FORM_RESPONSES].insert_one(dict(doc))
    await db[FORMS].update_one({"tenant_id": tenant_id, "form_id": send["form_id"]}, {"$inc": {"responses": 1}})
    return doc


def response_message(doc: Dict[str, Any]) -> str:
    """The submitted form as one message, for the inbox and for the agent."""
    lines = [f"[form submitted: {doc['form_name']}]"]
    lines.extend(f"{a['label']}: {a['value']}" for a in doc["answers"])
    if not doc["answers"]:
        lines.append("(no answers filled in)")
    return "\n".join(lines)


async def ensure_form_indexes(db) -> None:
    await db[FORMS].create_index([("tenant_id", 1), ("form_id", 1)], unique=True, name="uniq_tenant_form")
    await db[FORM_SENDS].create_index("flow_token", unique=True, name="uniq_flow_token")
    await db[FORM_SENDS].create_index([("tenant_id", 1), ("customer_phone", 1), ("sent_at", -1)], name="form_sends_by_customer")
    await db[FORM_RESPONSES].create_index([("tenant_id", 1), ("form_id", 1), ("received_at", -1)], name="form_responses_recent")
