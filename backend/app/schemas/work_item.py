from datetime import datetime
import uuid
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class WorkItemCreate(BaseModel):
    team_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: str = Field(default="TASK", max_length=50)
    priority: str = Field(default="MEDIUM", max_length=50)
    assignee_id: Optional[uuid.UUID] = None


class WorkItemResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    description: Optional[str]
    type: str
    priority: str
    status: str
    assignee_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkItemListResponse(BaseModel):
    items: List[WorkItemResponse]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = None
    has_more: bool = False


class WorkItemTransitionRequest(BaseModel):
    to_status: str = Field(..., description="Target status for the transition")
    version: int = Field(..., ge=1, description="Current version the client holds (optimistic lock)")
