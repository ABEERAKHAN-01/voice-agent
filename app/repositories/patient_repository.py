"""
Repository layer: the ONLY place that talks SQLAlchemy/SQL. Services never
build queries directly -- this keeps persistence swappable and testable.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient


class PatientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Patient:
        patient = Patient(**data)
        self.db.add(patient)
        await self.db.commit()
        await self.db.refresh(patient)
        return patient

    async def get_by_id(self, patient_id: uuid.UUID, include_deleted: bool = False) -> Patient | None:
        stmt = select(Patient).where(Patient.patient_id == patient_id)
        if not include_deleted:
            stmt = stmt.where(Patient.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone_number: str) -> Patient | None:
        stmt = select(Patient).where(
            Patient.phone_number == phone_number, Patient.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        last_name: str | None = None,
        date_of_birth: date | None = None,
        phone_number: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Patient]:
        stmt = select(Patient).where(Patient.deleted_at.is_(None))
        if last_name:
            stmt = stmt.where(Patient.last_name.ilike(last_name))
        if date_of_birth:
            stmt = stmt.where(Patient.date_of_birth == date_of_birth)
        if phone_number:
            stmt = stmt.where(Patient.phone_number == phone_number)
        stmt = stmt.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, patient: Patient, data: dict) -> Patient:
        for key, value in data.items():
            setattr(patient, key, value)
        await self.db.commit()
        await self.db.refresh(patient)
        return patient

    async def soft_delete(self, patient: Patient) -> Patient:
        patient.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(patient)
        return patient
