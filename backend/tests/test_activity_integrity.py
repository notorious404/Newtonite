import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from sqlalchemy.exc import DBAPIError

from app.models.team import Team
from app.models.user import User
from app.models.work_item import WorkItem, WorkItemStatus
from app.models.activity_event import ActivityEvent, ActivityEventType
from app.services.activity_service import activity_service
from app.services.work_item_service import work_item_service
from tests.conftest import TestingSessionLocal


def test_activity_events_are_append_only_update_rejected(db: Session):
    """
    Verify PostgreSQL trigger rejects any attempt to UPDATE an activity event.
    """
    team = db.scalar(select(Team).limit(1))
    user = db.scalar(select(User).limit(1))
    assert team is not None
    assert user is not None

    item = WorkItem(
        team_id=team.id,
        title="Append-only test item",
        status=WorkItemStatus.OPEN,
        created_by=user.id,
        version=1,
    )
    db.add(item)
    db.flush()

    event = activity_service.record_event(
        db,
        item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.CREATED,
        to_value=WorkItemStatus.OPEN,
    )
    db.flush()
    event_id = event.id

    # Attempt to UPDATE the activity event -> must be rejected by database trigger
    with pytest.raises(DBAPIError) as exc_info:
        db.execute(
            update(ActivityEvent)
            .where(ActivityEvent.id == event_id)
            .values(type="TAMPERED")
        )
        db.flush()

    assert "append-only" in str(exc_info.value).lower() or "immutable" in str(exc_info.value).lower()
    db.rollback()


def test_activity_events_are_append_only_delete_rejected(db: Session):
    """
    Verify PostgreSQL trigger rejects any attempt to DELETE an activity event.
    """
    team = db.scalar(select(Team).limit(1))
    user = db.scalar(select(User).limit(1))
    assert team is not None
    assert user is not None

    item = WorkItem(
        team_id=team.id,
        title="Append-only delete test item",
        status=WorkItemStatus.OPEN,
        created_by=user.id,
        version=1,
    )
    db.add(item)
    db.flush()

    event = activity_service.record_event(
        db,
        item_id=item.id,
        actor_id=user.id,
        event_type=ActivityEventType.CREATED,
        to_value=WorkItemStatus.OPEN,
    )
    db.flush()
    event_id = event.id

    # Attempt to DELETE the activity event -> must be rejected by database trigger
    with pytest.raises(DBAPIError) as exc_info:
        db.execute(
            delete(ActivityEvent).where(ActivityEvent.id == event_id)
        )
        db.flush()

    assert "append-only" in str(exc_info.value).lower() or "immutable" in str(exc_info.value).lower()
    db.rollback()


def test_transaction_rollback_leaves_no_orphaned_activity_event(db: Session):
    """
    Verify that if a work item transaction fails or rolls back,
    no partial activity event is written to the database.
    """
    team = db.scalar(select(Team).limit(1))
    user = db.scalar(select(User).limit(1))
    fake_item_id = uuid.uuid4()

    # In a sub-transaction, insert an event and then roll back
    nested = db.begin_nested()
    activity_service.record_event(
        db,
        item_id=fake_item_id,
        actor_id=user.id,
        event_type=ActivityEventType.CREATED,
    )
    # Roll back the nested transaction
    nested.rollback()

    events = list(db.scalars(select(ActivityEvent).where(ActivityEvent.item_id == fake_item_id)).all())
    assert len(events) == 0
