import hashlib
import json
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status as http_status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.work_item import (
    WorkItemCreate,
    WorkItemResponse,
    WorkItemListResponse,
    WorkItemTransitionRequest,
)
from app.schemas.activity_event import (
    ActivityEventResponse,
    ActivityEventListResponse,
)
from app.models.user import User
from app.api.deps import get_current_active_user
from app.services.work_item_service import (
    work_item_service,
    WorkItemPermissionDenied,
    WorkItemNotFound,
    WorkItemConflict,
)
from app.services.activity_service import activity_service
from app.services.idempotency_service import (
    idempotency_service,
    IdempotencyConflict,
    IdempotencyMismatch,
)

router = APIRouter(prefix="/work-items", tags=["work-items"])


@router.get(
    "",
    response_model=WorkItemListResponse,
    summary="List Accessible Work Items",
)
def list_work_items(
    team_id: Optional[uuid.UUID] = Query(None, description="Filter by team"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, IN_PROGRESS, etc.)"),
    priority: Optional[str] = Query(None, description="Filter by priority (LOW, MEDIUM, HIGH, CRITICAL)"),
    q: Optional[str] = Query(None, description="Search in title and description"),
    cursor: Optional[str] = Query(None, description="Keyset pagination cursor for next page"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset (used when cursor is not provided)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WorkItemListResponse:
    try:
        items, total, next_cursor, has_more = work_item_service.list_work_items(
            db,
            user_id=current_user.id,
            team_id=team_id,
            status=status,
            priority=priority,
            q=q,
            cursor=cursor,
            limit=limit,
            offset=offset,
        )
        return WorkItemListResponse(
            items=[WorkItemResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except WorkItemPermissionDenied as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "",
    response_model=WorkItemResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Create Work Item (supports Idempotency-Key header)",
)
def create_work_item(
    request: Request,
    item_in: WorkItemCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WorkItemResponse:
    # --- Idempotency handling ---
    if idempotency_key:
        body_bytes = request._body if hasattr(request, "_body") else b""
        # Compute deterministic hash
        try:
            # Re-serialize the validated body to get a canonical representation
            body_bytes = item_in.model_dump_json().encode("utf-8")
        except Exception:
            body_bytes = b""

        req_hash = idempotency_service.compute_hash(
            user_id=current_user.id,
            method="POST",
            path="/api/v1/work-items",
            body=body_bytes,
        )

        try:
            existing = idempotency_service.check_or_reserve(
                db,
                user_id=current_user.id,
                key=idempotency_key,
                request_hash=req_hash,
            )
        except IdempotencyMismatch as e:
            raise HTTPException(status_code=422, detail=str(e))
        except IdempotencyConflict as e:
            raise HTTPException(status_code=409, detail=str(e))

        if existing is not None:
            # Replay stored response
            return WorkItemResponse.model_validate(existing.response_body)

        # Reserve the key slot atomically (INSERT ON CONFLICT DO NOTHING)
        # Raises IdempotencyConflict if another request already holds this key
        try:
            idem_record = idempotency_service.reserve(
                db,
                user_id=current_user.id,
                key=idempotency_key,
                request_hash=req_hash,
            )
        except IdempotencyConflict as e:
            raise HTTPException(
                status_code=409,
                detail=str(e),
            )
        except IdempotencyMismatch as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Process the creation
        try:
            work_item = work_item_service.create_work_item(
                db,
                user_id=current_user.id,
                item_in=item_in,
            )
        except WorkItemPermissionDenied as e:
            idempotency_service.delete_on_failure(db, record=idem_record)
            db.commit()
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(e))
        except ValueError as e:
            idempotency_service.delete_on_failure(db, record=idem_record)
            db.commit()
            raise HTTPException(status_code=422, detail=str(e))

        response_data = WorkItemResponse.model_validate(work_item)
        response_dict = json.loads(response_data.model_dump_json())
        idempotency_service.store_result(
            db,
            record=idem_record,
            status_code=201,
            response_body=response_dict,
        )
        db.commit()
        return response_data

    # --- No idempotency key: standard creation ---
    try:
        work_item = work_item_service.create_work_item(
            db,
            user_id=current_user.id,
            item_in=item_in,
        )
        return WorkItemResponse.model_validate(work_item)
    except WorkItemPermissionDenied as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.post(
    "/{item_id}/claim",
    response_model=WorkItemResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Atomically Claim an OPEN Work Item",
)
def claim_work_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WorkItemResponse:
    try:
        work_item = work_item_service.claim_work_item(
            db,
            user_id=current_user.id,
            item_id=item_id,
        )
        db.commit()
        db.refresh(work_item)
        return WorkItemResponse.model_validate(work_item)
    except WorkItemNotFound as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkItemPermissionDenied as e:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkItemConflict as e:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{item_id}/transition",
    response_model=WorkItemResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Transition Work Item Status (Optimistic Locking)",
)
def transition_work_item(
    item_id: uuid.UUID,
    transition_in: WorkItemTransitionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WorkItemResponse:
    try:
        work_item = work_item_service.transition_work_item(
            db,
            user_id=current_user.id,
            item_id=item_id,
            to_status=transition_in.to_status,
            expected_version=transition_in.version,
        )
        db.commit()
        db.refresh(work_item)
        return WorkItemResponse.model_validate(work_item)
    except WorkItemNotFound as e:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkItemPermissionDenied as e:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkItemConflict as e:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/{item_id}",
    response_model=WorkItemResponse,
    summary="Retrieve Accessible Work Item",
)
def get_work_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WorkItemResponse:
    try:
        work_item = work_item_service.get_work_item(
            db,
            user_id=current_user.id,
            item_id=item_id,
        )
        return WorkItemResponse.model_validate(work_item)
    except WorkItemNotFound as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except WorkItemPermissionDenied as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get(
    "/{item_id}/activity",
    response_model=ActivityEventListResponse,
    summary="Retrieve Work Item Activity History",
)
def get_work_item_activity(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> ActivityEventListResponse:
    # 1. Enforce access to the work item
    try:
        work_item_service.get_work_item(
            db,
            user_id=current_user.id,
            item_id=item_id,
        )
    except WorkItemNotFound as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except WorkItemPermissionDenied as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    # 2. Retrieve chronological audit history
    events = activity_service.get_events_for_item(db, item_id=item_id)
    return ActivityEventListResponse(
        items=[ActivityEventResponse.model_validate(e) for e in events],
        total=len(events),
    )
