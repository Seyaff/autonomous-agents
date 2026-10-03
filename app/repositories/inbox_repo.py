import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from core.database import get_database
from models.inbox import Conversation, Message, MessagePreview, MediaInfo, AgentMeta
from services.conversation_state import GROUP_FILTERS, serialize_conversation

logger = logging.getLogger(__name__)

CONVERSATIONS = "conversations"
MESSAGES = "messages"


class InboxRepository:
    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    async def upsert_conversation(
        self,
        tenant_id: str,
        customer_phone: str,
        customer_name: str = "",
        customer_avatar: Optional[str] = None,
    ) -> Conversation:
        db = get_database()
        conversation_id = f"conv_{tenant_id}_{customer_phone}"
        now = datetime.now(timezone.utc)

        existing = await db[CONVERSATIONS].find_one({"conversation_id": conversation_id})
        if existing:
            update_fields: Dict[str, Any] = {"updated_at": now, "last_activity_at": now}
            if customer_name and not existing.get("customer_name"):
                update_fields["customer_name"] = customer_name
            if customer_avatar and not existing.get("customer_avatar"):
                update_fields["customer_avatar"] = customer_avatar
            await db[CONVERSATIONS].update_one(
                {"conversation_id": conversation_id}, {"$set": update_fields}
            )
            existing.update(update_fields)
            existing.pop("_id", None)
            return Conversation(**existing)

        doc = {
            "conversation_id": conversation_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "customer_avatar": customer_avatar,
            "status": "open",
            "last_message": None,
            "unread_count": 0,
            "tags": [],
            "created_at": now,
            "updated_at": now,
            "last_activity_at": now,
        }
        await db[CONVERSATIONS].insert_one(doc)
        doc.pop("_id", None)
        return Conversation(**doc)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        db = get_database()
        doc = await db[CONVERSATIONS].find_one({"conversation_id": conversation_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Conversation(**doc)

    async def update_conversation_last_message(
        self,
        conversation_id: str,
        tenant_id: str,
        last_message: MessagePreview,
        increment_unread: bool = False,
    ) -> None:
        db = get_database()
        now = datetime.now(timezone.utc)
        update: Dict[str, Any] = {
            "$set": {
                "last_message": last_message.model_dump(),
                "updated_at": now,
                "last_activity_at": now,
            }
        }
        if increment_unread:
            update["$inc"] = {"unread_count": 1}
        await db[CONVERSATIONS].update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id}, update
        )

    async def update_conversation(
        self, conversation_id: str, tenant_id: str, fields: Dict[str, Any]
    ) -> Optional[Conversation]:
        db = get_database()
        clean_fields = {k: v for k, v in fields.items() if v is not None}
        if clean_fields:
            clean_fields["updated_at"] = datetime.now(timezone.utc)
            await db[CONVERSATIONS].update_one(
                {"conversation_id": conversation_id, "tenant_id": tenant_id},
                {"$set": clean_fields},
            )
        return await self.get_conversation(conversation_id)

    async def set_unread_count(self, tenant_id: str, conversation_id: str, count: int) -> None:
        db = get_database()
        await db[CONVERSATIONS].update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {"$set": {"unread_count": count}},
        )

    async def get_unread_total(self, tenant_id: str) -> int:
        db = get_database()
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": None, "total": {"$sum": "$unread_count"}}},
        ]
        cursor = await db[CONVERSATIONS].aggregate(pipeline)
        results = await cursor.to_list(length=1)
        return int(results[0]["total"]) if results else 0

    async def get_unread_breakdown(self, tenant_id: str) -> List[Dict[str, Any]]:
        db = get_database()
        cursor = db[CONVERSATIONS].find(
            {"tenant_id": tenant_id, "unread_count": {"$gt": 0}},
            {"conversation_id": 1, "unread_count": 1},
        )
        docs = await cursor.to_list(length=200)
        return [
            {"conversation_id": d["conversation_id"], "unread": d["unread_count"]}
            for d in docs
        ]

    async def get_conversation_raw(self, conversation_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Raw conversation document (with ownership/escalation fields), serialized."""
        db = get_database()
        query: Dict[str, Any] = {"conversation_id": conversation_id}
        if tenant_id:
            query["tenant_id"] = tenant_id
        doc = await db[CONVERSATIONS].find_one(query)
        return serialize_conversation(doc)

    async def list_conversations(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        sort: str = "last_activity_at",
        group: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = get_database()
        base: Dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            base["status"] = status
        if search:
            base["$or"] = [
                {"customer_name": {"$regex": search, "$options": "i"}},
                {"customer_phone": {"$regex": search, "$options": "i"}},
            ]

        query = dict(base)
        if group:
            if group not in GROUP_FILTERS:
                raise ValueError(f"Unknown group: {group}")
            query = {"$and": [base, GROUP_FILTERS[group]]}

        skip = max(page - 1, 0) * limit
        cursor = db[CONVERSATIONS].find(query).sort(sort, -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        total = await db[CONVERSATIONS].count_documents(query)
        unread_total = await self.get_unread_total(tenant_id)

        group_counts = {}
        for g, f in GROUP_FILTERS.items():
            group_counts[g] = await db[CONVERSATIONS].count_documents({"$and": [base, f]})

        return {
            "conversations": [serialize_conversation(d) for d in docs],
            "total": total,
            "page": page,
            "limit": limit,
            "unread_total": unread_total,
            "group_counts": group_counts,
        }

    async def set_handover(
        self, conversation_id: str, tenant_id: str, handled_by: str, user_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Switch who answers the chat. Taking over (owner) stamps who and when;
        handing back (agent) clears it and resolves any active escalation."""
        db = get_database()
        now = datetime.now(timezone.utc)
        update: Dict[str, Any] = {
            "$set": {
                "handled_by": handled_by,
                "handed_over_at": now if handled_by == "owner" else None,
                "handed_over_by_user_id": user_id if handled_by == "owner" else None,
                "updated_at": now,
            }
        }
        if handled_by == "agent":
            update["$set"]["escalation.active"] = False
            update["$set"]["escalation.resolved_at"] = now
            update["$set"]["escalation.resolved_by"] = user_id
        await db[CONVERSATIONS].update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id}, update
        )
        return await self.get_conversation_raw(conversation_id, tenant_id)

    async def raise_escalation(
        self, conversation_id: str, tenant_id: str, reason: str, summary: str
    ) -> Optional[Dict[str, Any]]:
        db = get_database()
        now = datetime.now(timezone.utc)
        await db[CONVERSATIONS].update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {
                "$set": {
                    "escalation": {
                        "active": True,
                        "reason": reason,
                        "summary": summary,
                        "raised_at": now,
                        "resolved_at": None,
                        "resolved_by": None,
                    },
                    "updated_at": now,
                }
            },
        )
        return await self.get_conversation_raw(conversation_id, tenant_id)

    async def resolve_escalation(
        self, conversation_id: str, tenant_id: str, user_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        db = get_database()
        now = datetime.now(timezone.utc)
        await db[CONVERSATIONS].update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {
                "$set": {
                    "escalation.active": False,
                    "escalation.resolved_at": now,
                    "escalation.resolved_by": user_id,
                    "updated_at": now,
                }
            },
        )
        return await self.get_conversation_raw(conversation_id, tenant_id)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    async def create_message(
        self,
        conversation_id: str,
        tenant_id: str,
        sender: str,
        content: str,
        message_type: str = "text",
        sender_phone: Optional[str] = None,
        media: Optional[MediaInfo] = None,
        status: str = "sending",
        wamid: Optional[str] = None,
        agent_metadata: Optional[AgentMeta] = None,
    ) -> Message:
        db = get_database()
        now = datetime.now(timezone.utc)
        message_id = f"msg_{uuid.uuid4().hex[:12]}"

        doc = {
            "message_id": message_id,
            "wamid": wamid,
            "conversation_id": conversation_id,
            "tenant_id": tenant_id,
            "sender": sender,
            "sender_phone": sender_phone,
            "content": content,
            "type": message_type,
            "media": media.model_dump() if media else None,
            "status": status,
            "agent_metadata": agent_metadata.model_dump() if agent_metadata else None,
            "created_at": now,
            "delivered_at": None,
            "read_at": None,
        }
        await db[MESSAGES].insert_one(doc)
        doc.pop("_id", None)
        return Message(**doc)

    async def get_messages(
        self,
        conversation_id: str,
        before_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        db = get_database()
        query: Dict[str, Any] = {"conversation_id": conversation_id}

        if before_id:
            anchor = await db[MESSAGES].find_one({"message_id": before_id})
            if anchor:
                query["created_at"] = {"$lt": anchor["created_at"]}

        cursor = db[MESSAGES].find(query).sort("created_at", -1).limit(limit + 1)
        docs = await cursor.to_list(length=limit + 1)

        has_more = len(docs) > limit
        docs = docs[:limit]
        for d in docs:
            d.pop("_id", None)
        docs.reverse()  # oldest -> newest for the UI

        return {"messages": docs, "has_more": has_more}

    async def update_message_status(
        self, message_id: str, status: str, wamid: Optional[str] = None
    ) -> Optional[Message]:
        db = get_database()
        update: Dict[str, Any] = {"status": status}
        if wamid:
            update["wamid"] = wamid
        await db[MESSAGES].update_one({"message_id": message_id}, {"$set": update})
        doc = await db[MESSAGES].find_one({"message_id": message_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Message(**doc)

    async def update_message_status_by_wamid(
        self,
        wamid: str,
        status: str,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
    ) -> Optional[Message]:
        db = get_database()
        update: Dict[str, Any] = {"status": status}
        if delivered_at:
            update["delivered_at"] = delivered_at
        if read_at:
            update["read_at"] = read_at
        await db[MESSAGES].update_one({"wamid": wamid}, {"$set": update})
        doc = await db[MESSAGES].find_one({"wamid": wamid})
        if not doc:
            return None
        doc.pop("_id", None)
        return Message(**doc)

    async def mark_message_read(self, message_id: str) -> Optional[Message]:
        db = get_database()
        now = datetime.now(timezone.utc)
        await db[MESSAGES].update_one(
            {"message_id": message_id}, {"$set": {"status": "read", "read_at": now}}
        )
        doc = await db[MESSAGES].find_one({"message_id": message_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return Message(**doc)

    async def mark_conversation_read(self, conversation_id: str) -> int:
        db = get_database()
        now = datetime.now(timezone.utc)
        result = await db[MESSAGES].update_many(
            {
                "conversation_id": conversation_id,
                "sender": "customer",
                "status": {"$ne": "read"},
            },
            {"$set": {"status": "read", "read_at": now}},
        )
        return result.modified_count


inbox_repo = InboxRepository()
