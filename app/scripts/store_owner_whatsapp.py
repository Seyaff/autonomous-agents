"""
One-time: moves the dev WhatsApp credentials from .env into one restaurant's record.

After this, every restaurant (yours included) sends with its own stored credentials,
and the .env WhatsApp values are no longer used by the app.

Usage (from the app folder, with the production TOKEN_ENCRYPTION_KEY set locally):
    uv run python scripts/store_owner_whatsapp.py <tenant_id>

Refuses to run without TOKEN_ENCRYPTION_KEY, so the token is never stored unencrypted.
"""

import asyncio
import sys

from core.database import close_mongo_connection, connect_to_mongo, get_database
from core.secrets import protect
from core.settings import settings
from core.whatsapp_utils import verify_phone_number


async def main(tenant_id: str) -> int:
    if not settings.TOKEN_ENCRYPTION_KEY:
        print("TOKEN_ENCRYPTION_KEY is not set. Refusing to store the token unencrypted.")
        return 1
    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        print("WHATSAPP_TOKEN or WHATSAPP_PHONE_NUMBER_ID is missing from the environment.")
        return 1

    details = await verify_phone_number(settings.WHATSAPP_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID)

    await connect_to_mongo()
    db = get_database()
    result = await db["tenants"].update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
            "whatsapp_access_token": protect(settings.WHATSAPP_TOKEN),
            "whatsapp_connected": True,
            "whatsapp_status": "connected",
            "whatsapp_last_error": None,
            "display_phone_number": details.get("display_phone_number"),
            "verified_name": details.get("verified_name"),
        }},
    )
    await close_mongo_connection()
    if result.matched_count != 1:
        print(f"No restaurant with tenant_id={tenant_id}.")
        return 1
    print(f"Stored WhatsApp credentials for {tenant_id}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
