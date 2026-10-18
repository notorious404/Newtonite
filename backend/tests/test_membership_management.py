"""
Tests for Admin-only membership management endpoints:
  POST   /api/v1/teams/{team_id}/members
  DELETE /api/v1/teams/{team_id}/members/{user_id}

Role matrix enforced:
  Admin -> add/remove members (success)
  Lead  -> 403
  Member -> 403
  Viewer -> 403
  Non-member -> 403
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.team import Team
from app.models.user import User
from app.models.membership import Membership, MembershipRole
from app.services.auth_service import auth_service


def get_team_id_by_name(db: Session, name: str) -> uuid.UUID:
    team = db.scalar(select(Team).where(Team.name == name))
    assert team is not None
    return team.id


def get_user_id_by_email(db: Session, email: str) -> uuid.UUID:
    user = auth_service.get_user_by_email(db, email)
    assert user is not None
    return user.id


# ─── Add member ──────────────────────────────────────────────────────────────

def test_admin_can_add_member(client: TestClient, db: Session, auth_headers):
    """Admin adds outsider (non-member) to Team Alpha as Member."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    outsider_id = get_user_id_by_email(db, "outsider@newtonite.io")

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": str(outsider_id), "role": MembershipRole.MEMBER},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == str(outsider_id)
    assert data["team_id"] == str(team_id)
    assert data["role"] == MembershipRole.MEMBER

    # Verify membership is in the database
    m = db.scalar(
        select(Membership).where(
            Membership.team_id == team_id,
            Membership.user_id == outsider_id,
        )
    )
    assert m is not None


def test_lead_cannot_add_member(client: TestClient, db: Session, auth_headers):
    """Lead cannot add members — only Admin may."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    outsider_id = get_user_id_by_email(db, "outsider@newtonite.io")

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": str(outsider_id), "role": MembershipRole.MEMBER},
        headers=auth_headers("lead"),
    )
    assert resp.status_code == 403


def test_member_cannot_add_member(client: TestClient, db: Session, auth_headers):
    """Regular Member cannot add members."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    outsider_id = get_user_id_by_email(db, "outsider@newtonite.io")

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": str(outsider_id), "role": MembershipRole.MEMBER},
        headers=auth_headers("engineer"),
    )
    assert resp.status_code == 403


def test_add_member_invalid_role_returns_422(client: TestClient, db: Session, auth_headers):
    """Admin supplying an invalid role string gets 422."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    outsider_id = get_user_id_by_email(db, "outsider@newtonite.io")

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": str(outsider_id), "role": "SUPERUSER"},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 422


def test_add_member_nonexistent_user_returns_404(client: TestClient, db: Session, auth_headers):
    """Admin adding a non-existent user UUID gets 404."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    fake_user_id = str(uuid.uuid4())

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": fake_user_id, "role": MembershipRole.MEMBER},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 404


def test_add_duplicate_member_returns_409(client: TestClient, db: Session, auth_headers):
    """Adding someone who is already a member returns 409."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    # engineer is already a member of Team Alpha
    engineer_id = get_user_id_by_email(db, "engineer@newtonite.io")

    resp = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": str(engineer_id), "role": MembershipRole.MEMBER},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 409


# ─── Remove member ────────────────────────────────────────────────────────────

def test_admin_can_remove_member(client: TestClient, db: Session, auth_headers):
    """Admin removes the viewer from Team Alpha."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    viewer_id = get_user_id_by_email(db, "viewer@newtonite.io")

    resp = client.delete(
        f"/api/v1/teams/{team_id}/members/{viewer_id}",
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 204

    # Confirm the membership is gone
    m = db.scalar(
        select(Membership).where(
            Membership.team_id == team_id,
            Membership.user_id == viewer_id,
        )
    )
    assert m is None


def test_admin_cannot_remove_themselves(client: TestClient, db: Session, auth_headers):
    """Admin cannot remove themselves (guard against accidental team lock-out)."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    admin_id = get_user_id_by_email(db, "admin@newtonite.io")

    resp = client.delete(
        f"/api/v1/teams/{team_id}/members/{admin_id}",
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 409


def test_lead_cannot_remove_member(client: TestClient, db: Session, auth_headers):
    """Lead cannot remove members — only Admin may."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    viewer_id = get_user_id_by_email(db, "viewer@newtonite.io")

    resp = client.delete(
        f"/api/v1/teams/{team_id}/members/{viewer_id}",
        headers=auth_headers("lead"),
    )
    assert resp.status_code == 403


def test_remove_nonexistent_membership_returns_404(client: TestClient, db: Session, auth_headers):
    """Removing a user who is not a member returns 404."""
    team_id = get_team_id_by_name(db, "Team Alpha")
    outsider_id = get_user_id_by_email(db, "outsider@newtonite.io")

    resp = client.delete(
        f"/api/v1/teams/{team_id}/members/{outsider_id}",
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 404
