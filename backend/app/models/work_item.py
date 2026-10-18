from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.user import User
    from app.models.activity_event import ActivityEvent


class WorkItemStatus:
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    ALL = {OPEN, IN_PROGRESS, AWAITING_APPROVAL, RESOLVED, CLOSED}


class WorkItemPriority:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    ALL = {LOW, MEDIUM, HIGH, CRITICAL}


class WorkItemType:
    TASK = "TASK"
    BUG = "BUG"
    FEATURE = "FEATURE"
    IMPROVEMENT = "IMPROVEMENT"

    ALL = {TASK, BUG, FEATURE, IMPROVEMENT}


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default=WorkItemType.TASK)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default=WorkItemPriority.MEDIUM)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=WorkItemStatus.OPEN)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    team: Mapped["Team"] = relationship("Team", back_populates="work_items")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id])
    activity_events: Mapped[List["ActivityEvent"]] = relationship(
        "ActivityEvent",
        back_populates="work_item",
        cascade="all, delete-orphan",
        order_by="ActivityEvent.created_at.asc()",
    )

    __table_args__ = (
        Index("ix_work_items_team_status", "team_id", "status"),
        Index("ix_work_items_team_priority", "team_id", "priority"),
    )
