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