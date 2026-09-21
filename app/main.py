import os 
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
import uvicorn  # 1. Import uvicorn

from core.database import connect_to_mongo, close_mongo_connection
from routes.tenant import tenant_routes
from routes.whatsapp import whatsapp_router, alias_router


load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(lifespan=lifespan)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(tenant_routes)
v1_router.include_router(whatsapp_router)
v1_router.include_router(alias_router)

app.include_router(v1_router)
