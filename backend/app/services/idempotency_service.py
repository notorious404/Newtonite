"""
Idempotency service for ticket creation.

Flow:
1. No Idempotency-Key header  → process normally (backward compatible).
2. Key exists, status_code set → replay stored response.
3. Key exists, status_code null (in-flight) → 409.
4. Key exists, different hash  → 422.
5. Key absent                  → atomic INSERT ON CONFLICT DO UPDATE (no-op update),
   then check if WE inserted it by comparing the returned row's request_hash.
   If the returned row has a different hash → another request won; raise conflict or mismatch.

The INSERT...ON CONFLICT DO UPDATE trick forces PostgreSQL to always return a row
(unlike DO NOTHING which returns nothing on conflict), letting us detect whether
we won the race or someone else inserted first.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.idempotency_key import IdempotencyKey


class IdempotencyConflict(Exception):
    """Raised when the key is in-flight (another request is processing it)."""


class IdempotencyMismatch(Exception):
    """Raised when the key is reused with a different request body."""


class IdempotencyService:
    EXPIRY_HOURS = 24

    @staticmethod
    def compute_hash(user_id: uuid.UUID, method: str, path: str, body: bytes) -> str:
        raw = f"{user_id}:{method.upper()}:{path}:".encode() + body
        return hashlib.sha256(raw).hexdigest()

    @classmethod
    def check_or_reserve(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
    ) -> Optional[IdempotencyKey]:
        """
        Look up an existing COMPLETED key record.
        Returns:
          - None if no completed record exists (caller should call reserve() then process)
          - IdempotencyKey with status_code set → caller should replay
          - Raises IdempotencyConflict if the key exists but is still in-flight
          - Raises IdempotencyMismatch if the hash differs
        """
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
        )
        record = db.scalar(stmt)
        if record is None:
            return None

        if record.request_hash != request_hash:
            raise IdempotencyMismatch(
                "Idempotency key reused with a different request body."
            )

        if record.status_code is None:
            raise IdempotencyConflict(
                "A request with this idempotency key is already being processed."
            )

        return record  # Caller replays this

    @classmethod
    def reserve(
        cls,
        db: Session,
        *,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
    ) -> IdempotencyKey:
        """
        Atomically reserve an idempotency key slot.

        Uses INSERT ... ON CONFLICT ON CONSTRAINT ... DO UPDATE SET id=id
        (a no-op update) combined with RETURNING *. This forces PostgreSQL to
        always return the winning row — regardless of whether WE inserted it or
        someone else got there first. By comparing the returned row's request_hash
        with our own, we can detect whether we won the race.

        Guarantee: only ONE concurrent request will successfully proceed with creation;
        all others will receive IdempotencyConflict or IdempotencyMismatch.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=cls.EXPIRY_HOURS)
        new_id = uuid.uuid4()

        stmt = (
            pg_insert(IdempotencyKey)
            .values(
                id=new_id,
                user_id=user_id,
                key=key,
                request_hash=request_hash,
                status_code=None,
                response_headers=None,
                response_body=None,
                created_at=now,
                expires_at=expires,
            )
            # On conflict, do a true no-op update (keep existing expires_at unchanged)
            # so RETURNING always yields the row that "won" the INSERT race.
            .on_conflict_do_update(
                constraint="uq_idempotency_keys_user_key",
                set_={"expires_at": IdempotencyKey.__table__.c.expires_at},
            )
            .returning(IdempotencyKey)
        )
        result = db.execute(stmt)
        returned_record = result.scalar_one()

        if returned_record.id != new_id:
            # Another request already holds this slot (the no-op UPDATE fired)
            existing = returned_record
            if existing.request_hash != request_hash:
                raise IdempotencyMismatch(
                    "Idempotency key reused with a different request body."
                )
            raise IdempotencyConflict(
                "Concurrent request with the same idempotency key is being processed."
            )

        # We won — the INSERT succeeded; return our fresh record
        db.flush()
        return returned_record

    @classmethod
    def store_result(
        cls,
        db: Session,
        *,
        record: IdempotencyKey,
        status_code: int,
        response_body: Dict[str, Any],
    ) -> None:
        """Persist the final result onto the pending record."""
        record.status_code = status_code
        record.response_body = response_body
        db.flush()

    @classmethod
    def delete_on_failure(
        cls,
        db: Session,
        *,
        record: IdempotencyKey,
    ) -> None:
        """
        Remove the pending record so a future retry can start fresh.
        Called when creation fails (so the key is not permanently poisoned).
        """
        db.delete(record)
        db.flush()


idempotency_service = IdempotencyService()
