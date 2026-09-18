import uuid
from datetime import datetime, timezone
from typing import Dict, Any

class DummyPaymentService:
    """Mock payment service simulating payment gateway (Stripe/PayPal/Razorpay) interactions."""

    @staticmethod
    def generate_dummy_checkout_link(order_id: str, amount: float, customer_phone: str) -> Dict[str, Any]:
        """Generates a mock checkout session link for customer testing."""
        session_id = f"dummy_sess_{uuid.uuid4().hex[:12]}"
        return {
            "session_id": session_id,
            "order_id": order_id,
            "amount": amount,
            "currency": "USD",
            "checkout_url": f"https://pay.restaurant.example/checkout/{session_id}",
            "status": "pending"
        }

    @staticmethod
    def process_instant_dummy_payment(order_id: str, amount: float) -> Dict[str, Any]:
        """Simulates an immediate successful payment transaction."""
        transaction_id = f"txn_mock_{uuid.uuid4().hex[:10]}"
        return {
            "transaction_id": transaction_id,
            "order_id": order_id,
            "amount": amount,
            "status": "dummy_paid",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Dummy payment processed successfully."
        }

dummy_payment_service = DummyPaymentService()
