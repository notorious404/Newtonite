from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserProfileResponse
from app.schemas.team import TeamMembershipResponse
from app.models.user import User
from app.api.deps import get_current_active_user
from app.services.auth_service import auth_service
from app.services.authorization_service import authorization_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User",
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = auth_service.authenticate_user(
        db,
        email=login_data.email,
        password=login_data.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Current User Profile & Memberships",
)
def get_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    memberships = authorization_service.get_user_memberships(db, user_id=current_user.id)
    membership_items = [
        TeamMembershipResponse(
            id=m.id,
            team_id=m.team_id,
            team_name=m.team.name if m.team else "",
            role=m.role,
            created_at=m.created_at,
        )
        for m in memberships
    ]
    return UserProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        memberships=membership_items,
    )
