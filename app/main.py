import os 
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from starlette.middleware.sessions import SessionMiddleware
from core.settings import settings
from fastapi.middleware.cors import CORSMiddleware

from core.database import connect_to_mongo, close_mongo_connection
from routes.tenant import tenant_routes
from routes.whatsapp import whatsapp_router, alias_router
from routes.auth import auth_routes
from routes.user import user_routes
from routes.orders import order_router
from routes.analytics import analytics_router
from routes.founder import founder_router
from routes.websocket import websocket_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Autonomous Agent Business Platform",
    description="Multi-tenant autonomous AI operating system for restaurant operations and founder growth.",
    version="1.0.0",
    lifespan=lifespan
)

origins = [
    "http://localhost:3000",      
    "http://localhost:5173",      
    settings.FRONTEND_ORIGIN,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           
    allow_credentials=True,          
    allow_methods=["*"],             
    allow_headers=["*"],             
)

app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SESSION_SECRET_KEY
)

# API v1 routes
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_routes)
v1_router.include_router(user_routes)
v1_router.include_router(tenant_routes)
v1_router.include_router(order_router)
v1_router.include_router(analytics_router)
v1_router.include_router(founder_router)
v1_router.include_router(whatsapp_router)
v1_router.include_router(alias_router)

app.include_router(v1_router)

# Realtime WebSocket channels
app.include_router(websocket_router)
