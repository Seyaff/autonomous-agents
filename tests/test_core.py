import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.core.database import init_db
from app.services.dummy_payment import dummy_payment_service

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    try:
        await init_db()
    except Exception:
        pass
    yield

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data

@pytest.mark.asyncio
async def test_meta_webhook_verification():
    verify_token = settings.META_WEBHOOK_VERIFY_TOKEN
    challenge = "1158201244"
    url = f"/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.challenge={challenge}&hub.verify_token={verify_token}"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(url)
    assert response.status_code == 200
    assert response.text == challenge

@pytest.mark.asyncio
async def test_meta_webhook_alias_verification():
    verify_token = settings.META_WEBHOOK_VERIFY_TOKEN
    challenge = "99887766"
    url = f"/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.challenge={challenge}&hub.verify_token={verify_token}"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(url)
    assert response.status_code == 200
    assert response.text == challenge

@pytest.mark.asyncio
async def test_meta_webhook_verification_invalid_token():
    url = "/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=123&hub.verify_token=wrong_token"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(url)
    assert response.status_code == 403

def test_dummy_payment_service():
    session = dummy_payment_service.generate_dummy_checkout_link("order_123", 25.50, "+15551234")
    assert session["amount"] == 25.50
    assert "checkout_url" in session
    assert session["status"] == "pending"

    payment = dummy_payment_service.process_instant_dummy_payment("order_123", 25.50)
    assert payment["status"] == "dummy_paid"
    assert payment["amount"] == 25.50
    assert "transaction_id" in payment
