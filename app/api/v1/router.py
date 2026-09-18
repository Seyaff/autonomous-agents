from fastapi import APIRouter
from app.api.v1.webhooks_whatsapp import (
    router as whatsapp_webhook_router,
    alias_router as whatsapp_webhook_alias_router
)
from app.api.v1.meta_auth import router as meta_auth_router
from app.api.v1.menu import router as menu_router
from app.api.v1.orders import router as orders_router
from app.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(whatsapp_webhook_router)
api_v1_router.include_router(whatsapp_webhook_alias_router)
api_v1_router.include_router(meta_auth_router)
api_v1_router.include_router(menu_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(tenants_router)
