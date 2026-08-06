"""
Integration tests for the patient REST API. Uses an isolated in-memory
SQLite DB (async, via aiosqlite) so tests don't require a running Postgres.
Install `aiosqlite` locally to run these (not needed in production).
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def client():
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestSession = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


VALID_PATIENT = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1990-05-14",
    "sex": "Female",
    "phone_number": "5125550111",
    "address_line_1": "123 Main St",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
}


@pytest.mark.asyncio
async def test_create_and_get_patient(client: AsyncClient):
    resp = await client.post("/patients", json=VALID_PATIENT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["error"] is None
    patient_id = body["data"]["patient_id"]

    resp2 = await client.get(f"/patients/{patient_id}")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_rejects_future_dob(client: AsyncClient):
    bad = {**VALID_PATIENT, "date_of_birth": "2999-01-01"}
    resp = await client.post("/patients", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_invalid_phone(client: AsyncClient):
    bad = {**VALID_PATIENT, "phone_number": "123"}
    resp = await client.post("/patients", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_and_filter_by_last_name(client: AsyncClient):
    await client.post("/patients", json=VALID_PATIENT)
    resp = await client.get("/patients", params={"last_name": "Doe"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_update_patient_partial(client: AsyncClient):
    created = (await client.post("/patients", json=VALID_PATIENT)).json()["data"]
    resp = await client.put(f"/patients/{created['patient_id']}", json={"city": "Dallas"})
    assert resp.status_code == 200
    assert resp.json()["data"]["city"] == "Dallas"
    assert resp.json()["data"]["last_name"] == "Doe"  # untouched fields preserved


@pytest.mark.asyncio
async def test_soft_delete_patient(client: AsyncClient):
    created = (await client.post("/patients", json=VALID_PATIENT)).json()["data"]
    resp = await client.delete(f"/patients/{created['patient_id']}")
    assert resp.status_code == 200

    resp2 = await client.get(f"/patients/{created['patient_id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_patient_404(client: AsyncClient):
    resp = await client.get("/patients/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
