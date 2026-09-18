import re
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db
from app.services.audio_service import audio_service
from app.services.telemetry_service import telemetry_service

HINDI_BLOCKLIST = [
    r"\bturant\b",
    r"\bkripya\b",
    r"\bnamaste\b",
    r"\bnamaskar\b",
    r"\bdhanyawad\b",
    r"\bsamay\b",
    r"\bbhojan\b",
    r"\bswagat\b",
    r"\bavashyakta\b",
    r"\bmitra\b",
]

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()

@pytest.mark.asyncio
async def test_pashto_phonetic_number_and_phrase_normalization():
    """
    Eval Suite: Pashto & colloquial Urdu transcript normalization.
    Ensures spoken Pashto numbers (Yao, Dwa, Dray, Salor, etc.) and verbs
    are resolved to clean digits and recognized order terms.
    """
    cases = [
        ("yao Shinwari Karahi ao salor naana rawalege", "1 Shinwari Karahi ao 4 naan bhej dein"),
        ("dwa plate Chapli Kabab ao las naana", "2 plate Chapli Kabab ao 10 naan"),
        ("dray Kabuli Pulao khurak", "3 Kabuli Pulao portion / plate"),
        ("peenzah Roghani Naan ao dwa chaye", "5 Roghani Naan ao 2 kahwa"),
    ]

    for raw_input, expected_sub in cases:
        normalized = audio_service.normalize_pashto_urdu_transcript(raw_input)
        # Check numbers converted
        for num in ["1", "2", "3", "4", "5", "10"]:
            if num in expected_sub:
                assert num in normalized, f"Failed to normalize number {num} in '{raw_input}' -> '{normalized}'"

@pytest.mark.asyncio
async def test_roman_urdu_purity_and_zero_hindi():
    """
    Eval Suite: Roman Urdu Lexicon Benchmark.
    Ensures customer support responses contain zero Hindi vocabulary.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "1251071574764683",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "923417268523",
                            "phone_number_id": "1251071574764683"
                        },
                        "messages": [{
                            "from": "923005550001",
                            "id": "wamid.EVAL_TEST_01",
                            "timestamp": "1710777000",
                            "type": "text",
                            "text": {"body": "Assalam-o-Alaikum, order karna hai"}
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        res = await client.post("/api/v1/whatsapp/webhook", json=payload)
        assert res.status_code == 200
        reply = res.json().get("reply", "")
        assert reply, "Expected agent reply"

        # Check against Hindi blocklist
        reply_lower = reply.lower()
        for forbidden in HINDI_BLOCKLIST:
            match = re.search(forbidden, reply_lower)
            assert not match, f"Found forbidden Hindi word matching '{forbidden}' in response: {reply}"

@pytest.mark.asyncio
async def test_frictionless_menu_presentation():
    """
    Eval Suite: Menu Gatekeeping Benchmark.
    When a customer asks for the menu, the agent MUST immediately display dishes & Rs. prices,
    without forcing qualification questions (e.g. 'kitne afraad hain?').
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "1251071574764683",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "923417268523",
                            "phone_number_id": "1251071574764683"
                        },
                        "messages": [{
                            "from": "923005550002",
                            "id": "wamid.EVAL_TEST_02",
                            "timestamp": "1710777001",
                            "type": "text",
                            "text": {"body": "menu dikhao please"}
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        res = await client.post("/api/v1/whatsapp/webhook", json=payload)
        assert res.status_code == 200
        reply = res.json().get("reply", "")

        # Must mention prices in Rs. and key specialties
        assert "Rs" in reply or "rs" in reply.lower(), f"Expected 'Rs.' currency in menu reply: {reply}"
        assert any(dish in reply.lower() for dish in ["karahi", "kabab", "pulao", "naan"]), (
            f"Expected dish listings in menu response: {reply}"
        )

        # Must NOT force qualification gatekeeping
        gatekeeping_phrases = ["pehle batayein kitne", "kitne afraad", "qualification"]
        assert not any(phrase in reply.lower() for phrase in gatekeeping_phrases), (
            f"Agent gatekept menu with qualification question: {reply}"
        )

@pytest.mark.asyncio
async def test_telemetry_trace_recording():
    """
    Eval Suite: Turn Observability & Telemetry Verification.
    Verifies that webhook interactions generate structured traces with granular span latencies.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check telemetry traces endpoint
        res = await client.get("/api/v1/telemetry/traces")
        assert res.status_code == 200
        data = res.json()
        assert "metrics" in data
        assert "traces" in data
        assert data["metrics"]["total_turns"] > 0
        assert data["metrics"]["avg_latency_ms"] >= 0

        latest_trace = data["traces"][0]
        assert "trace_id" in latest_trace
        assert "spans" in latest_trace
        assert "total_latency_ms" in latest_trace
