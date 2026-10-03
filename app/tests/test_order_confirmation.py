"""Order confirmation: button ids and the summary the customer reads.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from services.order_confirmation import CANCEL_PREFIX, CONFIRM_PREFIX, parse_button, summary_text


def test_confirm_button_id_round_trips():
    assert parse_button(f"{CONFIRM_PREFIX}ORD-1A2B") == ("confirm", "ORD-1A2B")


def test_cancel_button_id_round_trips():
    assert parse_button(f"{CANCEL_PREFIX}ORD-1A2B") == ("cancel", "ORD-1A2B")


def test_unknown_button_id_is_ignored():
    assert parse_button("something_else:ORD-1") == (None, None)
    assert parse_button("") == (None, None)


def test_summary_lists_items_total_and_asks_for_confirmation():
    order = {
        "customer_name": "Ayesha",
        "items": [{"name": "Chicken Karahi", "quantity": 2}, {"name": "Naan", "quantity": 4}],
        "delivery_address": "Block 4, Gulberg III",
        "payment_method": "cod",
        "currency": "PKR",
        "total_amount": 2950.0,
    }
    text = summary_text(order)
    assert "Ayesha" in text
    assert "2 x Chicken Karahi" in text and "4 x Naan" in text
    assert "Block 4, Gulberg III" in text
    assert "PKR 2950.00" in text
    assert "Tap Confirm" in text
