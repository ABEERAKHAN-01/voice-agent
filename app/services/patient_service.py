"""
Service layer: business logic sits here, orchestrating the repository and
cache. Both the REST API and the Vapi webhook call into this same layer so
behavior (validation, caching, duplicate detection) is identical regardless
of entry point.
"""
import uuid
from datetime import date

import structlog
from fastapi import HTTPException, status

from app.redis_client import cache_delete, cache_get, cache_set
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate

log = structlog.get_logger()


class PatientService:
    def __init__(self, repo: PatientRepository):
        self.repo = repo

    async def create_patient(self, payload: PatientCreate) -> PatientRead:
        patient = await self.repo.create(payload.model_dump())
        log.info("patient_created", patient_id=str(patient.patient_id), phone=patient.phone_number)
        await cache_delete(f"patient:phone:{patient.phone_number}")
        return PatientRead.model_validate(patient)

    async def get_patient(self, patient_id: uuid.UUID) -> PatientRead:
        cache_key = f"patient:id:{patient_id}"
        cached = await cache_get(cache_key)
        if cached:
            return PatientRead.model_validate(cached)

        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        result = PatientRead.model_validate(patient)
        await cache_set(cache_key, result.model_dump(mode="json"))
        return result

    async def find_by_phone(self, phone_number: str) -> PatientRead | None:
        """Used both by GET /patients?phone_number= and by the Vapi duplicate-
        detection tool call at the start of a conversation."""
        cache_key = f"patient:phone:{phone_number}"
        cached = await cache_get(cache_key)
        if cached:
            return PatientRead.model_validate(cached)

        patient = await self.repo.get_by_phone(phone_number)
        if not patient:
            return None
        result = PatientRead.model_validate(patient)
        await cache_set(cache_key, result.model_dump(mode="json"))
        return result

    async def list_patients(
        self,
        last_name: str | None = None,
        date_of_birth: date | None = None,
        phone_number: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PatientRead]:
        patients = await self.repo.list(last_name, date_of_birth, phone_number, limit, offset)
        return [PatientRead.model_validate(p) for p in patients]

    async def update_patient(self, patient_id: uuid.UUID, payload: PatientUpdate) -> PatientRead:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        data = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update(patient, data)
        log.info("patient_updated", patient_id=str(patient_id), fields=list(data.keys()))

        await cache_delete(f"patient:id:{patient_id}", f"patient:phone:{updated.phone_number}")
        return PatientRead.model_validate(updated)

    async def delete_patient(self, patient_id: uuid.UUID) -> None:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        await self.repo.soft_delete(patient)
        log.info("patient_soft_deleted", patient_id=str(patient_id))
        await cache_delete(f"patient:id:{patient_id}", f"patient:phone:{patient.phone_number}")

    async def register_or_flag_duplicate(self, payload: PatientCreate) -> dict:
        """
        Core bonus requirement: if phone_number already matches an existing
        patient, do NOT silently create a duplicate -- return a signal the
        voice agent uses to ask the caller if they want to update instead.
        """
        existing = await self.find_by_phone(payload.phone_number)
        if existing:
            return {
                "duplicate": True,
                "existing_patient": existing.model_dump(mode="json"),
            }
        created = await self.create_patient(payload)
        return {"duplicate": False, "patient": created.model_dump(mode="json")}
