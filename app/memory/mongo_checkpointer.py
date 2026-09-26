import logging
from typing import Any, AsyncIterator, Optional, Sequence
from bson.binary import Binary
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    PendingWrite,
    WRITES_IDX_MAP,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class MongoDBCkptSaver(BaseCheckpointSaver):
    """
    MongoDB-backed persistent checkpointer for LangGraph.
    Saves serialized checkpoints, blobs, and writes to MongoDB collections,
    ensuring full state recovery across restarts with zero in-memory volatility.
    """

    def __init__(self, db: Any):
        super().__init__()
        self.db = db
        self.checkpoints_col = self.db["langgraph_checkpoints"]
        self.blobs_col = self.db["langgraph_checkpoint_blobs"]
        self.writes_col = self.db["langgraph_checkpoint_writes"]
        self._indexes_created = False

    async def ensure_indexes(self):
        """Ensures compound indexes for fast thread lookup and ordering."""
        if self._indexes_created:
            return
        try:
            await self.checkpoints_col.create_index(
                [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", -1)]
            )
            await self.blobs_col.create_index(
                [("thread_id", 1), ("checkpoint_ns", 1), ("channel", 1), ("version", 1)],
                unique=True
            )
            await self.writes_col.create_index(
                [
                    ("thread_id", 1),
                    ("checkpoint_ns", 1),
                    ("checkpoint_id", 1),
                    ("task_id", 1),
                    ("idx", 1),
                ],
                unique=True
            )
            self._indexes_created = True
        except Exception as e:
            logger.warning(f"Could not create checkpointer indexes: {e}")

    async def _load_blobs(
        self, thread_id: str, checkpoint_ns: str, versions: ChannelVersions
    ) -> dict[str, Any]:
        """Loads and deserializes channel value blobs for given channel versions."""
        if not versions:
            return {}

        results: dict[str, Any] = {}
        for channel, version in versions.items():
            doc = await self.blobs_col.find_one({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "channel": channel,
                "version": str(version),
            })
            if doc and doc.get("blob_type") != "empty":
                type_str = doc.get("blob_type", "msgpack")
                raw_bytes = bytes(doc.get("blob_data", b""))
                results[channel] = self.serde.loads_typed((type_str, raw_bytes))

        return results

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Asynchronously retrieves a checkpoint tuple for the given thread_id."""
        await self.ensure_indexes()

        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        query = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id

        # Find requested or most recent checkpoint
        doc = await self.checkpoints_col.find_one(
            query,
            sort=[("checkpoint_id", -1)]
        )
        if not doc:
            return None

        chk_id = doc["checkpoint_id"]
        parent_id = doc.get("parent_checkpoint_id")

        checkpoint_raw = bytes(doc["checkpoint_data"])
        checkpoint_type = doc.get("checkpoint_type", "msgpack")
        checkpoint_: Checkpoint = self.serde.loads_typed((checkpoint_type, checkpoint_raw))

        metadata_raw = bytes(doc["metadata_data"])
        metadata_type = doc.get("metadata_type", "msgpack")
        metadata: CheckpointMetadata = self.serde.loads_typed((metadata_type, metadata_raw))

        # Load blobs
        channel_values = await self._load_blobs(
            thread_id, checkpoint_ns, checkpoint_["channel_versions"]
        )

        # Load pending writes
        writes_cursor = self.writes_col.find({
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": chk_id,
        })
        writes_docs = await writes_cursor.to_list(length=1000)
        pending_writes: list[PendingWrite] = []
        for w in writes_docs:
            w_type = w.get("type", "msgpack")
            w_val = self.serde.loads_typed((w_type, bytes(w["data"])))
            pending_writes.append((w["task_id"], w["channel"], w_val))

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": chk_id,
                }
            },
            checkpoint={
                **checkpoint_,
                "channel_values": channel_values,
            },
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_id,
                    }
                }
                if parent_id
                else None
            ),
            pending_writes=pending_writes,
        )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Asynchronously saves checkpoint and new channel blobs to MongoDB."""
        await self.ensure_indexes()

        c = checkpoint.copy()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        chk_id = checkpoint["id"]
        parent_id = config["configurable"].get("checkpoint_id")

        values: dict[str, Any] = c.pop("channel_values", {})

        # Store new channel blobs
        for k, v in new_versions.items():
            if k in values:
                b_type, b_bytes = self.serde.dumps_typed(values[k])
                blob_doc = {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": k,
                    "version": str(v),
                    "blob_type": b_type,
                    "blob_data": Binary(b_bytes),
                }
            else:
                blob_doc = {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": k,
                    "version": str(v),
                    "blob_type": "empty",
                    "blob_data": Binary(b""),
                }

            await self.blobs_col.update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": k,
                    "version": str(v),
                },
                {"$set": blob_doc},
                upsert=True,
            )

        # Store checkpoint document
        chk_type, chk_bytes = self.serde.dumps_typed(c)
        meta_type, meta_bytes = self.serde.dumps_typed(
            get_checkpoint_metadata(config, metadata)
        )

        chk_doc = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": chk_id,
            "parent_checkpoint_id": parent_id,
            "checkpoint_type": chk_type,
            "checkpoint_data": Binary(chk_bytes),
            "metadata_type": meta_type,
            "metadata_data": Binary(meta_bytes),
        }

        await self.checkpoints_col.update_one(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": chk_id,
            },
            {"$set": chk_doc},
            upsert=True,
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": chk_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Asynchronously saves task writes to MongoDB."""
        await self.ensure_indexes()

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            w_type, w_bytes = self.serde.dumps_typed(value)

            doc = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "idx": write_idx,
                "channel": channel,
                "type": w_type,
                "data": Binary(w_bytes),
                "task_path": task_path,
            }

            await self.writes_col.update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                    "task_id": task_id,
                    "idx": write_idx,
                },
                {"$set": doc},
                upsert=True,
            )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Asynchronously lists checkpoint tuples matching given criteria."""
        await self.ensure_indexes()

        query: dict[str, Any] = {}
        if config:
            query["thread_id"] = config["configurable"]["thread_id"]
            if "checkpoint_ns" in config["configurable"]:
                query["checkpoint_ns"] = config["configurable"]["checkpoint_ns"]
            if chk_id := get_checkpoint_id(config):
                query["checkpoint_id"] = chk_id

        if before and (before_id := get_checkpoint_id(before)):
            query["checkpoint_id"] = {"$lt": before_id}

        cursor = self.checkpoints_col.find(query).sort("checkpoint_id", -1)
        count = 0

        async for doc in cursor:
            if limit is not None and count >= limit:
                break

            meta_type = doc.get("metadata_type", "msgpack")
            metadata: CheckpointMetadata = self.serde.loads_typed(
                (meta_type, bytes(doc["metadata_data"]))
            )

            if filter and not all(
                metadata.get(k) == v for k, v in filter.items()
            ):
                continue

            thread_id = doc["thread_id"]
            checkpoint_ns = doc["checkpoint_ns"]
            chk_id = doc["checkpoint_id"]
            parent_id = doc.get("parent_checkpoint_id")

            chk_type = doc.get("checkpoint_type", "msgpack")
            checkpoint_: Checkpoint = self.serde.loads_typed(
                (chk_type, bytes(doc["checkpoint_data"]))
            )

            channel_values = await self._load_blobs(
                thread_id, checkpoint_ns, checkpoint_["channel_versions"]
            )

            writes_cursor = self.writes_col.find({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": chk_id,
            })
            writes_docs = await writes_cursor.to_list(length=1000)
            pending_writes: list[PendingWrite] = []
            for w in writes_docs:
                w_type = w.get("type", "msgpack")
                w_val = self.serde.loads_typed((w_type, bytes(w["data"])))
                pending_writes.append((w["task_id"], w["channel"], w_val))

            count += 1
            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": chk_id,
                    }
                },
                checkpoint={
                    **checkpoint_,
                    "channel_values": channel_values,
                },
                metadata=metadata,
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": parent_id,
                        }
                    }
                    if parent_id
                    else None
                ),
                pending_writes=pending_writes,
            )

    # Sync fallbacks raise informative error as this is an async-first platform
    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        raise NotImplementedError("Use async aget_tuple for MongoDBCkptSaver")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use async aput for MongoDBCkptSaver")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        raise NotImplementedError("Use async aput_writes for MongoDBCkptSaver")

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ):
        raise NotImplementedError("Use async alist for MongoDBCkptSaver")
