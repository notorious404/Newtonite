import base64
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update, or_, and_


def encode_cursor(created_at: datetime, item_id: uuid.UUID) -> str:
    payload = f"{created_at.isoformat()}|{str(item_id)}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor_str: str) -> Tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        dt_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(dt_str), uuid.UUID(id_str)
    except Exception:
        raise ValueError("Invalid cursor format")

from app.models.work_item import (
    WorkItem,
    WorkItemStatus,
    WorkItemPriority,
    WorkItemType,
)
from app.models.activity_event import ActivityEventType
from app.schemas.work_item import WorkItemCreate
from app.services.authorization_service import authorization_service
from app.services.activity_service import activity_service
from app.services.workflow_service import workflow_service


class WorkItemPermissionDenied(Exception):
    pass


class WorkItemNotFound(Exception):
    pass


class WorkItemConflict(Exception):
    pass


class WorkItemService:
    @staticmethod
    def create_work_item(
        db: Session,
        *,
        user_id: uuid.UUID,
        item_in: WorkItemCreate,
    ) -> WorkItem:
        # 1. Validate team membership and creation permissions
        can_create = authorization_service.can_create_work_item(
            db,
            user_id=user_id,
            team_id=item_in.team_id,
        )
        if not can_create:
            raise WorkItemPermissionDenied(
                "You do not have permission to create work items for this team."
            )

        # Validate type and priority against allowed sets
        item_type = item_in.type.upper() if item_in.type else WorkItemType.TASK
        item_priority = item_in.priority.upper() if item_in.priority else WorkItemPriority.MEDIUM

        # 2. Instantiate WorkItem at OPEN status and version 1
        work_item = WorkItem(
            team_id=item_in.team_id,
            title=item_in.title,
            description=item_in.description,
            type=item_type,
            priority=item_priority,
            status=WorkItemStatus.OPEN,
            assignee_id=item_in.assignee_id,
            created_by=user_id,
            version=1,
        )
        db.add(work_item)
        db.flush()  # Generate work_item.id

        # 3. Write initial activity event in the same transaction
        activity_service.record_event(
            db,
            item_id=work_item.id,
            actor_id=user_id,
            event_type=ActivityEventType.CREATED,
            from_value=None,
            to_value=WorkItemStatus.OPEN,
            payload={
                "title": work_item.title,
                "type": work_item.type,
                "priority": work_item.priority,
                "team_id": str(work_item.team_id),
            },
        )

        db.commit()
        db.refresh(work_item)
        return work_item

    @staticmethod
    def list_work_items(
        db: Session,
        *,
        user_id: uuid.UUID,
        team_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        q: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[WorkItem], int, Optional[str], bool]:
        # Server-side access enforcement: retrieve all teams user is authorized in
        user_team_ids = authorization_service.get_user_team_ids(db, user_id=user_id)
        if not user_team_ids:
            return [], 0, None, False

        # Build base filter
        filters = []
        if team_id is not None:
            if team_id not in user_team_ids:
                raise WorkItemPermissionDenied(
                    "You do not have permission to access work items for this team."
                )
            filters.append(WorkItem.team_id == team_id)
        else:
            filters.append(WorkItem.team_id.in_(user_team_ids))

        if status:
            filters.append(WorkItem.status == status.upper())

        if priority:
            filters.append(WorkItem.priority == priority.upper())

        if q and q.strip():
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    WorkItem.title.ilike(term),
                    WorkItem.description.ilike(term),
                )
            )

        # Count total matching
        count_stmt = select(func.count(WorkItem.id)).where(*filters)
        total = db.scalar(count_stmt) or 0

        # Keyset pagination condition if cursor is provided
        query_filters = list(filters)
        if cursor:
            cursor_dt, cursor_id = decode_cursor(cursor)
            query_filters.append(
                or_(
                    WorkItem.created_at < cursor_dt,
                    and_(
                        WorkItem.created_at == cursor_dt,
                        WorkItem.id < cursor_id,
                    ),
                )
            )

        # Retrieve items (+1 to check has_more)
        items_stmt = (
            select(WorkItem)
            .where(*query_filters)
            .order_by(WorkItem.created_at.desc(), WorkItem.id.desc())
            .limit(limit + 1)
        )
        if not cursor and offset > 0:
            items_stmt = items_stmt.offset(offset)

        raw_items = list(db.scalars(items_stmt).all())
        has_more = len(raw_items) > limit
        items = raw_items[:limit]

        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.created_at, last_item.id)

        return items, total, next_cursor, has_more

    @staticmethod
    def get_work_item(
        db: Session,
        *,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> WorkItem:
        stmt = select(WorkItem).where(WorkItem.id == item_id)
        item = db.scalar(stmt)
        if not item:
            raise WorkItemNotFound("Work item not found.")

        # Server-side team access verification
        if not authorization_service.can_view_team(db, user_id=user_id, team_id=item.team_id):
            raise WorkItemPermissionDenied("You do not have access to this work item.")

        return item

    @staticmethod
    def claim_work_item(
        db: Session,
        *,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> WorkItem:
        """
        Atomically claim an OPEN, unassigned work item using a single
        conditional UPDATE with WHERE status='OPEN' AND assignee_id IS NULL.
        No separate read-then-write, so concurrent claims cannot both succeed.
        """
        # First verify the item exists and the user can see/claim it
        stmt_check = select(WorkItem).where(WorkItem.id == item_id)
        item = db.scalar(stmt_check)
        if not item:
            raise WorkItemNotFound("Work item not found.")

        if not authorization_service.can_view_team(db, user_id=user_id, team_id=item.team_id):
            raise WorkItemPermissionDenied("You do not have access to this work item.")

        if not authorization_service.can_claim(db, user_id=user_id, team_id=item.team_id):
            raise WorkItemPermissionDenied(
                "You do not have permission to claim work items for this team."
            )

        now = datetime.now(timezone.utc)
        stmt_update = (
            update(WorkItem)
            .where(
                WorkItem.id == item_id,
                WorkItem.status == WorkItemStatus.OPEN,
                WorkItem.assignee_id.is_(None),
            )
            .values(
                assignee_id=user_id,
                status=WorkItemStatus.IN_PROGRESS,
                version=WorkItem.version + 1,
                updated_at=now,
            )
            .returning(WorkItem)
        )
        result = db.execute(stmt_update)
        updated_item = result.scalar_one_or_none()

        if updated_item is None:
            # Row was not updated: item already claimed or not OPEN
            raise WorkItemConflict(
                "Work item could not be claimed. "
                "It may already be assigned or not in OPEN status."
            )

        # Record the activity event in the SAME transaction
        activity_service.record_event(
            db,
            item_id=item_id,
            actor_id=user_id,
            event_type=ActivityEventType.CLAIMED,
            from_value=WorkItemStatus.OPEN,
            to_value=WorkItemStatus.IN_PROGRESS,
            payload={"assignee_id": str(user_id)},
        )

        db.flush()
        return updated_item

    @staticmethod
    def transition_work_item(
        db: Session,
        *,
        user_id: uuid.UUID,
        item_id: uuid.UUID,
        to_status: str,
        expected_version: int,
    ) -> WorkItem:
        """
        Transition a work item's status using optimistic locking.
        The UPDATE only modifies the row when stored version == expected_version,
        preventing lost-update races between concurrent requests.
        """
        stmt_check = select(WorkItem).where(WorkItem.id == item_id)
        item = db.scalar(stmt_check)
        if not item:
            raise WorkItemNotFound("Work item not found.")

        if not authorization_service.can_view_team(db, user_id=user_id, team_id=item.team_id):
            raise WorkItemPermissionDenied("You do not have access to this work item.")

        if not authorization_service.can_transition(db, user_id=user_id, team_id=item.team_id):
            raise WorkItemPermissionDenied("You do not have permission to transition work items for this team.")

        # Validate transition against workflow map
        if not workflow_service.can_transition(item.status, to_status):
            raise WorkItemConflict(
                f"Transition from '{item.status}' to '{to_status}' is not allowed. "
                f"Allowed targets: {sorted(workflow_service.get_allowed_transitions(item.status))}"
            )

        # Separation-of-duties: only Lead/Admin may approve AWAITING_APPROVAL → RESOLVED
        if item.status == WorkItemStatus.AWAITING_APPROVAL and to_status == WorkItemStatus.RESOLVED:
            if not authorization_service.can_approve(db, user_id=user_id, team_id=item.team_id):
                raise WorkItemPermissionDenied(
                    "Only a Lead or Admin may approve work items."
                )
            if item.created_by == user_id:
                raise WorkItemPermissionDenied(
                    "You cannot approve a work item you created (separation of duties)."
                )

        now = datetime.now(timezone.utc)
        from_status = item.status

        stmt_update = (
            update(WorkItem)
            .where(
                WorkItem.id == item_id,
                WorkItem.version == expected_version,
            )
            .values(
                status=to_status,
                version=WorkItem.version + 1,
                updated_at=now,
            )
            .returning(WorkItem)
        )
        result = db.execute(stmt_update)
        updated_item = result.scalar_one_or_none()

        if updated_item is None:
            # Version mismatch: another update beat us
            raise WorkItemConflict(
                f"Version conflict: the item has been modified. "
                f"Your version={expected_version} no longer matches the database."
            )

        activity_service.record_event(
            db,
            item_id=item_id,
            actor_id=user_id,
            event_type=ActivityEventType.STATUS_CHANGED,
            from_value=from_status,
            to_value=to_status,
            payload={"version_before": expected_version, "version_after": updated_item.version},
        )

        db.flush()
        return updated_item


work_item_service = WorkItemService()
