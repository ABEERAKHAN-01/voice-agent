"""
REST API for patient records. Thin controllers only -- all logic lives in
PatientService. Every response uses the {data, error} envelope required by
the spec.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import Envelope, PatientCreate, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


def get_service(db: AsyncSession = Depends(get_db)) -> PatientService:
    return PatientService(PatientRepository(db))


@router.get("", response_model=Envelope)
async def list_patients(
    last_name: str | None = Query(default=None),
    date_of_birth: date | None = Query(default=None),
    phone_number: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    service: PatientService = Depends(get_service),
):
    patients = await service.list_patients(last_name, date_of_birth, phone_number, limit, offset)
    return Envelope(data=[p.model_dump(mode="json") for p in patients], error=None)


@router.get("/{patient_id}", response_model=Envelope)
async def get_patient(patient_id: uuid.UUID, service: PatientService = Depends(get_service)):
    patient = await service.get_patient(patient_id)
    return Envelope(data=patient.model_dump(mode="json"), error=None)


@router.post("", response_model=Envelope, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, service: PatientService = Depends(get_service)):
    try:
        patient = await service.create_patient(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return Envelope(data=patient.model_dump(mode="json"), error=None)


@router.put("/{patient_id}", response_model=Envelope)
async def update_patient(
    patient_id: uuid.UUID, payload: PatientUpdate, service: PatientService = Depends(get_service)
):
    patient = await service.update_patient(patient_id, payload)
    return Envelope(data=patient.model_dump(mode="json"), error=None)


@router.delete("/{patient_id}", response_model=Envelope)
async def delete_patient(patient_id: uuid.UUID, service: PatientService = Depends(get_service)):
    await service.delete_patient(patient_id)
    return Envelope(data={"patient_id": str(patient_id), "soft_deleted": True}, error=None)
