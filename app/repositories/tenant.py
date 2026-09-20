from schemas.tenant import TenantBase , TenantCreate
from pymongo.asynchronous.database import AsyncDatabase

class TenantModel:
    COLLECTION_NAME: "tenants"
    
    @staticmethod
    async def create(db : AsyncDatabase , tenant_data : TenantCreate):
        """Creates a new tenant doc and collection if not exists"""
        doc = tenant_data.model_dump()
        now = datetime.now(timezone.utc)
        doc["created_at"] = now
        doc["updated_at"] = now
        
        
        await db[TenantModel.COLLECTION_NAME].insert_one(doc)
        return doc
        