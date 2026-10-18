import concurrent.futures
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.team import Team
from app.models.user import User
from app.models.work_item import WorkItem, WorkItemStatus
from app.models.activity_event import ActivityEvent, ActivityEventType
from app.core.security import create_access_token
from app.services.work_item_service import work_item_service, WorkItemConflict
from tests.conftest import test_engine, TestingSessionLocal


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def test_claim_work_item_success(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")

    # Create an OPEN item
    create_resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Claimable task"},
        headers=headers_eng,
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    # Claim the item
    claim_resp = client.post(f"/api/v1/work-items/{item_id}/claim", headers=headers_eng)
    assert claim_resp.status_code == 200
    data = claim_resp.json()
    assert data["status"] == WorkItemStatus.IN_PROGRESS
    assert data["version"] == 2
    assert data["assignee_id"] is not None

    # Verify activity event recorded
    events = list(db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.item_id == uuid.UUID(item_id))
        .order_by(ActivityEvent.created_at.asc())
    ).all())
    assert len(events) == 2
    assert events[1].type == ActivityEventType.CLAIMED
    assert events[1].from_value == WorkItemStatus.OPEN
    assert events[1].to_value == WorkItemStatus.IN_PROGRESS


def test_claim_already_claimed_conflict(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")
    headers_lead = auth_headers("lead")

    create_resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Double claim task"},
        headers=headers_eng,
    )
    item_id = create_resp.json()["id"]

    # First claim succeeds
    resp1 = client.post(f"/api/v1/work-items/{item_id}/claim", headers=headers_eng)
    assert resp1.status_code == 200

    # Second claim returns 409 Conflict
    resp2 = client.post(f"/api/v1/work-items/{item_id}/claim", headers=headers_lead)
    assert resp2.status_code == 409
    assert "could not be claimed" in resp2.json()["detail"].lower()


def test_claim_viewer_forbidden(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")
    headers_viewer = auth_headers("viewer")

    create_resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Viewer claim attempt"},
        headers=headers_eng,
    )
    item_id = create_resp.json()["id"]

    # Viewer cannot claim
    resp = client.post(f"/api/v1/work-items/{item_id}/claim", headers=headers_viewer)
    assert resp.status_code == 403


def test_claim_non_member_forbidden(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")
    headers_outsider = auth_headers("outsider")

    create_resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Outsider claim attempt"},
        headers=headers_eng,
    )
    item_id = create_resp.json()["id"]

    # Outsider cannot claim Team Alpha item
    resp = client.post(f"/api/v1/work-items/{item_id}/claim", headers=headers_outsider)
    assert resp.status_code == 403


def test_claim_non_existent_item_404(client: TestClient, auth_headers):
    headers_eng = auth_headers("engineer")
    random_id = str(uuid.uuid4())
    resp = client.post(f"/api/v1/work-items/{random_id}/claim", headers=headers_eng)
    assert resp.status_code == 404


def test_concurrent_claims_exactly_one_succeeds():
    """
    Stress concurrency test:
    Spawns 10 parallel threads each with an independent PostgreSQL session,
    attempting to atomically claim the exact same OPEN work item at the same instant.
    Must result in exactly 1 successful claim and exactly 9 WorkItemConflict exceptions.
    """
    setup_session = TestingSessionLocal()
    from app.services.auth_service import auth_service
    auth_service.seed_demo_data(setup_session)

    team_alpha = setup_session.scalar(select(Team).where(Team.name == "Team Alpha"))
    eng_user = setup_session.scalar(select(User).where(User.email == "engineer@newtonite.io"))
    assert team_alpha is not None
    assert eng_user is not None

    item = WorkItem(
        team_id=team_alpha.id,
        title="Concurrent race condition claim test",
        status=WorkItemStatus.OPEN,
        assignee_id=None,
        created_by=eng_user.id,
        version=1,
    )
    setup_session.add(item)
    setup_session.commit()
    target_item_id = item.id
    target_user_id = eng_user.id
    setup_session.close()

    # Function executed concurrently across 10 threads
    def attempt_claim(worker_idx: int) -> str:
        worker_session = TestingSessionLocal()
        try:
            work_item_service.claim_work_item(
                worker_session,
                user_id=target_user_id,
                item_id=target_item_id,
            )
            worker_session.commit()
            return "SUCCESS"
        except WorkItemConflict:
            return "CONFLICT"
        finally:
            worker_session.close()

    # Launch 10 concurrent requests simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_claim, i) for i in range(10)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r == "SUCCESS"]
    conflicts = [r for r in results if r == "CONFLICT"]

    assert len(successes) == 1, f"Expected exactly 1 successful claim, got {len(successes)}: {results}"
    assert len(conflicts) == 9, f"Expected exactly 9 conflicts, got {len(conflicts)}: {results}"

