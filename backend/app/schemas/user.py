from datetime import datetime
import uuid
from typing import List
from pydantic import BaseModel, EmailStr, ConfigDict

from app.schemas.team import TeamMembershipResponse


class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    memberships: List[TeamMembershipResponse] = []

    model_config = ConfigDict(from_attributes=True)
