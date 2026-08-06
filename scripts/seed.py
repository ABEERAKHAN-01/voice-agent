"""Seeds 2 demo patient records. Run: python scripts/seed.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.repositories.patient_repository import PatientRepository  # noqa: E402
from app.schemas.patient import PatientCreate  # noqa: E402

SEED_PATIENTS = [
    PatientCreate(
        first_name="Jane", last_name="Doe", date_of_birth="1985-03-12", sex="Female",
        phone_number="5125550111", email="jane.doe@example.com",
        address_line_1="123 Main St", city="Austin", state="TX", zip_code="78701",
        preferred_language="English",
    ),
    PatientCreate(
        first_name="Miguel", last_name="Santos", date_of_birth="1979-11-02", sex="Male",
        phone_number="7135550199", address_line_1="456 Oak Ave", city="Houston",
        state="TX", zip_code="77002", preferred_language="Spanish",
    ),
]


async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        repo = PatientRepository(db)
        for p in SEED_PATIENTS:
            existing = await repo.get_by_phone(p.phone_number)
            if existing:
                print(f"Skipping {p.first_name} {p.last_name}, already seeded.")
                continue
            created = await repo.create(p.model_dump())
            print(f"Seeded {created.first_name} {created.last_name} -> {created.patient_id}")


if __name__ == "__main__":
    asyncio.run(main())
