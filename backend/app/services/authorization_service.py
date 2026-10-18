import uuid
from typing import Optional, List, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.membership import Membership, MembershipRole


class AuthorizationService:
    CREATION_ROLES: Set[str] = {
        MembershipRole.MEMBER,
        MembershipRole.LEAD,
        MembershipRole.ADMIN,
    }

    VIEW_ROLES: Set[str] = {
        MembershipRole.VIEWER,
        MembershipRole.MEMBER,
        MembershipRole.LEAD,
        MembershipRole.ADMIN,
    }

    @staticmethod
    def get_user_team_membership(
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> Optional[Membership]:
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.team_id == team_id,
        )
        return db.scalar(stmt)

    @staticmethod
    def get_user_memberships(
        db: Session,
        *,
        user_id: uuid.UUID,
    ) -> List[Membership]:
        stmt = (
            select(Membership)
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_user_team_ids(
        db: Session,
        *,
        user_id: uuid.UUID,
    ) -> List[uuid.UUID]:
        stmt = select(Membership.team_id).where(Membership.user_id == user_id)
        return list(db.scalars(stmt).all())

    @classmethod
    def can_view_team(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        membership = cls.get_user_team_membership(db, user_id=user_id, team_id=team_id)
        return membership is not None and membership.role in cls.VIEW_ROLES

    @classmethod
    def can_create_work_item(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        membership = cls.get_user_team_membership(db, user_id=user_id, team_id=team_id)
        return membership is not None and membership.role in cls.CREATION_ROLES

    @classmethod
    def can_claim(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        """Member, Lead, Admin may claim work items. Viewer may not."""
        return cls.can_create_work_item(db, user_id=user_id, team_id=team_id)

    @classmethod
    def can_transition(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        """Member, Lead, Admin may transition work item status. Viewer may not."""
        return cls.can_create_work_item(db, user_id=user_id, team_id=team_id)

    @classmethod
    def can_approve(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        """Only Lead or Admin may approve (AWAITING_APPROVAL -> RESOLVED)."""
        membership = cls.get_user_team_membership(db, user_id=user_id, team_id=team_id)
        return membership is not None and membership.role in {
            MembershipRole.LEAD,
            MembershipRole.ADMIN,
        }

    @classmethod
    def can_manage_membership(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        """Only Admin may add/remove team members."""
        membership = cls.get_user_team_membership(db, user_id=user_id, team_id=team_id)
        return membership is not None and membership.role == MembershipRole.ADMIN

    @classmethod
    def is_lead_or_admin(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> bool:
        """Convenience check: True for Lead or Admin roles."""
        return cls.can_approve(db, user_id=user_id, team_id=team_id)


authorization_service = AuthorizationService()

