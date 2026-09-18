import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db
from app.services.kitchen_service import kitchen_service

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()

@pytest.mark.asyncio
async def test_kitchen_ticket_formatting():
    ticket = kitchen_service.format_kitchen_ticket(
        order_number="PK-991",
        order_type="delivery",
        delivery_address="F-8/2 Islamabad",
        items=[
            {"name": "Shinwari Mutton Karahi (Full)", "quantity": 1, "notes": "Medium spice"},
            {"name": "Roghani Naan", "quantity": 3}
        ],
        total_amount=2640.0,
        payment_method="COD",
        customer_notes="Please send extra mint chutney"
    )
    assert "KITCHEN TICKET #PK-991" in ticket
    assert "Shinwari Mutton Karahi (Full)" in ticket
    assert "3x Roghani Naan" in ticket
    assert "Rs. 2,640" in ticket
    assert "extra mint chutney" in ticket

@pytest.mark.asyncio
async def test_full_onboarding_pipeline():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 0: Start onboarding
        res = await client.post("/api/v1/onboarding/start", json={
            "name": "Khyber Shinwari Express",
            "currency": "PKR"
        })
        assert res.status_code == 200
        data = res.json()
        tenant_id = data["tenant_id"]
        assert "khyber-shinwari-express" in data["slug"]

        # Step 1: Update Identity
        res = await client.patch(f"/api/v1/onboarding/{tenant_id}/identity", json={
            "cuisine": "Shinwari & BBQ",
            "city": "Peshawar",
            "address": "University Road, Peshawar",
            "opening_hours": "01:00 PM - 01:00 AM",
            "kitchen_phone": "923001234567"
        })
        assert res.status_code == 200
        assert res.json()["current_step"] == "IDENTITY_SAVED"

        # Step 2: Ingest Menu
        res = await client.post(f"/api/v1/onboarding/{tenant_id}/menu", json={
            "items": [
                {"name": "Special Dumba Karahi", "category": "Karahi Specials", "price": 3200.0, "is_available": True},
                {"name": "Garlic Naan", "category": "Breads", "price": 90.0, "is_available": True}
            ]
        })
        assert res.status_code == 200
        assert res.json()["count"] == 2
        assert res.json()["current_step"] == "MENU_INGESTED"

        # Step 3: Connect WhatsApp (Sandbox mode)
        res = await client.post(f"/api/v1/onboarding/{tenant_id}/whatsapp", json={
            "phone_number_id": "test_phone_id_999",
            "waba_id": "test_waba_id_888",
            "display_phone_number": "923001234567"
        })
        assert res.status_code == 200
        assert res.json()["current_step"] == "WHATSAPP_CONNECTED"

        # Step 4: Test Kitchen Ticket
        res = await client.post(f"/api/v1/onboarding/{tenant_id}/test-kitchen", json={
            "kitchen_phone": "923001234567"
        })
        assert res.status_code == 200
        assert res.json()["current_step"] == "KITCHEN_VERIFIED"

        # Step 5: Complete Onboarding
        res = await client.post(f"/api/v1/onboarding/{tenant_id}/complete")
        assert res.status_code == 200
        complete_data = res.json()
        assert complete_data["status"] == "active"
        assert "wa.me" in complete_data["whatsapp_link"]

        # Check Final Status
        status_res = await client.get(f"/api/v1/onboarding/{tenant_id}/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["current_step"] == "ACTIVE"
        assert status_data["progress_percentage"] == 100
        assert status_data["whatsapp_connected"] is True
        assert status_data["kitchen_verified"] is True

@pytest.mark.asyncio
async def test_marketing_stats():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/marketing/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_delivered_orders" in data
        assert "estimated_social_impressions" in data
        assert data["viral_loop_status"] == "active"
