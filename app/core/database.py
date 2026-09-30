import os
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from .settings import settings


class MongoDB:
    client: AsyncMongoClient = None
    db = None


class RedisContainer:
    client: Redis = None
    checkpointer: AsyncRedisSaver = None


db_container = MongoDB()
redis_container = RedisContainer()


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
async def connect_to_mongo():
    mongo_uri = settings.MONGO_URI
    db_name = settings.DATABASE_NAME

    try:
        db_container.client = AsyncMongoClient(mongo_uri)
        await db_container.client.admin.command("ping")
        db_container.db = db_container.client[db_name]
        collection_list = await db_container.db.list_collection_names()
        print(f"collections : {collection_list}")
        print("Successfully connected to MongoDB.")
    except PyMongoError as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise e


async def close_mongo_connection():
    if db_container.client:
        await db_container.client.close()
        print("MongoDB connection closed.")


def get_database():
    if db_container.db is None:
        raise RuntimeError("Database is not initialized. Ensure app lifespan has run.")
    return db_container.db


async def ensure_webhook_indexes():
    db = db_container.db
    if db is None:
        raise RuntimeError("Database not connected.")

    await db["processed_messages"].create_index(
        "message_id", unique=True, name="uniq_message_id"
    )
    await db["processed_messages"].create_index(
        "received_at", expireAfterSeconds=7 * 24 * 3600, name="ttl_received_at"
    )
    
    await db["conversation_summaries"].create_index(
        [("tenant_id", 1), ("customer_phone", 1), ("created_at", -1)],
        name="tenant_phone_created_idx"
    )
    await db["conversation_summaries"].create_index(
        "thread_id", unique=True, name="uniq_thread_id"
    )
    
    print("[webhook] processed_messages indexes ensured.")
    print("[memory] conversation_summaries indexes ensured.")


async def verify_webhook_indexes():
    db = db_container.db
    info = await db["processed_messages"].index_information()

    has_unique = False
    for name, spec in info.items():
        keys = [k[0] for k in spec.get("key", [])]
        if "message_id" in keys and spec.get("unique"):
            has_unique = True
            break

    if has_unique:
        print("[webhook] ✅ unique index on processed_messages.message_id exists")
    else:
        print("[webhook] ❌ MISSING unique index on processed_messages.message_id "
              "— dedup will NOT work")
        print(f"[webhook] current indexes: {list(info.keys())}")

    return has_unique


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_module_name(raw) -> str:
    """Coerce a MODULE LIST entry's name field into a lowercase str."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode(errors="ignore").lower()
    return str(raw).lower()


def _extract_module_names(modules_raw) -> set[str]:
    """
    redis-py returns MODULE LIST in different shapes depending on version:
      - list of lists:  [[b'name', b'ReJSON', b'ver', 20810], ...]
      - list of dicts:  [{'name': 'ReJSON', 'ver': 20810}, ...]
      - list of tuples: [('name', 'ReJSON', 'ver', 20810), ...]
    This handles all three without ever indexing a missing key.
    """
    names: set[str] = set()
    for m in modules_raw or []:
        if isinstance(m, dict):
            names.add(_normalize_module_name(m.get("name")))
        elif isinstance(m, (list, tuple)) and len(m) >= 2:
            # name is conventionally the second element: ['name', 'ReJSON', ...]
            names.add(_normalize_module_name(m[1]))
    names.discard("")
    return names


# ---------------------------------------------------------------------------
# Redis + LangGraph master-graph checkpointer
# ---------------------------------------------------------------------------
async def connect_redis_database():
    redis_uri = (settings.REDIS_URI or "").strip()

    if not redis_uri:
        raise RuntimeError(
            "REDIS_URI is not set. Add it to .env (e.g. redis://localhost:6379)"
        )

    if not redis_uri.startswith(("redis://", "rediss://", "unix://")):
        raise RuntimeError(
            f"REDIS_URI must start with redis://, rediss://, or unix:// "
            f"(got: {redis_uri!r})"
        )

    # -------- Capability check: RediSearch + RedisJSON must exist --------
    probe = Redis.from_url(redis_uri, decode_responses=True)
    try:
        await probe.ping()
    except RedisError as e:
        await probe.aclose()
        raise RuntimeError(f"Cannot reach Redis at {redis_uri}: {e}")

    try:
        modules_raw = await probe.execute_command("MODULE", "LIST")
    except RedisError as e:
        await probe.aclose()
        raise RuntimeError(f"MODULE LIST failed — Redis too old? ({e})")

    # Debug line so you can see the real shape if anything goes wrong again
    # print(f"[redis] MODULE LIST raw = {modules_raw!r}")

    module_names = _extract_module_names(modules_raw)

    if "search" not in module_names or "rejson" not in module_names:
        await probe.aclose()
        raise RuntimeError(
            "Redis is missing required modules. LangGraph's checkpointer needs "
            "RediSearch + RedisJSON.\n"
            f"Detected modules: {sorted(module_names) or 'none'}\n"
            "Fix: use redis/redis-stack:latest (see docker-compose.yml)."
        )

    print(f"[redis] ✅ modules detected: {sorted(module_names)}")
    await probe.aclose()

    # -------- Real Redis client for general app use --------
    try:
        redis_container.client = Redis.from_url(redis_uri, decode_responses=True)
        await redis_container.client.ping()
        print(f"Successfully connected to Redis at {redis_uri}.")
    except RedisError as e:
        print(f"Failed to connect to Redis client: {e}")
        raise e

    # -------- LangGraph AsyncRedisSaver checkpointer --------
    # IMPORTANT: AsyncRedisSaver.from_conn_string() returns an async context
    # manager, NOT the saver itself. __aenter__() yields the real saver.
    try:
        checkpointer_cm = AsyncRedisSaver.from_conn_string(
            redis_uri,
            ttl={
                "default_ttl": 60 * 24 * 7,   # 7 days (minutes in this API)
                "refresh_on_read": True,
            },
        )
        redis_container.checkpointer = await checkpointer_cm.__aenter__()
        await redis_container.checkpointer.asetup()
        print("[checkpointer] ✅ AsyncRedisSaver initialized and indices ensured.")
    except Exception as e:
        print(f"Failed to initialize LangGraph Redis checkpointer: {e}")
        raise e


async def close_redis_connection():
    if redis_container.checkpointer:
        try:
            await redis_container.checkpointer.__aexit__(None, None, None)
            print("LangGraph Redis checkpointer closed.")
        except Exception as e:
            print(f"Error closing checkpointer: {e}")
        finally:
            redis_container.checkpointer = None

    if redis_container.client:
        try:
            await redis_container.client.aclose()
            print("Redis connection closed.")
        except Exception as e:
            print(f"Error closing Redis client: {e}")
        finally:
            redis_container.client = None



def get_redis():
    if redis_container.client is None:
        raise RuntimeError("Redis is not initialized. Ensure app lifespan has run.")
    return redis_container.client


def get_checkpointer() -> AsyncRedisSaver:
    if redis_container.checkpointer is None:
        raise RuntimeError("Checkpointer is not initialized. Ensure app lifespan has run.")
    return redis_container.checkpointer