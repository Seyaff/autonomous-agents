from fastapi import APIRouter

from api.v1.endpoints.tenant import tenant_routes
from api.v1.endpoints.whatsapp import whatsapp_router, alias_router
from api.v1.endpoints.auth import auth_routes
from api.v1.endpoints.user import user_routes
from api.v1.endpoints.orders import order_router
from api.v1.endpoints.analytics import analytics_router
from api.v1.endpoints.founder import founder_router
from api.v1.endpoints.knowledge import knowledge_router
from api.v1.endpoints.websocket import websocket_router
from api.v1.endpoints.agent import agent_router
from api.v1.endpoints.health import router as health_router


v1_router = APIRouter()

v1_router.include_router(auth_routes)
v1_router.include_router(user_routes)
v1_router.include_router(tenant_routes)
v1_router.include_router(order_router)
v1_router.include_router(analytics_router)
v1_router.include_router(founder_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(whatsapp_router)
v1_router.include_router(alias_router)
v1_router.include_router(alias_router)
v1_router.include_router(websocket_router)
v1_router.include_router(agent_router)
v1_router.include_router(health_router)