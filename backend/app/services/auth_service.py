from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.models.team import Team
from app.models.membership import Membership, MembershipRole
from app.core.security import verify_password, get_password_hash, create_access_token


class AuthService:
    @staticmethod
    def authenticate_user(
        db: Session,
        *,
        email: str,
        password: str,
    ) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower().strip())
        user = db.scalar(stmt)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: Any) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return db.scalar(stmt)

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.lower().strip())
        return db.scalar(stmt)

    @staticmethod
    def seed_demo_data(db: Session) -> Dict[str, Any]:
        """
        Idempotent seeding of demo teams, users and memberships.
        Does not duplicate or overwrite existing production records.
        """
        # 1. Seed Teams
        demo_teams_data = [
            {"name": "Team Alpha"},
            {"name": "Team Beta"},
        ]
        teams_map = {}
        for t_data in demo_teams_data:
            stmt = select(Team).where(Team.name == t_data["name"])
            team = db.scalar(stmt)
            if not team:
                team = Team(name=t_data["name"])
                db.add(team)
                db.flush()
            teams_map[t_data["name"]] = team

        # 2. Seed Users
        demo_password = "Password123!"
        hashed = get_password_hash(demo_password)
        demo_users_data = [
            {"email": "admin@newtonite.io", "name": "Alice Admin"},
            {"email": "lead@newtonite.io", "name": "Bob Lead"},
            {"email": "engineer@newtonite.io", "name": "Charlie Engineer"},
            {"email": "viewer@newtonite.io", "name": "Dana Viewer"},
            {"email": "outsider@newtonite.io", "name": "Oscar Outsider"},
        ]
        users_map = {}
        for u_data in demo_users_data:
            stmt = select(User).where(User.email == u_data["email"].lower())
            user = db.scalar(stmt)
            if not user:
                user = User(
                    name=u_data["name"],
                    email=u_data["email"].lower(),
                    hashed_password=hashed,
                    is_active=True,
                )
                db.add(user)
                db.flush()
            users_map[u_data["email"]] = user

        # 3. Seed Memberships
        memberships_data = [
            # Team Alpha memberships
            {"user": "admin@newtonite.io", "team": "Team Alpha", "role": MembershipRole.ADMIN},
            {"user": "lead@newtonite.io", "team": "Team Alpha", "role": MembershipRole.LEAD},
            {"user": "engineer@newtonite.io", "team": "Team Alpha", "role": MembershipRole.MEMBER},
            {"user": "viewer@newtonite.io", "team": "Team Alpha", "role": MembershipRole.VIEWER},
            # Team Beta memberships
            {"user": "admin@newtonite.io", "team": "Team Beta", "role": MembershipRole.ADMIN},
            {"user": "outsider@newtonite.io", "team": "Team Beta", "role": MembershipRole.MEMBER},
        ]

        for m_data in memberships_data:
            user = users_map[m_data["user"]]
            team = teams_map[m_data["team"]]
            stmt = select(Membership).where(
                Membership.user_id == user.id,
                Membership.team_id == team.id,
            )
            membership = db.scalar(stmt)
            if not membership:
                membership = Membership(
                    user_id=user.id,
                    team_id=team.id,
                    role=m_data["role"],
                )
                db.add(membership)

        db.commit()
        return {
            "teams": list(teams_map.keys()),
            "users": list(users_map.keys()),
            "status": "seeded",
        }


auth_service = AuthService()
