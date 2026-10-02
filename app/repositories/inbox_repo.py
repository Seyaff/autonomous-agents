from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from core.database import get_database
from models.inbox import (
    Conversation,
    Message,
    ConversationParticipant,
    PushSubscription,
    MediaInfo,
    AgentMeta,
    MessagePreview,
)


class InboxRepository:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db

    async def ensure_indexes(self):
        """Create all required indexes for inbox collections."""
        # Conversations indexes
        await self.db.conversations.create_index(
            [("tenant_id", 1), ("customer_phone", 1)],
            unique=True,
            name="tenant_phone_unique"
        )
        await self.db.conversations.create_index(
            [("tenant_id", 1), ("updated_at", -1)],
            name="tenant_updated_desc"
        )
        await self.db.conversations.create_index(
            [("tenant_id", 1), ("status", 1), ("last_activity_at", -1)],
            name="tenant_status_activity"
        )

        # Messages indexes
        await self.db.messages.create_index(
            [("conversation_id", 1), ("created_at", 1)],
            name="conv_created_asc"
        )
        await self.db.messages.create_index(
            [("wamid", 1)],
            unique=True,
            sparse=True,
            name="wamid_unique"
        )
        await self.db.messages.create_index(
            [("tenant_id", 1), ("created_at", -1)],
            name="tenant_created_desc"
        )

        # Participants indexes (with TTL for typing)
        await self.db.conversation_participants.create_index(
            [("conversation_id", 1), ("participant_type", 1)],
            name="conv_participant_type"
        )
        await self.db.conversation_participants.create_index(
            [("updated_at", 1)],
            expireAfterSeconds=30,
            name="participant_typing_ttl"
        )

        # Push subscriptions
        await self.db.push_subscriptions.create_index(
            [("user_id", 1), ("tenant_id", 1)],
            name="user_tenant"
        )

    # ================================================================
    # Conversation Operations
    # ================================================================

    async def upsert_conversation(
        self,
        tenant_id: str,
        customer_phone: str,
        customer_name: str = "",
        customer_avatar: Optional[str] = None,
    ) -> Conversation:
        """Create or get existing conversation for tenant + customer."""
        conversation_id = f"conv_{tenant_id}_{customer_phone}"
        now = datetime.now(timezone.utc)

        conv_doc = await self.db.conversations.find_one_and_update(
            {"conversation_id": conversation_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "tenant_id": tenant_id,
                    "customer_phone": customer_phone,
                    "customer_name": customer_name,
                    "customer_avatar": customer_avatar,
                    "status": "open",
                    "unread_count": 0,
                    "tags": [],
                    "created_at": now,
                    "updated_at": now,
                    "last_activity_at": now,
                },
                "$set": {
                    "customer_name": customer_name or "",
                    "customer_avatar": customer_avatar,
                    "updated_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )

        if conv_doc:
            conv_doc.pop("_id", None)
            return Conversation(**conv_doc)

        # Fallback: fetch the created document
        conv_doc = await self.db.conversations.find_one({"conversation_id": conversation_id})
        conv_doc.pop("_id", None)
        return Conversation(**conv_doc)

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        doc = await self.db.conversations.find_one({"conversation_id": conversation_id})
        if doc:
            doc.pop("_id", None)
            return Conversation(**doc)
        return None

    async def get_conversation_by_phone(self, tenant_id: str, customer_phone: str) -> Optional[Conversation]:
        conversation_id = f"conv_{tenant_id}_{customer_phone}"
        return await self.get_conversation(conversation_id)

    async def list_conversations(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        sort: str = "last_activity_at",
    ) -> Dict[str, Any]:
        query = {"tenant_id": tenant_id}
        if status:
            query["status"] = status

        if search:
            query["$or"] = [
                {"customer_name": {"$regex": search, "$options": "i"}},
                {"customer_phone": {"$regex": search, "$options": "i"}},
            ]

        sort_field = sort if sort in ["last_activity_at", "created_at", "unread_count"] else "last_activity_at"
        sort_order = DESCENDING if sort_field in ["last_activity_at", "created_at"] else ASCENDING

        total = await self.db.conversations.count_documents(query)
        cursor = self.db.conversations.find(query).sort(sort_field, sort_order).skip((page - 1) * limit).limit(limit)

        conversations = []
        async for doc in cursor:
            doc.pop("_id", None)
            conversations.append(Conversation(**doc))

        # Get total unread count
        unread_pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": None, "total": {"$sum": "$unread_count"}}}
        ]
        unread_result = await self.db.conversations.aggregate(unread_pipeline).to_list(1)
        unread_total = unread_result[0]["total"] if unread_result else 0

        return {
            "conversations": conversations,
            "total": total,
            "page": page,
            "limit": limit,
            "unread_total": unread_total,
        }

    async def update_conversation(
        self,
        conversation_id: str,
        tenant_id: str,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Conversation]:
        update_doc = {"updated_at": datetime.now(timezone.utc)}
        if status:
            update_doc["status"] = status
        if tags is not None:
            update_doc["tags"] = tags

        doc = await self.db.conversations.find_one_and_update(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {"$set": update_doc},
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Conversation(**doc)
        return None

    async def update_conversation_last_message(
        self,
        conversation_id: str,
        tenant_id: str,
        last_message: MessagePreview,
        increment_unread: bool = True,
    ) -> Optional[Conversation]:
        now = datetime.now(timezone.utc)
        update_doc = {
            "$set": {
                "last_message": last_message.model_dump(),
                "updated_at": now,
                "last_activity_at": now,
            }
        }
        if increment_unread:
            update_doc["$inc"] = {"unread_count": 1}

        doc = await self.db.conversations.find_one_and_update(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            update_doc,
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Conversation(**doc)
        return None

    async def decrement_unread(self, tenant_id: str, conversation_id: str, amount: int = 1) -> Optional[Conversation]:
        doc = await self.db.conversations.find_one_and_update(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {
                "$inc": {"unread_count": -amount},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Conversation(**doc)
        return None

    async def set_unread_count(self, tenant_id: str, conversation_id: str, count: int) -> Optional[Conversation]:
        doc = await self.db.conversations.find_one_and_update(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {
                "$set": {"unread_count": max(0, count), "updated_at": datetime.now(timezone.utc)},
            },
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Conversation(**doc)
        return None

    async def archive_conversation(self, tenant_id: str, conversation_id: str) -> bool:
        result = await self.db.conversations.update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    # ================================================================
    # Message Operations
    # ================================================================

    async def create_message(
        self,
        conversation_id: str,
        tenant_id: str,
        sender: str,
        content: str,
        message_type: str = "text",
        media: Optional[MediaInfo] = None,
        sender_phone: Optional[str] = None,
        status: str = "sending",
        wamid: Optional[str] = None,
        agent_metadata: Optional[AgentMeta] = None,
    ) -> Message:
        import uuid
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        msg = Message(
            message_id=message_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            sender=sender,
            sender_phone=sender_phone,
            content=content,
            type=message_type,
            media=media,
            status=status,
            wamid=wamid,
            agent_metadata=agent_metadata,
            created_at=now,
        )

        msg_doc = msg.model_dump(by_alias=True, exclude={"id"})
        await self.db.messages.insert_one(msg_doc)
        return msg

    async def get_message(self, message_id: str) -> Optional[Message]:
        doc = await self.db.messages.find_one({"message_id": message_id})
        if doc:
            doc.pop("_id", None)
            return Message(**doc)
        return None

    async def get_message_by_wamid(self, wamid: str) -> Optional[Message]:
        doc = await self.db.messages.find_one({"wamid": wamid})
        if doc:
            doc.pop("_id", None)
            return Message(**doc)
        return None

    async def get_messages(
        self,
        conversation_id: str,
        before_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Message]:
        query = {"conversation_id": conversation_id}
        if before_id:
            before_msg = await self.get_message(before_id)
            if before_msg:
                query["created_at"] = {"$lt": before_msg.created_at}

        cursor = self.db.messages.find(query).sort("created_at", DESCENDING).limit(limit)
        messages = []
        async for doc in cursor:
            doc.pop("_id", None)
            messages.append(Message(**doc))
        return list(reversed(messages))  # Return in chronological order

    async def get_messages_paginated(
        self,
        conversation_id: str,
        before_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        messages = await self.get_messages(conversation_id, before_id, limit + 1)
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        return {"messages": messages, "has_more": has_more}

    async def update_message_status(
        self,
        message_id: str,
        status: str,
        wamid: Optional[str] = None,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
    ) -> Optional[Message]:
        update_doc = {"status": status}
        if wamid:
            update_doc["wamid"] = wamid
        if delivered_at:
            update_doc["delivered_at"] = delivered_at
        if read_at:
            update_doc["read_at"] = read_at

        doc = await self.db.messages.find_one_and_update(
            {"message_id": message_id},
            {"$set": update_doc},
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Message(**doc)
        return None

    async def update_message_status_by_wamid(
        self,
        wamid: str,
        status: str,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
    ) -> Optional[Message]:
        update_doc = {"status": status}
        if delivered_at:
            update_doc["delivered_at"] = delivered_at
        if read_at:
            update_doc["read_at"] = read_at

        doc = await self.db.messages.find_one_and_update(
            {"wamid": wamid},
            {"$set": update_doc},
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Message(**doc)
        return None

    async def mark_message_read(self, message_id: str) -> Optional[Message]:
        now = datetime.now(timezone.utc)
        doc = await self.db.messages.find_one_and_update(
            {"message_id": message_id, "read_at": {"$exists": False}},
            {"$set": {"status": "read", "read_at": now}},
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return Message(**doc)
        return None

    async def mark_conversation_read(self, conversation_id: str) -> int:
        """Mark all unread messages in conversation as read. Returns count of updated messages."""
        now = datetime.now(timezone.utc)
        result = await self.db.messages.update_many(
            {
                "conversation_id": conversation_id,
                "sender": "customer",
                "read_at": {"$exists": False},
            },
            {"$set": {"status": "read", "read_at": now}},
        )
        return result.modified_count

    # ================================================================
    # Participant Operations
    # ================================================================

    async def upsert_participant(
        self,
        conversation_id: str,
        tenant_id: str,
        participant_type: str,
        participant_id: str,
        participant_name: str,
        is_typing: bool = False,
    ) -> ConversationParticipant:
        now = datetime.now(timezone.utc)
        doc = await self.db.conversation_participants.find_one_and_update(
            {"conversation_id": conversation_id, "participant_id": participant_id},
            {
                "$set": {
                    "conversation_id": conversation_id,
                    "tenant_id": tenant_id,
                    "participant_type": participant_type,
                    "participant_id": participant_id,
                    "participant_name": participant_name,
                    "is_typing": is_typing,
                    "last_seen_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "tenant_id": tenant_id,
                },
            },
            upsert=True,
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return ConversationParticipant(**doc)
        return None

    async def set_typing(
        self,
        conversation_id: str,
        participant_id: str,
        is_typing: bool,
    ) -> bool:
        update_doc = {
            "is_typing": is_typing,
            "updated_at": datetime.now(timezone.utc),
        }
        if is_typing:
            update_doc["last_seen_at"] = datetime.now(timezone.utc)

        result = await self.db.conversation_participants.update_one(
            {"conversation_id": conversation_id, "participant_id": participant_id},
            {"$set": update_doc},
        )
        return result.modified_count > 0

    async def get_participants(self, conversation_id: str) -> List[Dict[str, Any]]:
        cursor = self.db.conversation_participants.find({"conversation_id": conversation_id})
        participants = []
        async for doc in cursor:
            doc.pop("_id", None)
            participants.append(doc)
        return participants

    # ================================================================
    # Push Subscription Operations
    # ================================================================

    async def save_push_subscription(
        self,
        user_id: str,
        tenant_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushSubscription:
        now = datetime.now(timezone.utc)
        doc = await self.db.push_subscriptions.find_one_and_update(
            {"user_id": user_id, "tenant_id": tenant_id, "endpoint": endpoint},
            {
                "$set": {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "endpoint": endpoint,
                    "p256dh": p256dh,
                    "auth": auth,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
            return_document=True,
        )
        if doc:
            doc.pop("_id", None)
            return PushSubscription(**doc)
        return None

    async def get_push_subscriptions(self, tenant_id: str, user_id: Optional[str] = None) -> List[PushSubscription]:
        query = {"tenant_id": tenant_id}
        if user_id:
            query["user_id"] = user_id
        cursor = self.db.push_subscriptions.find(query)
        subscriptions = []
        async for doc in cursor:
            doc.pop("_id", None)
            subscriptions.append(PushSubscription(**doc))
        return subscriptions

    async def delete_push_subscription(self, user_id: str, tenant_id: str, endpoint: str) -> bool:
        result = await self.db.push_subscriptions.delete_one(
            {"user_id": user_id, "tenant_id": tenant_id, "endpoint": endpoint}
        )
        return result.deleted_count > 0

    # ================================================================
    # Unread Count Operations
    # ================================================================

    async def increment_unread(self, tenant_id: str, conversation_id: str) -> bool:
        result = await self.db.conversations.update_one(
            {"conversation_id": conversation_id, "tenant_id": tenant_id},
            {"$inc": {"unread_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def get_unread_total(self, tenant_id: str) -> int:
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$group": {"_id": None, "total": {"$sum": "$unread_count"}}}
        ]
        result = await self.db.conversations.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0

    async def get_unread_breakdown(self, tenant_id: str) -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "unread_count": {"$gt": 0}}},
            {"$project": {"conversation_id": 1, "unread_count": 1}},
        ]
        cursor = self.db.conversations.aggregate(pipeline)
        result = []
        async for doc in cursor:
            result.append({"conversation_id": doc["conversation_id"], "unread": doc["unread_count"]})
        return result


# Global instance
inbox_repo = InboxRepository()