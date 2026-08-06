"""
One-time provisioning script. Run this AFTER the FastAPI app is deployed
(so VAPI_SERVER_URL is a real public URL).

Usage:
    python scripts/setup_vapi.py

What it does:
    1. Creates a Vapi Assistant using OpenAI gpt-4o, the SYSTEM_PROMPT, and
       the two tool definitions, pointed at our /vapi/webhook.
    2. Provisions a phone number:
       - Default: a FREE native Vapi US number (no Twilio account needed).
       - If USE_TWILIO_IMPORT=true in .env: imports an existing Twilio
         number instead (needed for non-US numbers, or a number you
         already own and want to keep).
    3. Prints the resulting assistant_id and phone number -- copy the
       assistant_id into VAPI_ASSISTANT_ID.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.vapi.prompt import SYSTEM_PROMPT  # noqa: E402
from app.vapi.tools_schema import VAPI_TOOLS  # noqa: E402

VAPI_BASE = "https://api.vapi.ai"  # verify current base URL at https://docs.vapi.ai/api-reference
HEADERS = {"Authorization": f"Bearer {settings.VAPI_API_KEY}", "Content-Type": "application/json"}


def create_assistant() -> str:
    payload = {
        "name": "Patient Registration Agent",
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.4,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
            "tools": VAPI_TOOLS,
        },
        "voice": {"provider": "vapi", "voiceId": "Elliot"},
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "en-US"},
        "firstMessage": "Hi, thanks for calling — this is Riley. Am I helping you register as a new patient today?",
        "serverUrl": settings.VAPI_SERVER_URL,
        "serverUrlSecret": settings.VAPI_WEBHOOK_SECRET,
        "endCallFunctionEnabled": True,
        "silenceTimeoutSeconds": 20,
    }
    resp = httpx.post(f"{VAPI_BASE}/assistant", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        print("VAPI ERROR:")
        print(resp.status_code)
        print(resp.text)
        exit()
    resp.raise_for_status()
    data = resp.json()
    print(f"Created assistant: {data['id']}")
    return data["id"]


def create_free_vapi_number(assistant_id: str) -> str:
    """Provisions a free native US number directly from Vapi. No Twilio needed.
    Vapi caps free numbers at 10 per account, US-only."""
    payload = {"provider": "vapi", "assistantId": assistant_id}
    resp = httpx.post(f"{VAPI_BASE}/phone-number", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    number = data.get("number", "unknown")
    print(f"Provisioned free Vapi number: {number} (id: {data['id']})")
    return number


def import_twilio_number(assistant_id: str) -> str:
    """Only used when USE_TWILIO_IMPORT=true — for non-US numbers or a
    number you already own on Twilio."""
    payload = {
        "provider": "twilio",
        "number": settings.TWILIO_PHONE_NUMBER,
        "twilioAccountSid": settings.TWILIO_ACCOUNT_SID,
        "twilioAuthToken": settings.TWILIO_AUTH_TOKEN,
        "assistantId": assistant_id,
    }
    resp = httpx.post(f"{VAPI_BASE}/phone-number", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    print(f"Imported Twilio number {settings.TWILIO_PHONE_NUMBER} as phone_number_id: {data['id']}")
    return settings.TWILIO_PHONE_NUMBER


if __name__ == "__main__":
    missing = [k for k in ("VAPI_API_KEY", "VAPI_SERVER_URL") if not getattr(settings, k)]
    if missing:
        raise SystemExit(f"Missing required env vars: {missing}")

    assistant_id = create_assistant()

    if settings.USE_TWILIO_IMPORT:
        needed = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"]
        missing_twilio = [k for k in needed if not getattr(settings, k)]
        if missing_twilio:
            raise SystemExit(f"USE_TWILIO_IMPORT=true but missing: {missing_twilio}")
        number = import_twilio_number(assistant_id)
    else:
        number = create_free_vapi_number(assistant_id)

    print(f"\nDone. Callable number: {number}")
    print(f"Set VAPI_ASSISTANT_ID={assistant_id} in your environment.")

