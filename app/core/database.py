import os
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from .settings import settings


class MongoDB:
    client: AsyncMongoClient = None
    db = None


class RedisContainer:
    client: Redis = None
    checkpointer: BaseCheckpointSaver = None  # Can be AsyncRedisSaver or MongoDBCkptSaver
    _using_mongo_fallback: bool = False


db_container = MongoDB()
redis_container = RedisContainer()


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
async def connect_to_mongo():
    mongo_uri = settings.MONGO_URI
    db_name = settings.DATABASE_NAME

    try:
        # Fail fast: a request waits at most this long for the database before it errors,
        # instead of hanging and leaving the app spinning for the whole driver default.
        db_container.client = AsyncMongoClient(
            mongo_uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000
        )
        # Startup retries a few times, so a slow moment doesn't keep the server down.
        for attempt in range(3):
            try:
                await db_container.client.admin.command("ping")
                break
            except PyMongoError:
                if attempt == 2:
                    raise
                print(f"MongoDB not reachable yet (attempt {attempt + 1}), retrying.")
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
    
    await db["orders"].create_index(
        [("tenant_id", 1), ("created_at", -1)], name="tenant_orders_by_date"
    )
    await db["messages"].create_index(
        [("conversation_id", 1), ("created_at", 1)], name="conversation_messages_in_order"
    )
    await db["messages"].create_index(
        [("tenant_id", 1), ("sender_phone", 1), ("created_at", -1)], name="tenant_customer_messages_recent"
    )
    print("[webhook] processed_messages indexes ensured.")
    from memory.facts import ensure_fact_indexes
    await ensure_fact_indexes(db)
    from services.billing import ensure_billing_indexes, migrate_subscriptions
    await ensure_billing_indexes(db)
    from services.sessions import ensure_session_indexes
    await ensure_session_indexes(db)
    from services.email import ensure_email_indexes
    await ensure_email_indexes(db)
    await migrate_subscriptions(db)
    from services.alerts import ensure_alert_indexes
    await ensure_alert_indexes(db)
    from services.menu_jobs import ensure_menu_job_indexes
    await ensure_menu_job_indexes(db)
    print("[memory] customer_facts indexes ensured.")


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
        print("[redis] REDIS_URI not set, will use MongoDB checkpointer fallback")
        await _setup_mongo_checkpointer_fallback()
        return

    if not redis_uri.startswith(("redis://", "rediss://", "unix://")):
        print(f"[redis] Invalid REDIS_URI format: {redis_uri!r}, using MongoDB fallback")
        await _setup_mongo_checkpointer_fallback()
        return

    # -------- Try to connect and check for Redis Stack modules --------
    probe = Redis.from_url(redis_uri, decode_responses=True)
    try:
        await probe.ping()
    except RedisError as e:
        print(f"[redis] Cannot reach Redis at {redis_uri}: {e}, using MongoDB fallback")
        await probe.aclose()
        await _setup_mongo_checkpointer_fallback()
        return

    try:
        modules_raw = await probe.execute_command("MODULE", "LIST")
    except RedisError as e:
        print(f"[redis] MODULE LIST failed: {e}, using MongoDB fallback")
        await probe.aclose()
        await _setup_mongo_checkpointer_fallback()
        return

    module_names = _extract_module_names(modules_raw)
    await probe.aclose()

    has_search = "search" in module_names
    has_rejson = "rejson" in module_names

    if not has_search or not has_rejson:
        print(f"[redis] Missing required modules (search={has_search}, rejson={has_rejson}), using MongoDB fallback")
        await _setup_mongo_checkpointer_fallback()
        return

    print(f"[redis] ✅ modules detected: {sorted(module_names)}")

    # -------- Real Redis client for general app use --------
    try:
        redis_container.client = Redis.from_url(redis_uri, decode_responses=True)
        await redis_container.client.ping()
        print(f"[redis] Successfully connected to Redis at {redis_uri}.")
    except RedisError as e:
        print(f"[redis] Failed to connect Redis client: {e}, using MongoDB fallback")
        await _setup_mongo_checkpointer_fallback()
        return

    # -------- LangGraph AsyncRedisSaver checkpointer --------
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
        print(f"[checkpointer] Failed to initialize Redis checkpointer: {e}, using MongoDB fallback")
        await _setup_mongo_checkpointer_fallback()
        return


async def _setup_mongo_checkpointer_fallback():
    """Setup MongoDB checkpointer as fallback for master graph."""
    if redis_container._using_mongo_fallback:
        return
    
    try:
        from memory.mongo_checkpointer import MongoDBCkptSaver
        db = get_database()
        redis_container.checkpointer = MongoDBCkptSaver(db)
        await redis_container.checkpointer.ensure_indexes()
        redis_container._using_mongo_fallback = True
        print("[checkpointer] ✅ MongoDB checkpointer fallback initialized for master graph")
    except Exception as e:
        print(f"[checkpointer] ❌ Failed to initialize MongoDB fallback: {e}")
        raise RuntimeError("No checkpointer available. Need Redis Stack or MongoDB.")


async def close_redis_connection():
    if redis_container.checkpointer and not redis_container._using_mongo_fallback:
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


def get_checkpointer() -> BaseCheckpointSaver:
    if redis_container.checkpointer is None:
        raise RuntimeError("Checkpointer is not initialized. Ensure app lifespan has run.")
    return redis_container.checkpointer