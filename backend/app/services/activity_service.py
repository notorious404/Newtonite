import uuid
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.activity_event import ActivityEvent


class ActivityService:
    @staticmethod
    def record_event(
        db: Session,
        *,
        item_id: uuid.UUID,
        actor_id: uuid.UUID,
        event_type: str,
        from_value: Optional[str] = None,
        to_value: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        event = ActivityEvent(
            item_id=item_id,
            actor_id=actor_id,
            type=event_type,
            from_value=from_value,
            to_value=to_value,
            payload=payload,
        )
        db.add(event)
        # Event is added to the current transaction, committed together with parent operation
        return event

    @staticmethod
    def get_events_for_item(
        db: Session,
        item_id: uuid.UUID,
    ) -> List[ActivityEvent]:
        stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.item_id == item_id)
            .order_by(ActivityEvent.created_at.asc())
        )
        return list(db.scalars(stmt).all())


activity_service = ActivityService()
