"""
Single webhook endpoint that Vapi calls for everything happening on a live
call: tool/function calls from the LLM, and the end-of-call report (used
here purely for observability/logging of the final transcript+payload).

Vapi's current "Server URL" message shape wraps tool invocations as:
    {
      "message": {
        "type": "tool-calls",
        "call": {"id": "..."},
        "toolCallList": [
          {"id": "...", "function": {"name": "save_patient", "arguments": {...}}}
        ]
      }
    }
We respond with:
    {"results": [{"toolCallId": "...", "result": "<string the LLM will read>"}]}
"""
import json
import uuid

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.observability import trace_span
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/vapi", tags=["vapi"])
log = structlog.get_logger()


def _verify_secret(x_vapi_secret: str | None) -> None:
    """Vapi sends back whatever secret you configure on the Server URL.
    Reject anything else so randoms can't POST fake patient data."""
    if settings.VAPI_WEBHOOK_SECRET and x_vapi_secret != settings.VAPI_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


async def _handle_lookup_patient_by_phone(args: dict, service: PatientService) -> str:
    phone = args.get("phone_number", "")
    existing = await service.find_by_phone(phone)
    if existing:
        return json.dumps({
            "found": True,
            "patient_id": str(existing.patient_id),
            "first_name": existing.first_name,
            "last_name": existing.last_name,
        })
    return json.dumps({"found": False})


async def _handle_save_patient(args: dict, service: PatientService) -> str:
    patient_id = args.pop("patient_id", None)
    try:
        if patient_id:
            payload = PatientUpdate(**args)
            patient = await service.update_patient(uuid.UUID(patient_id), payload)
            return json.dumps({
                "success": True,
                "action": "updated",
                "patient_id": str(patient.patient_id),
            })
        else:
            payload = PatientCreate(**args)
            outcome = await service.register_or_flag_duplicate(payload)
            if outcome["duplicate"]:
                return json.dumps({
                    "success": False,
                    "duplicate": True,
                    "existing_patient": outcome["existing_patient"],
                    "message": "A patient with this phone number already exists.",
                })
            return json.dumps({
                "success": True,
                "action": "created",
                "patient_id": outcome["patient"]["patient_id"],
            })
    except ValidationError as exc:
        # Field-level errors so the agent can re-prompt just that field.
        errors = [{"field": e["loc"][-1], "message": e["msg"]} for e in exc.errors()]
        log.warning("save_patient_validation_failed", errors=errors)
        return json.dumps({"success": False, "validation_errors": errors})
    except Exception as exc:  # noqa: BLE001
        log.error("save_patient_failed", error=str(exc))
        return json.dumps({"success": False, "message": "Internal error saving patient record."})


TOOL_HANDLERS = {
    "lookup_patient_by_phone": _handle_lookup_patient_by_phone,
    "save_patient": _handle_save_patient,
}


@router.post("/webhook")
async def vapi_webhook(request: Request, x_vapi_secret: str | None = Header(default=None)):
    _verify_secret(x_vapi_secret)
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type")
    call_id = (message.get("call") or {}).get("id", "unknown")

    log.info("vapi_webhook_received", type=msg_type, call_id=call_id)

    if msg_type == "tool-calls":
        results = []
        async with AsyncSessionLocal() as db:  # type: AsyncSession
            service = PatientService(PatientRepository(db))
            for call in message.get("toolCallList", []):
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)
                handler = TOOL_HANDLERS.get(name)
                with trace_span(f"vapi_tool:{name}", call_id=call_id, arguments=args):
                    if handler:
                        result_str = await handler(dict(args), service)
                    else:
                        result_str = json.dumps({"success": False, "message": f"Unknown tool {name}"})
                results.append({"toolCallId": call.get("id"), "result": result_str})
        return {"results": results}

    if msg_type == "end-of-call-report":
        # Required "observability" item: log the final payload/transcript.
        log.info(
            "call_ended",
            call_id=call_id,
            ended_reason=message.get("endedReason"),
            transcript=message.get("transcript"),
            summary=message.get("summary"),
            cost=message.get("cost"),
        )
        with trace_span("vapi_end_of_call", call_id=call_id, summary=message.get("summary")):
            pass
        return {"received": True}

    # status-update, transcript, speech-update, etc. -- ack and ignore.
    return {"received": True}
