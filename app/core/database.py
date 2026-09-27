import os
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from .settings import settings

class MongoDB:
    client: AsyncMongoClient = None
    db = None

db_container = MongoDB()

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
    """Dependency / helper function to access the database instance."""
    if db_container.db is None:
        raise RuntimeError("Database is not initialized. Ensure app lifespan has run.")
    return db_container.db


async def ensure_webhook_indexes():
    """
    Idempotent startup hook. Creates the unique index that powers webhook
    dedup, plus a TTL index to auto-expire old entries after Meta's retry window.
    """
    db = db_container.db
    if db is None:
        raise RuntimeError("Database not connected.")

    await db["processed_messages"].create_index(
        "message_id", unique=True, name="uniq_message_id"
    )
    await db["processed_messages"].create_index(
        "received_at", expireAfterSeconds=7 * 24 * 3600, name="ttl_received_at"
    )
    print("[webhook] processed_messages indexes ensured.")


async def verify_webhook_indexes():
    """Logs whether the unique index exists. Useful for smoke-testing at startup."""
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