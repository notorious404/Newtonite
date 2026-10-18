from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.services.auth_service import auth_service


def test_login_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@newtonite.io", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_invalid_password(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@newtonite.io", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@newtonite.io", "password": "Password123!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_protected_endpoints_reject_unauthenticated(client: TestClient):
    # Test auth/me
    resp_me = client.get("/api/v1/auth/me")
    assert resp_me.status_code == 401

    # Test teams
    resp_teams = client.get("/api/v1/teams")
    assert resp_teams.status_code == 401

    # Test work-items
    resp_items = client.get("/api/v1/work-items")
    assert resp_items.status_code == 401


def test_protected_endpoint_rejects_invalid_token(client: TestClient):
    headers = {"Authorization": "Bearer invalid.fake.token"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_get_current_user_profile(client: TestClient, auth_headers):
    headers = auth_headers("engineer")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "engineer@newtonite.io"
    assert data["name"] == "Charlie Engineer"
    assert "hashed_password" not in data
    assert len(data["memberships"]) >= 1
    # Verify Charlie Engineer is in Team Alpha as Member
    alpha_membership = next(m for m in data["memberships"] if m["team_name"] == "Team Alpha")
    assert alpha_membership["role"] == "Member"


def test_list_teams_for_authenticated_user(client: TestClient, auth_headers):
    # Charlie Engineer is only in Team Alpha
    headers = auth_headers("engineer")
    response = client.get("/api/v1/teams", headers=headers)
    assert response.status_code == 200
    teams = response.json()
    team_names = [t["team_name"] for t in teams]
    assert "Team Alpha" in team_names
    assert "Team Beta" not in team_names

    # Oscar Outsider is only in Team Beta
    headers_outsider = auth_headers("outsider")
    response_outsider = client.get("/api/v1/teams", headers=headers_outsider)
    assert response_outsider.status_code == 200
    teams_outsider = response_outsider.json()
    team_names_outsider = [t["team_name"] for t in teams_outsider]
    assert "Team Beta" in team_names_outsider
    assert "Team Alpha" not in team_names_outsider

    # Alice Admin is in both Team Alpha and Team Beta
    headers_admin = auth_headers("admin")
    response_admin = client.get("/api/v1/teams", headers=headers_admin)
    assert response_admin.status_code == 200
    teams_admin = response_admin.json()
    team_names_admin = [t["team_name"] for t in teams_admin]
    assert "Team Alpha" in team_names_admin
    assert "Team Beta" in team_names_admin


def test_inactive_user_cannot_access(client: TestClient, db: Session, tokens):
    user = auth_service.get_user_by_email(db, "engineer@newtonite.io")
    assert user is not None
    user.is_active = False
    db.commit()

    headers = {"Authorization": f"Bearer {tokens['engineer']}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_demo_seed_idempotency(db: Session):
    # Running seed multiple times produces no errors and does not create duplicate users
    res1 = auth_service.seed_demo_data(db)
    res2 = auth_service.seed_demo_data(db)
    assert res1["status"] == "seeded"
    assert res2["status"] == "seeded"

    # Verify user count remains 5
    users = list(db.scalars(select(User)).all())
    assert len(users) == 5
