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
from app.services.work_item_service import work_item_service, WorkItemConflict
from tests.conftest import test_engine, TestingSessionLocal


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def test_transition_success(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")

    # 1. Create item in OPEN status (version 1)
    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Transition test item"},
        headers=headers_eng,
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]
    assert resp.json()["version"] == 1
    assert resp.json()["status"] == WorkItemStatus.OPEN

    # 2. Transition OPEN -> IN_PROGRESS with version 1
    trans_resp = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.IN_PROGRESS, "version": 1},
        headers=headers_eng,
    )
    assert trans_resp.status_code == 200
    data = trans_resp.json()
    assert data["status"] == WorkItemStatus.IN_PROGRESS
    assert data["version"] == 2

    # Verify event written
    events = list(db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.item_id == uuid.UUID(item_id))
        .order_by(ActivityEvent.created_at.asc())
    ).all())
    assert len(events) == 2
    assert events[1].type == ActivityEventType.STATUS_CHANGED
    assert events[1].from_value == WorkItemStatus.OPEN
    assert events[1].to_value == WorkItemStatus.IN_PROGRESS


def test_transition_stale_version_409(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")

    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Stale version test"},
        headers=headers_eng,
    )
    item_id = resp.json()["id"]

    # Provide stale expected version 99
    trans_resp = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.IN_PROGRESS, "version": 99},
        headers=headers_eng,
    )
    assert trans_resp.status_code == 409
    assert "version conflict" in trans_resp.json()["detail"].lower()


def test_transition_invalid_workflow_target_409(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")

    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Illegal transition"},
        headers=headers_eng,
    )
    item_id = resp.json()["id"]

    # Attempt illegal jump: OPEN -> RESOLVED
    trans_resp = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.RESOLVED, "version": 1},
        headers=headers_eng,
    )
    assert trans_resp.status_code == 409
    assert "not allowed" in trans_resp.json()["detail"].lower()


def test_transition_separation_of_duties_self_approval_forbidden(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_lead = auth_headers("lead")

    # Lead creates an item
    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Lead item"},
        headers=headers_lead,
    )
    item_id = resp.json()["id"]

    # Lead moves OPEN -> IN_PROGRESS
    r1 = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.IN_PROGRESS, "version": 1},
        headers=headers_lead,
    )
    assert r1.status_code == 200

    # Lead moves IN_PROGRESS -> AWAITING_APPROVAL
    r2 = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.AWAITING_APPROVAL, "version": 2},
        headers=headers_lead,
    )
    assert r2.status_code == 200

    # Lead attempts to approve own item (AWAITING_APPROVAL -> RESOLVED)
    r3 = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.RESOLVED, "version": 3},
        headers=headers_lead,
    )
    assert r3.status_code == 403
    assert "separation of duties" in r3.json()["detail"].lower()


def test_transition_approval_by_different_admin_succeeds(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")
    headers_lead = auth_headers("lead")

    # Engineer creates the item
    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Engineer item to approve"},
        headers=headers_eng,
    )
    item_id = resp.json()["id"]

    # Move to IN_PROGRESS then AWAITING_APPROVAL
    client.post(f"/api/v1/work-items/{item_id}/transition", json={"to_status": WorkItemStatus.IN_PROGRESS, "version": 1}, headers=headers_eng)
    client.post(f"/api/v1/work-items/{item_id}/transition", json={"to_status": WorkItemStatus.AWAITING_APPROVAL, "version": 2}, headers=headers_eng)

    # Lead approves (different user than creator)
    appr_resp = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.RESOLVED, "version": 3},
        headers=headers_lead,
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == WorkItemStatus.RESOLVED
    assert appr_resp.json()["version"] == 4


def test_transition_viewer_forbidden(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers_eng = auth_headers("engineer")
    headers_viewer = auth_headers("viewer")

    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Item for viewer check"},
        headers=headers_eng,
    )
    item_id = resp.json()["id"]

    resp_viewer = client.post(
        f"/api/v1/work-items/{item_id}/transition",
        json={"to_status": WorkItemStatus.IN_PROGRESS, "version": 1},
        headers=headers_viewer,
    )
    # Viewer can't modify/create
    # Note: can_view is allowed, but let's check transition role check
    # In work_item_service.py transition_work_item:
    # Let's verify authorization check in transition_work_item
    assert resp_viewer.status_code in {400, 403}


def test_concurrent_conflicting_transitions():
    """
    Two simultaneous requests both attempting to transition an item from version=1:
    exactly one succeeds, the other gets WorkItemConflict (HTTP 409).
    """
    setup_session = TestingSessionLocal()
    from app.services.auth_service import auth_service
    auth_service.seed_demo_data(setup_session)

    team_alpha = setup_session.scalar(select(Team).where(Team.name == "Team Alpha"))
    eng_user = setup_session.scalar(select(User).where(User.email == "engineer@newtonite.io"))

    item = WorkItem(
        team_id=team_alpha.id,
        title="Concurrent transition test item",
        status=WorkItemStatus.OPEN,
        assignee_id=eng_user.id,
        created_by=eng_user.id,
        version=1,
    )
    setup_session.add(item)
    setup_session.commit()
    target_item_id = item.id
    target_user_id = eng_user.id
    setup_session.close()

    def attempt_transition(worker_idx: int) -> str:
        worker_session = TestingSessionLocal()
        try:
            work_item_service.transition_work_item(
                worker_session,
                user_id=target_user_id,
                item_id=target_item_id,
                to_status=WorkItemStatus.IN_PROGRESS,
                expected_version=1,
            )
            worker_session.commit()
            return "SUCCESS"
        except WorkItemConflict:
            return "CONFLICT"
        finally:
            worker_session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_transition, i) for i in range(2)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r == "SUCCESS"]
    conflicts = [r for r in results if r == "CONFLICT"]

    assert len(successes) == 1, f"Expected exactly 1 success, got {results}"
    assert len(conflicts) == 1, f"Expected exactly 1 conflict, got {results}"

