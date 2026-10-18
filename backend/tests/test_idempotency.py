import uuid
import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.team import Team
from app.models.work_item import WorkItem
from app.core.config import settings


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def test_idempotency_same_key_same_body_replays_response(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")
    idem_key = str(uuid.uuid4())
    headers_with_key = {**headers, "Idempotency-Key": idem_key}

    payload = {
        "team_id": str(team_alpha_id),
        "title": "Idempotent Work Item",
        "description": "First attempt",
        "type": "TASK",
        "priority": "HIGH",
    }

    # First request: creates the item
    resp1 = client.post("/api/v1/work-items", json=payload, headers=headers_with_key)
    assert resp1.status_code == 201
    data1 = resp1.json()
    item_id = data1["id"]

    # Second request: identical key and payload -> replays stored response
    resp2 = client.post("/api/v1/work-items", json=payload, headers=headers_with_key)
    assert resp2.status_code in {200, 201}
    data2 = resp2.json()
    assert data2["id"] == item_id
    assert data2["title"] == "Idempotent Work Item"

    # Verify only ONE item was created in the database
    items = list(db.scalars(select(WorkItem).where(WorkItem.title == "Idempotent Work Item")).all())
    assert len(items) == 1


def test_idempotency_same_key_different_body_returns_422(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")
    idem_key = str(uuid.uuid4())
    headers_with_key = {**headers, "Idempotency-Key": idem_key}

    payload1 = {
        "team_id": str(team_alpha_id),
        "title": "Initial Title",
    }
    resp1 = client.post("/api/v1/work-items", json=payload1, headers=headers_with_key)
    assert resp1.status_code == 201

    payload2 = {
        "team_id": str(team_alpha_id),
        "title": "Changed Title Payload",
    }
    resp2 = client.post("/api/v1/work-items", json=payload2, headers=headers_with_key)
    assert resp2.status_code == 422
    assert "different request body" in resp2.json()["detail"].lower()


def test_idempotency_different_users_same_key_succeed_independently(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    shared_key = str(uuid.uuid4())

    headers_eng = {**auth_headers("engineer"), "Idempotency-Key": shared_key}
    headers_lead = {**auth_headers("lead"), "Idempotency-Key": shared_key}

    resp1 = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Engineer task with shared key"},
        headers=headers_eng,
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Lead task with shared key"},
        headers=headers_lead,
    )
    assert resp2.status_code == 201

    # Both succeeded because keys are scoped to user_id
    assert resp1.json()["id"] != resp2.json()["id"]


def test_idempotency_failed_request_can_be_retried(client: TestClient, db: Session, auth_headers):
    team_beta_id = get_team_id_by_name(db, "Team Beta")
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")
    idem_key = str(uuid.uuid4())
    headers_with_key = {**headers, "Idempotency-Key": idem_key}

    # 1. Attempt targeting Team Beta (engineer lacks permission -> 403)
    resp_fail = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_beta_id), "title": "Unauthorized attempt"},
        headers=headers_with_key,
    )
    assert resp_fail.status_code == 403

    # 2. Retry with valid Team Alpha targeting
    # Idempotency key was deleted on failure, so retry with same key succeeds
    resp_retry = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Retry attempt"},
        headers=headers_with_key,
    )
    assert resp_retry.status_code == 201
    assert resp_retry.json()["title"] == "Retry attempt"

def test_idempotency_concurrent_same_key_no_duplicates():
    """
    Concurrent idempotency test (spec §3, test case 3):
    Two parallel threads send POST /api/v1/work-items with the SAME Idempotency-Key
    to the live server (port 8000) simultaneously.

    Expected:
    - Exactly 1 work item is created in the database (no duplicates).
    - Responses are a mix of 201 (create), 200 (replay), or 409 (conflict).
    - NEVER two distinct 201 responses that create two separate items.

    Hits the live running server so each request has its own real TCP connection
    and independent PostgreSQL transaction — the only reliable way to test true
    DB-level race conditions without the ASGI event-loop serialization of TestClient.
    """
    import httpx
    from app.services.auth_service import auth_service
    from app.core.security import create_access_token
    from app.core.config import settings as app_settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    BASE_URL = "http://127.0.0.1:8000"

    # Check if the live server is up; skip gracefully if not
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=3)
        resp.raise_for_status()
    except Exception:
        import pytest
        pytest.skip("Live server not running on port 8000 — skipping concurrent idempotency test")

    prod_engine = create_engine(app_settings.sync_database_url, pool_pre_ping=True)
    ProdSession = sessionmaker(autocommit=False, autoflush=False, bind=prod_engine)

    setup_db = ProdSession()
    auth_service.seed_demo_data(setup_db)

    team = setup_db.scalar(select(Team).where(Team.name == "Team Alpha"))
    assert team is not None, "Team Alpha must be seeded in the production DB"
    team_id = str(team.id)

    eng_user = auth_service.get_user_by_email(setup_db, "engineer@newtonite.io")
    assert eng_user is not None
    token = create_access_token(subject=eng_user.id)
    setup_db.close()

    shared_key = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": shared_key,
    }
    payload = {
        "team_id": team_id,
        "title": f"Concurrent idem test {shared_key[:8]}",
    }

    def send_request(_: int) -> int:
        # Each thread gets its own httpx client (independent TCP connection)
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{BASE_URL}/api/v1/work-items", json=payload, headers=headers)
            return resp.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futs = [executor.submit(send_request, i) for i in range(2)]
        statuses = [f.result() for f in futs]

    # At most one 201 must have been issued — never two distinct creations
    two_o_one_count = statuses.count(201)
    assert two_o_one_count <= 1, (
        f"Both requests returned 201 — duplicate creation detected. Statuses: {statuses}"
    )

    # Verify the DB has exactly one item with this title
    verify_db = ProdSession()
    items = list(verify_db.scalars(
        select(WorkItem).where(WorkItem.title == payload["title"])
    ).all())
    verify_db.close()
    assert len(items) == 1, (
        f"Expected exactly 1 work item in DB, found {len(items)}. Statuses: {statuses}"
    )
