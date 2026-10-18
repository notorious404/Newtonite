from datetime import datetime
import uuid
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, ConfigDict


class ActivityEventResponse(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    actor_id: uuid.UUID
    type: str
    from_value: Optional[str]
    to_value: Optional[str]
    payload: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityEventListResponse(BaseModel):
    items: List[ActivityEventResponse]
    total: int
