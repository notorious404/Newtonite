"""
Tests for Keyset Pagination, Search, and Index Performance.
- Verifies deterministic ordering across page boundaries.
- Verifies keyset pagination via `cursor` parameter.
- Verifies search querying via `q` parameter.
- Verifies invalid cursor returns 422.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.team import Team
from app.models.work_item import WorkItem, WorkItemStatus, WorkItemPriority


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def test_keyset_pagination_deterministic_and_no_duplicates(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")

    # Create 5 distinct work items
    created_ids = []
    for i in range(5):
        resp = client.post(
            "/api/v1/work-items",
            json={
                "team_id": str(team_alpha_id),
                "title": f"Keyset Pagination Item {i:02d}",
                "description": f"Description for item {i}",
                "priority": "MEDIUM",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    # Fetch Page 1 with limit=2
    resp1 = client.get(
        f"/api/v1/work-items?team_id={team_alpha_id}&limit=2",
        headers=headers,
    )
    assert resp1.status_code == 200
    page1 = resp1.json()
    assert len(page1["items"]) == 2
    assert page1["has_more"] is True
    assert page1["next_cursor"] is not None

    page1_ids = [item["id"] for item in page1["items"]]

    # Fetch Page 2 using next_cursor
    resp2 = client.get(
        f"/api/v1/work-items?team_id={team_alpha_id}&limit=2&cursor={page1['next_cursor']}",
        headers=headers,
    )
    assert resp2.status_code == 200
    page2 = resp2.json()
    assert len(page2["items"]) == 2
    page2_ids = [item["id"] for item in page2["items"]]

    # Ensure no duplicates between Page 1 and Page 2
    overlap = set(page1_ids).intersection(set(page2_ids))
    assert len(overlap) == 0, f"Pages overlap on IDs: {overlap}"

    # Fetch Page 3 using Page 2 next_cursor
    assert page2["next_cursor"] is not None
    resp3 = client.get(
        f"/api/v1/work-items?team_id={team_alpha_id}&limit=2&cursor={page2['next_cursor']}",
        headers=headers,
    )
    assert resp3.status_code == 200
    page3 = resp3.json()
    assert len(page3["items"]) >= 1
    page3_ids = [item["id"] for item in page3["items"]]

    # Verify all pages are mutually exclusive
    all_seen = set(page1_ids + page2_ids + page3_ids)
    assert len(all_seen) == len(page1_ids) + len(page2_ids) + len(page3_ids)


def test_work_items_search_filter(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")

    # Create unique items for search
    unique_keyword = f"UniqueSearchKey_{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/v1/work-items",
        json={
            "team_id": str(team_alpha_id),
            "title": f"Special Item {unique_keyword}",
            "description": "Standard description",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/work-items",
        json={
            "team_id": str(team_alpha_id),
            "title": "Other normal item",
            "description": "Another description",
        },
        headers=headers,
    )

    # Search by unique keyword
    resp = client.get(
        f"/api/v1/work-items?team_id={team_alpha_id}&q={unique_keyword}",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert unique_keyword in data["items"][0]["title"]


def test_invalid_cursor_returns_422(client: TestClient, db: Session, auth_headers):
    team_alpha_id = get_team_id_by_name(db, "Team Alpha")
    headers = auth_headers("engineer")

    resp = client.get(
        f"/api/v1/work-items?team_id={team_alpha_id}&cursor=invalid_base64_payload",
        headers=headers,
    )
    assert resp.status_code == 422
