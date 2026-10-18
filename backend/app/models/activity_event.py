from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Optional, Any, Dict
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.work_item import WorkItem
    from app.models.user import User


class ActivityEventType:
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    UPDATED = "UPDATED"
    ASSIGNED = "ASSIGNED"
    CLAIMED = "CLAIMED"


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    work_item: Mapped["WorkItem"] = relationship("WorkItem", back_populates="activity_events")
    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_activity_events_item_created", "item_id", "created_at"),
    )
