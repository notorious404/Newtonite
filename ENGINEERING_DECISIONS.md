# Newtonite Operations Under Pressure — Engineering Decisions & Architectural Architecture

This document records the architectural context, design alternatives considered, selected strategies, trade-offs, and empirical verification for the Newtonite Operations Under Pressure platform.

---

## 1. Atomic Ticket Claiming & Concurrency Safety

### Context
In operational incident and task management, multiple operators simultaneously attempting to claim the same unassigned ticket is a classic race condition. A naive read-then-write sequence (`SELECT ...` followed by `UPDATE ...`) is vulnerable to lost updates and double-assignment under high concurrent load.

### Options Considered
1. **Application-Level Mutex (Redis / In-Memory Lock):**
   - *Pros:* Offloads coordination from PostgreSQL.
   - *Cons:* Introduces an external dependency, network hops, distributed locking edge cases (split-brain, lease expiration during network partition).
2. **Pessimistic Row Locking (`SELECT ... FOR UPDATE`):**
   - *Pros:* Standard relational locking pattern.
   - *Cons:* Requires two separate database round trips; holds row locks across network trips, increasing connection pool contention.
3. **Conditional Atomic Single-Statement UPDATE with `RETURNING` (Selected):**
   - *Query:*
     ```sql
     UPDATE work_items
     SET assignee_id = :user_id,
         status = 'IN_PROGRESS',
         version = version + 1,
         updated_at = :now
     WHERE id = :item_id
       AND status = 'OPEN'
       AND assignee_id IS NULL
     RETURNING *;
     ```
   - *Pros:* Fully atomic inside PostgreSQL's transaction engine. Exactly one database statement. Zero application-level lock contention. PostgreSQL row-level locks naturally serialize concurrent callers; exactly one statement updates the row (`rowCount == 1`), while all losing concurrent statements update zero rows (`rowCount == 0`).
   - *Trade-offs:* Requires clients to handle HTTP 409 Conflict gracefully and refresh their UI.

### Verification & Concurrency Proof
- Tested with real parallel database sessions in `tests/test_claims.py::test_concurrent_claims_exactly_one_succeeds`.
- 10 threads concurrently issue simultaneous claims against the same open ticket: **exactly 1 request returns HTTP 200/201 (SUCCESS) and exactly 9 requests return HTTP 409 Conflict**.

---

## 2. Optimistic Locking vs. Pessimistic Row Locking for State Transitions

### Context
Work items undergo multi-step lifecycle transitions (`OPEN` → `IN_PROGRESS` → `AWAITING_APPROVAL` → `RESOLVED` → `CLOSED`). In a web application where operators view items and deliberate before clicking an action, holding pessimistic row locks (`SELECT FOR UPDATE`) across user read-and-think time is unacceptable.

