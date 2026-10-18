from typing import Set, Dict
from app.models.work_item import WorkItemStatus


class WorkflowService:
    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        WorkItemStatus.OPEN: {WorkItemStatus.IN_PROGRESS},
        WorkItemStatus.IN_PROGRESS: {WorkItemStatus.AWAITING_APPROVAL},
        WorkItemStatus.AWAITING_APPROVAL: {
            WorkItemStatus.RESOLVED,
            WorkItemStatus.IN_PROGRESS,  # Rejection
        },
        WorkItemStatus.RESOLVED: {
            WorkItemStatus.CLOSED,
            WorkItemStatus.IN_PROGRESS,  # Reopening
        },
        WorkItemStatus.CLOSED: set(),
    }

    @classmethod
    def can_transition(cls, current_status: str, target_status: str) -> bool:
        if current_status not in cls.ALLOWED_TRANSITIONS:
            return False
        return target_status in cls.ALLOWED_TRANSITIONS[current_status]

    @classmethod
    def get_allowed_transitions(cls, current_status: str) -> Set[str]:
        return cls.ALLOWED_TRANSITIONS.get(current_status, set())


workflow_service = WorkflowService()
