"""Two-step sign-in and beta access: codes, recovery codes, challenges, locks, and who may add restaurants.

Run from the app folder:
    uv run --with pytest python -m pytest tests -q
"""

from datetime import datetime, timedelta, timezone

import pyotp

from services import beta, two_factor


def test_a_current_code_is_accepted_and_a_wrong_one_is_not():
    secret = two_factor.new_secret()
    assert two_factor.verify_totp(secret, pyotp.TOTP(secret).now())
    assert not two_factor.verify_totp(secret, "000000" if pyotp.TOTP(secret).now() != "000000" else "111111")
    assert not two_factor.verify_totp(secret, "12ab56")


def test_the_provisioning_link_names_the_app_and_the_account():
    secret = two_factor.new_secret()
    uri = two_factor.provisioning_uri(secret, "owner@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "Siyaf" in uri and "owner%40example.com" in uri


def test_a_recovery_code_works_once():
    codes = two_factor.new_recovery_codes()
    hashes = two_factor.hash_recovery_codes(codes)
    index = two_factor.use_recovery_code(hashes, codes[2])
    assert index == 2
    hashes.pop(index)
    assert two_factor.use_recovery_code(hashes, codes[2]) is None


def test_a_challenge_names_its_owner_and_nothing_else():
    token = two_factor.challenge_token("usr_1")
    assert two_factor.read_challenge(token) == "usr_1"
    assert two_factor.read_challenge("not-a-token") is None


def test_an_account_is_locked_until_the_lock_passes():
    now = datetime.now(timezone.utc)
    assert two_factor.is_locked({"totp_locked_until": now + timedelta(minutes=5)}, now)
    assert not two_factor.is_locked({"totp_locked_until": now - timedelta(minutes=1)}, now)
    assert not two_factor.is_locked({}, now)


def test_only_owners_have_two_step_sign_in():
    assert two_factor.is_owner({"role": "OWNER"})
    assert not two_factor.is_owner({"role": "FOUNDER"})


def test_beta_is_for_listed_owners_or_switched_on_accounts(monkeypatch):
    monkeypatch.setattr(beta.settings, "BETA_OWNER_EMAILS", "Friend@Example.com, other@example.com")
    assert beta.can_add_restaurant({"email": "friend@example.com"})
    assert beta.can_add_restaurant({"email": "stranger@example.com", "beta_multi_restaurant": True})
    assert not beta.can_add_restaurant({"email": "stranger@example.com"})
