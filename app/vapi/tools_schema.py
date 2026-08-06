"""
Tool (function) definitions registered with the Vapi assistant. Vapi calls
our webhook (app/api/vapi_webhook.py) with the function name + arguments
whenever the LLM decides to invoke one of these mid-call.
"""

PATIENT_PROPERTIES = {
    "first_name": {"type": "string", "description": "Patient's first name"},
    "last_name": {"type": "string", "description": "Patient's last name"},
    "date_of_birth": {
        "type": "string",
        "description": "Date of birth, formatted YYYY-MM-DD",
    },
    "sex": {
        "type": "string",
        "enum": ["Male", "Female", "Other", "Decline to Answer"],
    },
    "phone_number": {"type": "string", "description": "10-digit US phone number"},
    "email": {"type": "string", "description": "Email address, optional"},
    "address_line_1": {"type": "string"},
    "address_line_2": {"type": "string", "description": "Apartment/suite, optional"},
    "city": {"type": "string"},
    "state": {"type": "string", "description": "2-letter US state abbreviation"},
    "zip_code": {"type": "string", "description": "5-digit or ZIP+4 zip code"},
    "insurance_provider": {"type": "string"},
    "insurance_member_id": {"type": "string"},
    "preferred_language": {"type": "string"},
    "emergency_contact_name": {"type": "string"},
    "emergency_contact_phone": {"type": "string"},
}

REQUIRED_PATIENT_FIELDS = [
    "first_name",
    "last_name",
    "date_of_birth",
    "sex",
    "phone_number",
    "address_line_1",
    "city",
    "state",
    "zip_code",
]

VAPI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_patient_by_phone",
            "description": (
                "Look up whether a patient already exists with the given phone number. "
                "Call this as soon as you have the caller's phone number, before "
                "collecting the rest of their information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string", "description": "10-digit US phone number"}
                },
                "required": ["phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_patient",
            "description": (
                "Create a new patient record, or update an existing one if patient_id is "
                "provided. Only call this AFTER reading the full record back to the caller "
                "and receiving explicit confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "If updating an existing patient, their patient_id UUID. Omit for a new patient.",
                    },
                    **PATIENT_PROPERTIES,
                },
                "required": REQUIRED_PATIENT_FIELDS,
            },
        },
    },
]
