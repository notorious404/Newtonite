import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.team import Team
from app.models.work_item import WorkItem, WorkItemStatus
from app.models.activity_event import ActivityEvent, ActivityEventType


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def test_create_work_item_success(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")  # Member in Team Alpha

    payload = {
        "team_id": str(team_alpha_id),
        "title": "Build user authentication",
        "description": "Implement JWT and bcrypt authentication",
        "type": "TASK",
        "priority": "HIGH",
    }
    response = client.post("/api/v1/work-items", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Build user authentication"
    assert data["status"] == WorkItemStatus.OPEN
    assert data["version"] == 1
    assert data["priority"] == "HIGH"
    assert data["type"] == "TASK"

    item_id = uuid.UUID(data["id"])

    # Verify item persisted in database
    item_in_db = db.scalar(select(WorkItem).where(WorkItem.id == item_id))
    assert item_in_db is not None
    assert item_in_db.title == "Build user authentication"
    assert item_in_db.status == WorkItemStatus.OPEN
    assert item_in_db.version == 1

    # Verify initial activity event was persisted in same transaction
    events = list(db.scalars(select(ActivityEvent).where(ActivityEvent.item_id == item_id)).all())
    assert len(events) == 1
    assert events[0].type == ActivityEventType.CREATED
    assert events[0].to_value == WorkItemStatus.OPEN
    assert events[0].payload["title"] == "Build user authentication"


def test_create_work_item_viewer_forbidden(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("viewer")  # Viewer role in Team Alpha

    payload = {
        "team_id": str(team_alpha_id),
        "title": "Unauthorized attempt",
        "description": "Viewer cannot create items",
    }
    response = client.post("/api/v1/work-items", json=payload, headers=headers)
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_create_work_item_non_member_forbidden(client: TestClient, db: Session, auth_headers):
    team_beta_id = get_team_id_by_name(db, "Team Beta")
    headers = auth_headers("engineer")  # Engineer is in Team Alpha, NOT in Team Beta

    payload = {
        "team_id": str(team_beta_id),
        "title": "Cross-team unauthorized attempt",
    }
    response = client.post("/api/v1/work-items", json=payload, headers=headers)
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_create_work_item_invalid_payload(client: TestClient, db: Session, auth_headers):
    headers = auth_headers("engineer")

    # Missing title
    response = client.post(
        "/api/v1/work-items",
        json={"team_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 422

    # Empty title
    response_empty = client.post(
        "/api/v1/work-items",
        json={"team_id": str(uuid.uuid4()), "title": ""},
        headers=headers,
    )
    assert response_empty.status_code == 422


def test_list_work_items_isolation(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    team_beta_id = get_team_id_by_name(db, "Team Beta")

    # Create an item in Team Alpha by Engineer
    headers_eng = auth_headers("engineer")
    resp_alpha = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Alpha Task"},
        headers=headers_eng,
    )
    assert resp_alpha.status_code == 201

    # Create an item in Team Beta by Outsider
    headers_outsider = auth_headers("outsider")
    resp_beta = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_beta_id), "title": "Beta Task"},
        headers=headers_outsider,
    )
    assert resp_beta.status_code == 201

    # 1. Engineer lists work items (should only see Alpha Task, never Beta Task)
    list_eng = client.get("/api/v1/work-items", headers=headers_eng)
    assert list_eng.status_code == 200
    eng_items = list_eng.json()["items"]
    titles_eng = [it["title"] for it in eng_items]
    assert "Alpha Task" in titles_eng
    assert "Beta Task" not in titles_eng

    # 2. Outsider lists work items (should only see Beta Task, never Alpha Task)
    list_out = client.get("/api/v1/work-items", headers=headers_outsider)
    assert list_out.status_code == 200
    out_items = list_out.json()["items"]
    titles_out = [it["title"] for it in out_items]
    assert "Beta Task" in titles_out
    assert "Alpha Task" not in titles_out

    # 3. Engineer attempts to filter by Team Beta explicitly -> returns 403 Forbidden
    cross_filter = client.get(
        f"/api/v1/work-items?team_id={team_beta_id}",
        headers=headers_eng,
    )
    assert cross_filter.status_code == 403
    assert "permission" in cross_filter.json()["detail"].lower()


def test_get_work_item_and_activity_isolation(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")

    # Create an item in Team Alpha
    headers_eng = auth_headers("engineer")
    resp = client.post(
        "/api/v1/work-items",
        json={"team_id": str(team_alpha_id), "title": "Alpha Secret Task"},
        headers=headers_eng,
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Member in Team Alpha can retrieve the item
    get_resp = client.get(f"/api/v1/work-items/{item_id}", headers=headers_eng)
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Alpha Secret Task"

    # Member in Team Alpha can retrieve activity history
    activity_resp = client.get(f"/api/v1/work-items/{item_id}/activity", headers=headers_eng)
    assert activity_resp.status_code == 200
    events = activity_resp.json()["items"]
    assert len(events) == 1
    assert events[0]["type"] == ActivityEventType.CREATED
    assert events[0]["to_value"] == WorkItemStatus.OPEN

    # Outsider (Team Beta only) cannot retrieve the item -> returns 403 Forbidden
    headers_outsider = auth_headers("outsider")
    forbidden_resp = client.get(f"/api/v1/work-items/{item_id}", headers=headers_outsider)
    assert forbidden_resp.status_code == 403

    # Outsider cannot retrieve the item's activity history -> returns 403 Forbidden
    forbidden_act = client.get(f"/api/v1/work-items/{item_id}/activity", headers=headers_outsider)
    assert forbidden_act.status_code == 403

    # Non-existent item returns 404
    non_existent = str(uuid.uuid4())
    not_found_resp = client.get(f"/api/v1/work-items/{non_existent}", headers=headers_eng)
    assert not_found_resp.status_code == 404
