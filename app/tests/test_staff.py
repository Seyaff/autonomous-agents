"""Staff PINs, sign-in limits, one device per person, and the dine-in order steps.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

import asyncio
import re
from types import SimpleNamespace

import pytest

from services import staff as svc
from services.availability import today_for
from services.staff import StaffError

TENANT = "t_staff_1"
TODAY_TENANT = {"tenant_id": TENANT, "timezone": "UTC", "dine_table_count": 4, "tenant_slug": "shinwari"}


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_):
        return self

    async def to_list(self, length=None):
        return list(self.rows)


class Coll:
    """A small stand-in for a Mongo collection: equality, $ne, $in and $regex filters, $set and $unset updates."""

    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]

    @staticmethod
    def _match(doc, query):
        for key, want in query.items():
            have = doc.get(key)
            if isinstance(want, dict):
                if "$ne" in want and have == want["$ne"]:
                    return False
                if "$in" in want and have not in want["$in"]:
                    return False
                if "$regex" in want:
                    flags = re.I if "i" in want.get("$options", "") else 0
                    if have is None or not re.search(want["$regex"], str(have), flags):
                        return False
            elif have != want:
                return False
        return True

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if self._match(d, query):
                return dict(d)
        return None

    def find(self, query, projection=None):
        return Cursor([dict(d) for d in self.docs if self._match(d, query)])

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    @staticmethod
    def _apply(doc, update):
        doc.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            doc.pop(key, None)

    async def update_one(self, query, update):
        for d in self.docs:
            if self._match(d, query):
                self._apply(d, update)
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def update_many(self, query, update):
        n = 0
        for d in self.docs:
            if self._match(d, query):
                self._apply(d, update)
                n += 1
        return SimpleNamespace(matched_count=n)


class DB(dict):
    def __getattr__(self, name):
        return self[name]


def make_db(menu=None):
    menu = menu if menu is not None else [
        {"tenant_id": TENANT, "name": "Chicken Karahi", "price": 1650, "category": "Karahi"},
        {"tenant_id": TENANT, "name": "Plain Naan", "price": 70, "category": "Breads"},
        {"tenant_id": TENANT, "name": "Mutton Karahi", "price": 2650, "category": "Karahi", "sold_out_on": today_for(TODAY_TENANT)},
    ]
    return DB(
        tenants=Coll([dict(TODAY_TENANT)]),
        staff=Coll(),
        table_orders=Coll(),
        print_jobs=Coll(),
        menu_items=Coll(menu),
    )


def run(coro):
    return asyncio.run(coro)


def add_waiter(db, name="Ali", pin="1234"):
    return run(svc.create_staff(db, TENANT, name, "waiter", pin))


def sign_in(db, staff_id, pin, device="iPad 1"):
    return run(svc.sign_in(db, TENANT, staff_id, pin, device))


def current(db, token):
    return run(svc.staff_from_token(db, token))


# ---- PINs and owner setup ----

def test_pin_is_stored_as_a_hash_never_as_typed():
    db = make_db()
    add_waiter(db, pin="1234")
    stored = db.staff.docs[0]
    assert stored["pin_hash"] != "1234"
    assert svc.pin_matches("1234", stored["pin_hash"])


def test_pin_must_be_four_digits_and_role_must_be_known():
    db = make_db()
    for bad in ["12", "12345", "12a4", ""]:
        with pytest.raises(StaffError):
            add_waiter(db, pin=bad)
    with pytest.raises(StaffError):
        run(svc.create_staff(db, TENANT, "Bilal", "manager", "1234"))


def test_public_view_never_shows_the_pin():
    db = make_db()
    created = add_waiter(db)
    assert "pin" not in created and "pin_hash" not in created


# ---- Sign-in ----

def test_right_pin_signs_in_and_the_token_identifies_the_person():
    db = make_db()
    staff = add_waiter(db)
    result = sign_in(db, staff["staff_id"], "1234")
    assert current(db, result["token"])["staff_id"] == staff["staff_id"]


def test_three_wrong_pins_lock_the_person_until_the_owner_unlocks():
    db = make_db()
    staff = add_waiter(db)
    for _ in range(2):
        with pytest.raises(StaffError, match="tries left"):
            sign_in(db, staff["staff_id"], "0000")
    with pytest.raises(StaffError, match="Locked after 3 wrong PINs"):
        sign_in(db, staff["staff_id"], "0000")
    with pytest.raises(StaffError, match="locked"):
        sign_in(db, staff["staff_id"], "1234")

    run(svc.unlock(db, TENANT, staff["staff_id"]))
    assert sign_in(db, staff["staff_id"], "1234")["token"]


def test_signing_in_on_a_second_ipad_ends_the_first_session():
    db = make_db()
    staff = add_waiter(db)
    first = sign_in(db, staff["staff_id"], "1234", device="iPad 1")["token"]
    sign_in(db, staff["staff_id"], "1234", device="iPad 2")
    with pytest.raises(StaffError, match="another iPad"):
        current(db, first)


def test_resetting_the_pin_signs_the_device_out():
    db = make_db()
    staff = add_waiter(db)
    token = sign_in(db, staff["staff_id"], "1234")["token"]
    run(svc.reset_pin(db, TENANT, staff["staff_id"], "5555"))
    with pytest.raises(StaffError):
        current(db, token)
    assert sign_in(db, staff["staff_id"], "5555")["token"]


def test_kitchen_signs_in_with_its_own_pin():
    db = make_db()
    kitchen = run(svc.create_staff(db, TENANT, "Imran", "kitchen", "3690"))
    token = sign_in(db, kitchen["staff_id"], "3690")["token"]
    assert current(db, token)["role"] == "kitchen"


def test_removed_person_is_signed_out_and_leaves_the_roster():
    db = make_db()
    staff = add_waiter(db)
    token = sign_in(db, staff["staff_id"], "1234")["token"]
    run(svc.remove(db, TENANT, staff["staff_id"]))
    with pytest.raises(StaffError):
        current(db, token)
    assert run(svc.roster(db, TENANT)) == []


# ---- Dine-in orders ----

def test_order_takes_prices_from_the_menu_and_queues_two_prints():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    order = run(svc.send_order(db, TENANT, waiter, 2, [{"name": "chicken karahi", "qty": 2}]))
    assert order["items"][0]["price"] == 1650
    assert order["waiter_name"] == "Ali" and order["kitchen_status"] == "new"
    kinds = sorted(j["kind"] for j in db.print_jobs.docs)
    assert kinds == ["kitchen_ticket", "reception_slip"]


def test_sold_out_dish_and_unknown_dish_are_refused():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    with pytest.raises(StaffError, match="sold out"):
        run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Mutton Karahi", "qty": 1}]))
    with pytest.raises(StaffError, match="isn't on the menu"):
        run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Pizza", "qty": 1}]))


def test_table_must_exist_and_quantity_must_be_sensible():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    with pytest.raises(StaffError, match="isn't set up"):
        run(svc.send_order(db, TENANT, waiter, 9, [{"name": "Plain Naan", "qty": 1}]))
    with pytest.raises(StaffError, match="Quantity"):
        run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Plain Naan", "qty": 0}]))


def test_kitchen_moves_new_to_cooking_to_ready_and_the_table_shows_it():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    order = run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Plain Naan", "qty": 1}]))
    kitchen = {"staff_id": "k1", "tenant_id": TENANT, "role": "kitchen"}

    with pytest.raises(StaffError, match="past that step"):
        run(svc.kitchen_update(db, TENANT, kitchen, order["order_id"], "ready"))
    run(svc.kitchen_update(db, TENANT, kitchen, order["order_id"], "cooking"))
    run(svc.kitchen_update(db, TENANT, kitchen, order["order_id"], "ready"))

    board = run(svc.table_board(db, TENANT))
    assert board[0]["status"] == "ready"


def test_only_the_right_role_can_change_kitchen_status():
    db = make_db()
    waiter = {"staff_id": "w1", "tenant_id": TENANT, "role": "waiter", "name": "Ali"}
    with pytest.raises(StaffError, match="role"):
        run(svc.kitchen_update(db, TENANT, waiter, "TO-X", "cooking"))


def test_table_goes_free_to_sent_to_served_to_bill_to_paid():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    assert run(svc.table_board(db, TENANT))[0]["status"] == "free"

    order = run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Chicken Karahi", "qty": 1}, {"name": "Plain Naan", "qty": 2}]))
    assert run(svc.table_board(db, TENANT))[0]["status"] == "sent"

    run(svc.mark_served(db, TENANT, waiter, order["order_id"]))
    assert run(svc.table_board(db, TENANT))[0]["status"] == "served"

    bill = run(svc.request_bill(db, TENANT, waiter, 1))
    assert bill["total"] == 1650 + 2 * 70
    assert run(svc.table_board(db, TENANT))[0]["status"] == "bill"
    assert db.print_jobs.docs[-1]["kind"] == "bill"

    run(svc.mark_paid_cash(db, TENANT, waiter, 1))
    assert run(svc.table_board(db, TENANT))[0]["status"] == "free"


def test_cannot_mark_paid_before_the_bill_is_printed():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Plain Naan", "qty": 1}]))
    with pytest.raises(StaffError, match="Print the bill"):
        run(svc.mark_paid_cash(db, TENANT, waiter, 1))


def test_waiter_menu_marks_sold_out_and_leaves_out_hidden_dishes():
    db = make_db([
        {"tenant_id": TENANT, "name": "Chicken Karahi", "price": 1650, "category": "Karahi"},
        {"tenant_id": TENANT, "name": "Mutton Karahi", "price": 2650, "category": "Karahi", "sold_out_on": today_for(TODAY_TENANT)},
        {"tenant_id": TENANT, "name": "Old Dish", "price": 100, "category": "Other", "hidden": True},
    ])
    items = run(svc.staff_menu(db, TENANT, TODAY_TENANT))
    names = {i["name"]: i for i in items}
    assert "Old Dish" not in names
    assert names["Mutton Karahi"]["sold_out"] is True
    assert names["Chicken Karahi"]["sold_out"] is False


def test_named_bill_goes_to_the_counter_as_a_receipt_and_can_be_marked_printed():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Chicken Karahi", "qty": 1}, {"name": "Plain Naan", "qty": 2}]))
    run(svc.request_bill(db, TENANT, waiter, 1, customer_name="Mr Khan", customer_phone="0300 1234567"))

    jobs = run(svc.list_print_jobs(db, TENANT))
    assert len(jobs) == 1
    receipt = jobs[0]["receipt"]
    assert receipt["customer_name"] == "Mr Khan"
    assert receipt["total"] == 1650 + 2 * 70
    assert receipt["waiter"] == "Ali"

    run(svc.mark_printed(db, TENANT, jobs[0]["job_id"]))
    assert run(svc.list_print_jobs(db, TENANT)) == []
    with pytest.raises(StaffError):
        run(svc.mark_printed(db, TENANT, jobs[0]["job_id"]))


def test_bill_without_a_name_is_still_fine_and_a_bad_phone_is_refused():
    db = make_db()
    waiter = current(db, sign_in(db, add_waiter(db)["staff_id"], "1234")["token"])
    run(svc.send_order(db, TENANT, waiter, 1, [{"name": "Plain Naan", "qty": 1}]))
    with pytest.raises(StaffError, match="phone"):
        run(svc.request_bill(db, TENANT, waiter, 1, customer_phone="call me"))
    run(svc.request_bill(db, TENANT, waiter, 1))
    assert run(svc.list_print_jobs(db, TENANT))[0]["receipt"]["customer_name"] is None
