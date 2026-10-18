from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.work_item import WorkItem


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    memberships: Mapped[List["Membership"]] = relationship(
        "Membership",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    work_items: Mapped[List["WorkItem"]] = relationship(
        "WorkItem",
        back_populates="team",
        cascade="all, delete-orphan",
    )
