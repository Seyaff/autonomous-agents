"""JazzCash signing: what we sign, what we accept back, and what we refuse.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest

from services import jazzcash

SALT = "test-salt"
NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)


def signed_callback(**changes):
    fields = {
        "pp_TxnRefNo": "TORD1100000", "pp_Amount": "135000", "pp_ResponseCode": "000",
        "pp_TxnCurrency": "PKR", "pp_Version": "1.1",
    }
    fields.update(changes)
    fields["pp_SecureHash"] = jazzcash.secure_hash(fields, SALT)
    return urlencode(fields).encode()


def test_the_hash_is_uppercase_hex_and_ignores_empty_fields():
    a = jazzcash.secure_hash({"pp_Amount": "100", "pp_Empty": ""}, SALT)
    b = jazzcash.secure_hash({"pp_Amount": "100"}, SALT)
    assert a == b
    assert a == a.upper() and len(a) == 64


def test_a_correctly_signed_callback_is_accepted():
    fields = jazzcash.parse_callback(signed_callback())
    jazzcash.verify_callback(fields, SALT)


def test_a_changed_amount_is_refused():
    body = signed_callback()
    tampered = body.replace(b"135000", b"100")
    with pytest.raises(ValueError):
        jazzcash.verify_callback(jazzcash.parse_callback(tampered), SALT)


def test_a_callback_signed_with_another_salt_is_refused():
    fields = jazzcash.parse_callback(signed_callback())
    with pytest.raises(ValueError):
        jazzcash.verify_callback(fields, "not-the-salt")


def test_a_callback_without_a_signature_is_refused():
    with pytest.raises(ValueError):
        jazzcash.verify_callback({"pp_Amount": "135000"}, SALT)


def test_amounts_are_sent_in_paisa():
    fields = jazzcash.payment_fields(reference="TORD1", amount_pkr=1350, description="Order", return_url="https://x", now=NOW)
    assert fields["pp_Amount"] == "135000"
    assert fields["pp_TxnCurrency"] == "PKR"
    assert len(fields["pp_TxnDateTime"]) == 14


def test_references_are_alphanumeric_and_keep_the_order_id():
    ref = jazzcash.txn_ref("ORD-1A2B", NOW)
    assert ref.isalnum()
    assert "ORD1A2B" in ref
