import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

from core.database import get_database
from repositories.inbox_repo import inbox_repo
from models.inbox import (
    Conversation,
    Message,
    MessagePreview,
    MediaInfo,
    AgentMeta,
)
from core.ws_events import WSEvent

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self):
        self._ws_manager = None

    @property
    def ws_manager(self):
        if self._ws_manager is None:
            from core.ws_inbox import ws_inbox_manager
            self._ws_manager = ws_inbox_manager
        return self._ws_manager

    # ================================================================
    # Inbound Message Processing (Customer -> Agent)
    # ================================================================

    async def persist_inbound(
        self,
        tenant_id: str,
        sender_phone: str,
        content: str,
        message_type: str = "text",
        media: Optional[MediaInfo] = None,
        wamid: Optional[str] = None,
        customer_name: str = "",
        customer_avatar: Optional[str] = None,
    ) -> Optional[Message]:
        """Persist inbound customer message and broadcast to owner dashboard."""
        try:
            # 1. Upsert conversation
            conversation = await inbox_repo.upsert_conversation(
                tenant_id=tenant_id,
                customer_phone=sender_phone,
                customer_name=customer_name,
            )

            # 2. Create message
            message = await inbox_repo.create_message(
                conversation_id=conversation.conversation_id,
                tenant_id=tenant_id,
                sender="customer",
                sender_phone=sender_phone,
                content=content,
                message_type=message_type,
                media=media,
                status="received",
                wamid=wamid,
            )

            # 3. Update conversation with last message and increment unread
            last_message_preview = MessagePreview(
                content=content[:100],
                sender="customer",
                timestamp=message.created_at,
                type=message_type,
            )
            await inbox_repo.update_conversation_last_message(
                conversation_id=conversation.conversation_id,
                tenant_id=tenant_id,
                last_message=last_message_preview,
                increment_unread=True,
            )

            # 4. Broadcast to owner dashboard
            await self._broadcast_message_new(tenant_id, conversation, message)

            logger.info(f"Persisted inbound message {message.message_id} for tenant {tenant_id}")
            return message

        except Exception as e:
            logger.exception(f"Failed to persist inbound message: {e}")
            return None

    # ================================================================
    # Outbound Message Processing (Agent/Owner -> Customer)
    # ================================================================

    async def persist_outbound(
        self,
        conversation_id: str,
        tenant_id: str,
        content: str,
        message_type: str = "text",
        media: Optional[MediaInfo] = None,
        sender: str = "agent",
        agent_metadata: Optional[AgentMeta] = None,
    ) -> Optional[Message]:
        """Create outbound message with 'sending' status. Call update_outbound_status after WhatsApp API call."""
        try:
            message = await inbox_repo.create_message(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                sender=sender,
                content=content,
                message_type=message_type,
                status="sending",
            )

            # Update conversation with last message (don't increment unread for outbound)
            last_message_preview = MessagePreview(
                content=content[:100],
                sender=sender,
                timestamp=datetime.now(timezone.utc),
                type=message_type,
            )
            await inbox_repo.update_conversation_last_message(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                last_message=last_message_preview,
                increment_unread=False,
            )

            # Broadcast to owner dashboard (optimistic)
            conversation = await inbox_repo.get_conversation(conversation_id)
            if conversation:
                await self._broadcast_message_new(tenant_id, conversation, message)

            logger.info(f"Created outbound message {message.message_id} for tenant {tenant_id}")
            return message

        except Exception as e:
            logger.exception(f"Failed to create outbound message: {e}")
            return None

    async def update_outbound_status(
        self,
        message_id: str,
        wamid: str,
        status: str = "sent",
    ) -> Optional[Message]:
        """Update message status after WhatsApp API response."""
        message = await inbox_repo.update_message_status(
            message_id=message_id,
            status=status,
            wamid=wamid,
        )
        if message:
            await self._broadcast_message_status(message)
        return message

    async def update_outbound_status_by_wamid(
        self,
        wamid: str,
        status: str,
    ) -> Optional[Message]:
        """Update message status using WhatsApp message ID (from status webhook)."""
        message = await inbox_repo.update_message_status_by_wamid(
            wamid=wamid,
            status=status,
        )
        if message:
            await self._broadcast_message_status(message)
        return message

    # ================================================================
    # Status Webhook Handling
    # ================================================================

    async def handle_status_webhook(
        self,
        wamid: str,
        status: str,
        timestamp: Optional[int] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> Optional[Message]:
        """Handle WhatsApp status webhook (delivered/read/failed)."""
        try:
            message = await inbox_repo.update_message_status_by_wamid(
                wamid=wamid,
                status=status,
                delivered_at=datetime.fromtimestamp(timestamp, timezone.utc) if timestamp and status == "delivered" else None,
                read_at=datetime.fromtimestamp(timestamp, timezone.utc) if timestamp and status == "read" else None,
            )

            if message:
                await self._broadcast_message_status(message)

                # If read, also broadcast read event
                if status == "read":
                    await self._broadcast_message_read(message)

            if error and status == "failed":
                logger.warning(f"Message {wamid} failed: {error}")

            return message

        except Exception as e:
            logger.exception(f"Failed to handle status webhook for {wamid}: {e}")
            return None

    # ================================================================
    # Read Receipts
    # ================================================================

    async def mark_message_read(self, message_id: str, tenant_id: str) -> bool:
        """Mark a single message as read and broadcast to all owner tabs."""
        try:
            message = await inbox_repo.mark_message_read(message_id)
            if not message:
                return False

            # Broadcast read event to ALL owner connections (other tabs)
            await self._broadcast_message_read(message, read_by="owner")

            # Update unread count
            conversation = await inbox_repo.get_conversation(message.conversation_id)
            if conversation:
                await self._broadcast_unread_count(conversation.tenant_id)

            return True

        except Exception as e:
            logger.exception(f"Failed to mark message read: {e}")
            return False

    async def mark_conversation_read(self, conversation_id: str, tenant_id: str) -> int:
        """Mark all unread messages in conversation as read."""
        count = await inbox_repo.mark_conversation_read(conversation_id)
        if count > 0:
            await inbox_repo.set_unread_count(tenant_id, conversation_id, 0)
            await self._broadcast_unread_count(tenant_id)
        return count

    # ================================================================
    # WebSocket Broadcasting
    # ================================================================

    async def _broadcast_message_new(self, tenant_id: str, conversation: Conversation, message: Message):
        """Broadcast new message to all owner connections."""
        try:
            event = WSEvent(
                type="message.new",
                payload={
                    "conversation_id": conversation.conversation_id,
                    "message": self._message_to_dict(message),
                    "conversation": self._conversation_to_list_dict(conversation),
                }
            )
            await self.ws_manager.broadcast_to_tenant(tenant_id, event)
        except Exception as e:
            logger.warning(f"Failed to broadcast message.new: {e}")

    async def _broadcast_message_status(self, message: Message):
        """Broadcast message status update (sent/delivered/read/failed)."""
        try:
            event = WSEvent(
                type="message.status",
                payload={
                    "message_id": message.message_id,
                    "conversation_id": message.conversation_id,
                    "status": message.status,
                    "timestamp": message.updated_at.isoformat() if hasattr(message, "updated_at") else datetime.now(timezone.utc).isoformat(),
                }
            )
            await self.ws_manager.broadcast_to_tenant(message.tenant_id, event)
        except Exception as e:
            logger.warning(f"Failed to broadcast message.status: {e}")

    async def _broadcast_message_read(self, message: Message, read_by: str = "owner"):
        """Broadcast read receipt to all owner connections."""
        try:
            event = WSEvent(
                type="message.read",
                payload={
                    "message_id": message.message_id,
                    "conversation_id": message.conversation_id,
                    "read_by": read_by,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            await self.ws_manager.broadcast_to_tenant(message.tenant_id, event)
        except Exception as e:
            logger.warning(f"Failed to broadcast message.read: {e}")

    async def _broadcast_unread_count(self, tenant_id: str):
        """Broadcast updated unread counts to all owner tabs."""
        try:
            unread_total = await inbox_repo.get_unread_total(tenant_id)
            unread_breakdown = await inbox_repo.get_unread_breakdown(tenant_id)

            event = WSEvent(
                type="unread.count",
                payload={
                    "total_unread": unread_total,
                    "conversations": [
                        {"conversation_id": item["conversation_id"], "unread": item["unread"]}
                        for item in unread_breakdown
                    ],
                }
            )
            await self.ws_manager.broadcast_to_tenant(tenant_id, event)
        except Exception as e:
            logger.warning(f"Failed to broadcast unread.count: {e}")

    # ================================================================
    # Helpers
    # ================================================================

    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        return {
            "message_id": message.message_id,
            "wamid": message.wamid,
            "conversation_id": message.conversation_id,
            "tenant_id": message.tenant_id,
            "sender": message.sender,
            "sender_phone": message.sender_phone,
            "content": message.content,
            "type": message.type,
            "media": {
                "url": message.media.url,
                "mime_type": message.media.mime_type,
                "filename": message.media.filename,
                "size": message.media.size,
                "caption": message.media.caption,
            } if message.media else None,
            "status": message.status,
            "agent_metadata": {
                "agent_type": message.agent_metadata.agent_type,
                "model": message.agent_metadata.model,
                "tokens_used": message.agent_metadata.tokens_used,
                "tools_called": message.agent_metadata.tools_called,
            } if message.agent_metadata else None,
            "created_at": message.created_at.isoformat(),
            "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
            "read_at": message.read_at.isoformat() if message.read_at else None,
        }

    def _conversation_to_list_dict(self, conversation: Conversation) -> Dict[str, Any]:
        return {
            "conversation_id": conversation.conversation_id,
            "tenant_id": conversation.tenant_id,
            "customer_phone": conversation.customer_phone,
            "customer_name": conversation.customer_name,
            "customer_avatar": conversation.customer_avatar,
            "status": conversation.status,
            "last_message": {
                "content": conversation.last_message.content,
                "sender": conversation.last_message.sender,
                "timestamp": conversation.last_message.timestamp.isoformat(),
                "type": conversation.last_message.type,
            } if conversation.last_message else None,
            "unread_count": conversation.unread_count,
            "tags": conversation.tags,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "last_activity_at": conversation.last_activity_at.isoformat(),
        }


message_service = MessageService()