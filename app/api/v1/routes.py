from fastapi import APIRouter

from api.v1.endpoints.tenant import tenant_routes
from api.v1.endpoints.whatsapp import whatsapp_router, alias_router
from api.v1.endpoints.auth import auth_routes
from api.v1.endpoints.user import user_routes
from api.v1.endpoints.orders import order_router
from api.v1.endpoints.kpis import kpi_router
from api.v1.endpoints.customers import customer_router
from api.v1.endpoints.billing import billing_router
from api.v1.endpoints.alerts import alert_router
from api.v1.endpoints.operations import ops_router
from api.v1.endpoints.analytics import analytics_router
from api.v1.endpoints.knowledge import knowledge_router
from api.v1.endpoints.inbox import inbox_router
from api.v1.endpoints.inbox_ws import inbox_ws_router
from api.v1.endpoints.agent import agent_router
from api.v1.endpoints.health import router as health_router
from api.v1.endpoints.payments import payments_router
from api.v1.endpoints.staff import owner_staff_routes, staff_routes


v1_router = APIRouter()

v1_router.include_router(auth_routes)
v1_router.include_router(user_routes)
v1_router.include_router(tenant_routes)
v1_router.include_router(order_router)
v1_router.include_router(kpi_router)
v1_router.include_router(customer_router)
v1_router.include_router(billing_router)
v1_router.include_router(alert_router)
v1_router.include_router(ops_router)
v1_router.include_router(analytics_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(whatsapp_router)
v1_router.include_router(alias_router)
v1_router.include_router(inbox_router)
v1_router.include_router(inbox_ws_router)
v1_router.include_router(agent_router)
v1_router.include_router(health_router)
v1_router.include_router(payments_router)
v1_router.include_router(owner_staff_routes)
v1_router.include_router(staff_routes)
