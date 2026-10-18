"""
Pydantic schemas for membership management endpoints.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MembershipCreate(BaseModel):
    """Request body for adding a member to a team."""
    user_id: uuid.UUID
    role: str


class MembershipResponse(BaseModel):
    """Response body for a membership record."""
    id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
