from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str


class TeamResponse(TeamBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamMembershipResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
