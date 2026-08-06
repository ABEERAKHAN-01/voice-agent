"""
Pydantic v2 schemas. These are the SOURCE OF TRUTH for validation — the
spec requires server-side validation regardless of what the voice agent
already checked conversationally.
"""
import re
import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

NAME_RE = re.compile(r"^[A-Za-z\-']{1,50}$")
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


class Sex(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


def _digits_only(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _validate_name(v: str) -> str:
    if not NAME_RE.match(v):
        raise ValueError("Names must be 1-50 alphabetic characters, hyphens, or apostrophes")
    return v


def _validate_dob(v: date) -> date:
    if v > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    if v.year < 1900:
        raise ValueError("date_of_birth is not plausible")
    return v


def _validate_phone(v: str, field_name: str = "phone_number") -> str:
    digits = _digits_only(v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(f"{field_name} must be a valid 10-digit US phone number")
    return digits


def _validate_state(v: str) -> str:
    v = v.strip().upper()
    if v not in US_STATES:
        raise ValueError("state must be a valid 2-letter US state abbreviation")
    return v


def _validate_zip(v: str) -> str:
    v = v.strip()
    if not re.match(r"^\d{5}(-\d{4})?$", v):
        raise ValueError("zip_code must be in 5-digit or ZIP+4 format")
    return v


class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: EmailStr | None = None
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: str | None = None
    city: str = Field(..., min_length=1, max_length=100)
    state: str
    zip_code: str
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_name(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        return _validate_dob(v)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v, field_name="phone_number")

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return _validate_phone(v, field_name="emergency_contact_phone")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        return _validate_state(v)

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        return _validate_zip(v)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional -> supports PATCH-style partial updates via PUT."""
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        return v if v is None else _validate_name(v)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        return v if v is None else _validate_dob(v)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return v if v is None else _validate_phone(v, field_name="phone_number")

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: str | None) -> str | None:
        return None if not v else _validate_phone(v, field_name="emergency_contact_phone")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        return v if v is None else _validate_state(v)

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str | None) -> str | None:
        return v if v is None else _validate_zip(v)


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class Envelope(BaseModel):
    """Consistent API response envelope required by the spec."""
    data: object | None = None
    error: str | None = None
