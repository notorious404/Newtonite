import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.schemas.team import TeamMembershipResponse
from app.schemas.membership import MembershipCreate, MembershipResponse
from app.models.user import User
from app.models.membership import Membership, MembershipRole
from app.api.deps import get_current_active_user
from app.services.authorization_service import authorization_service

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get(
    "",
    response_model=List[TeamMembershipResponse],
    summary="List Authenticated User's Teams",
)
def list_teams(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[TeamMembershipResponse]:
    memberships = authorization_service.get_user_memberships(db, user_id=current_user.id)
    return [
        TeamMembershipResponse(
            id=m.id,
            team_id=m.team_id,
            team_name=m.team.name if m.team else "",
            role=m.role,
            created_at=m.created_at,
        )
        for m in memberships
    ]


@router.post(
    "/{team_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Member to Team (Admin only)",
)
def add_team_member(
    team_id: uuid.UUID,
    member_in: MembershipCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    """Only Admin of a team may add members. Validates the target user exists."""
    if not authorization_service.can_manage_membership(
        db, user_id=current_user.id, team_id=team_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a team Admin may add members.",
        )

    # Validate the target role is legal
    if member_in.role not in MembershipRole.ALL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{member_in.role}'. Must be one of {sorted(MembershipRole.ALL)}.",
        )

    # Verify the target user exists
    target_user = db.scalar(select(User).where(User.id == member_in.user_id))
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found.",
        )

    membership = Membership(
        user_id=member_in.user_id,
        team_id=team_id,
        role=member_in.role,
    )
    db.add(membership)
    try:
        db.commit()
        db.refresh(membership)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this team.",
        )

    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        team_id=membership.team_id,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Member from Team (Admin only)",
)
def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Only Admin of a team may remove members. Admin cannot remove themselves."""
    if not authorization_service.can_manage_membership(
        db, user_id=current_user.id, team_id=team_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a team Admin may remove members.",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin cannot remove themselves from the team.",
        )

    membership = db.scalar(
        select(Membership).where(
            Membership.team_id == team_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    db.delete(membership)
    db.commit()