### Options Considered
1. **Pessimistic Row Locking:** Long-lived row locks exhaust connection pools and risk deadlocks.
2. **Last-Write-Wins (LWW):** Silent overwriting of concurrent changes causes catastrophic data loss (e.g. overwriting another operator's status or notes).
3. **Version-Based Optimistic Concurrency Control (Selected):**
   - Every `work_items` record contains an integer `version` initialized to `1`.
   - The client submits `{"to_status": "...", "version": N}` representing the version they observed.
   - The update executes:
     ```sql
     UPDATE work_items
     SET status = :to_status,
         version = version + 1,
         updated_at = :now
     WHERE id = :item_id
       AND version = :expected_version
     RETURNING *;
     ```
   - If `rowCount == 0`, a concurrent update already incremented the version. The service raises `WorkItemConflict`, returning **HTTP 409** with a detailed payload. The frontend displays a dedicated `ConflictModal` offering a 1-click state reload.

### Verification
- Tested in `tests/test_transitions.py::test_transition_stale_version_409` and `tests/test_concurrent_conflicting_transitions`.
- Verified that simultaneous transition attempts with the same version result in exactly 1 success and 1 conflict, with zero orphaned activity events.

---

## 3. Idempotency Keys & Duplicate Request Prevention

### Context
Network timeouts, mobile retries, and rapid double-clicks frequently cause clients to retry creation requests. Creating duplicate tickets or charging duplicate resources violates operational integrity.

### Selected Architecture
1. **User-Scoped Idempotency:** The database table `idempotency_keys` enforces a unique constraint `UNIQUE (user_id, key)`:
   - Prevents cross-user key collision or denial-of-service.
2. **Canonical Request Fingerprinting:**
   - Hash: `SHA256(user_id + ":" + METHOD + ":" + PATH + ":" + canonical_json_bytes)`.
   - If a client re-uses an active key with a differing payload, the server returns **HTTP 422 Unprocessable Entity**.
3. **Atomic Single-Winner Reservation via PostgreSQL:**
   ```sql
   INSERT INTO idempotency_keys (id, user_id, key, request_hash, status_code, ...)
   VALUES (...)
   ON CONFLICT ON CONSTRAINT uq_idempotency_keys_user_key
   DO UPDATE SET expires_at = idempotency_keys.expires_at
   RETURNING *;
   ```
   - A true no-op update combined with `RETURNING *` guarantees that PostgreSQL always returns the winning row. The server compares `returned.id != new_id`: if different, another concurrent request already claimed the slot and the server returns **HTTP 409**.
4. **Failure Cleanup:** If work item validation or authorization fails before persistence, the reservation record is deleted (`delete_on_failure`), allowing the user to correct the error and retry with the same key.
5. **Replay Response:** Upon completion, the response body and status code (201) are persisted in `response_body` (JSONB). Subsequent identical calls with the same key return the cached 201 response directly without re-executing business logic.

### Verification
- Tested in `tests/test_idempotency.py`:
  - `test_idempotency_same_key_same_body_replays_response`
  - `test_idempotency_same_key_different_body_returns_422`
  - `test_idempotency_different_users_same_key_succeed_independently`
  - `test_idempotency_failed_request_can_be_retried`
  - `test_idempotency_concurrent_same_key_no_duplicates` (parallel thread race test)

---

## 4. Keyset (Cursor) Pagination vs. Offset Pagination

### Context
Offset pagination (`OFFSET 25000 LIMIT 20`) requires PostgreSQL to scan and discard 25,000 index tuples before returning 20 records. Under large dataset scale (50,000+ items), response times degrade linearly ($O(N)$). Furthermore, inserting or deleting items between pages causes "page drift" where items are duplicated or skipped across page boundaries.

### Selected Approach: Deterministic Keyset Pagination
- Ordering key: `(created_at DESC, id DESC)`. Including the primary key `id` guarantees total order even when multiple items share identical microsecond timestamps.
- Cursor: Base64-encoded URL-safe tuple `created_at|id`.
- SQL Filter:
  ```sql
  WHERE (created_at < :cursor_created_at)
     OR (created_at = :cursor_created_at AND id < :cursor_id)
  ORDER BY created_at DESC, id DESC
  LIMIT :limit + 1;
  ```
- Composite index: `ix_work_items_keyset` on `(team_id, created_at DESC, id DESC)` enables an immediate $O(\log N)$ B-tree index seek directly to the cursor position.
- Backward compatibility: The API retains `limit` and `offset` parameters for existing test suites while adding optional `cursor` support, returning `next_cursor` and `has_more`.

### Scale Validation Findings (50,000 Synthetic Work Items)
Executed via `backend/scripts/scale_benchmark.py` against PostgreSQL 16:
- **Composite Index Filter:** Filter on `(team_id, status='OPEN', priority='CRITICAL')` executed in **0.389 ms**.
- **Partial Index:** Unassigned urgent items (`WHERE assignee_id IS NULL AND status = 'OPEN' AND priority IN ('HIGH', 'CRITICAL')`) executed in **0.081 ms** via `ix_work_items_unassigned_urgent`.
- **Deep Keyset Pagination:** Paginating at offset 25,000 executed in **4.17 ms** directly using the index.
- **Zero Duplicates:** Verified across multiple pages that no records overlap across page boundaries.

---

## 5. Append-Only Transactional Activity History

### Context
Audit logs and compliance trails must guarantee immutability. If an attacker or application bug can issue `UPDATE` or `DELETE` statements on historical events, the audit trail is compromised.

### Selected Architecture
1. **PostgreSQL Database Trigger:**
   An Alembic migration (`24d860092dba_append_only_activity_events_trigger.py`) created a PL/pgSQL trigger function:
   ```sql
   CREATE OR REPLACE FUNCTION prevent_activity_event_mutation()
   RETURNS TRIGGER AS $$
   BEGIN
     RAISE EXCEPTION 'activity_events records are append-only and cannot be modified or deleted';
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER trg_activity_events_immutable
   BEFORE UPDATE OR DELETE ON activity_events
   FOR EACH ROW
   EXECUTE FUNCTION prevent_activity_event_mutation();
   ```
2. **Transactional Boundary:** Every state mutation (creation, claim, status transition) writes the `ActivityEvent` within the exact same database transaction as the `WorkItem` modification. If either fails, the entire transaction rolls back.

### Verification
- Tested in `tests/test_activity_integrity.py`:
  - Direct SQLAlchemy `UPDATE` on `activity_events` raises `InternalError / Exception`.
  - Direct SQLAlchemy `DELETE` on `activity_events` raises `InternalError / Exception`.
  - Transaction rollback on failed ticket creation produces zero orphaned activity records.

---

## 6. Centralized Authorization & Status Code Semantics

### Context
Ad-hoc permission checks scattered throughout route handlers create security regressions. Clear role semantics are required across `Viewer`, `Member`, `Lead`, and `Admin`.

### Centralized Service Implementation
All authorization checks route through [`AuthorizationService`](file:///backend/app/services/authorization_service.py):
- `can_view_team`: Viewer, Member, Lead, Admin
- `can_create_work_item`: Member, Lead, Admin (Viewer rejected)
- `can_claim`: Member, Lead, Admin (Viewer rejected)
- `can_transition`: Member, Lead, Admin (Viewer rejected)
- `can_approve`: Lead, Admin only.
- `can_manage_membership`: Admin only.

### Separation of Duties
To prevent fraudulent self-approval, approval from `AWAITING_APPROVAL` to `RESOLVED` checks:
```python
if item.created_by == user_id:
    raise WorkItemPermissionDenied("You cannot approve a work item you created (separation of duties).")
```

### HTTP 403 vs. HTTP 404 Security Semantics
- **HTTP 404 (Not Found):** Returned when a resource does not exist OR when the requester has no membership in the owning team. This prevents cross-tenant enumeration attacks (attackers cannot discover whether another team has a ticket with ID `X`).
- **HTTP 403 (Forbidden):** Returned when the requester is authenticated as a valid member of the team, but lacks the necessary role permissions for that specific operation (e.g., a `Viewer` attempting to claim a ticket, or a creator attempting to approve their own ticket).

---

## 7. What Was Deliberately Not Built

1. **Distributed Message Broker (Kafka / RabbitMQ):**
   - *Rationale:* PostgreSQL 16 transactional tables combined with row locking (`FOR UPDATE SKIP LOCKED`) easily handle thousands of jobs per second with transactional consistency. Adding RabbitMQ introduces multi-system failure modes without justification at this scale.
2. **External Caching Tier (Redis):**
   - *Rationale:* With proper PostgreSQL indexes (`ix_work_items_keyset`, `ix_work_items_team_status_priority`), sub-millisecond query execution makes external caching redundant while avoiding cache invalidation bugs.
3. **Complex Full-Text Search Engine (Elasticsearch):**
   - *Rationale:* PostgreSQL's native `ILIKE` and `pg_trgm` GIN indexes satisfy search requirements without operating a separate cluster.

---

## 8. Known Limitations & Next Steps

1. **Role Delegation & Expirable Memberships:** Memberships currently do not have expiration timestamps. Adding `expires_at` to memberships would support temporary on-call lead delegations.
2. **WebSocket / Server-Sent Events (SSE) Live Feed:** While TanStack Query polls the `/health` and invalidates caches after mutations, adding an SSE endpoint backed by PostgreSQL `LISTEN/NOTIFY` would provide sub-100ms real-time collaboration across multiple active browser windows.
