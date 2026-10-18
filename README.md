# ⚡ Newtonite Ops: Operations Under Pressure

<div align="center">

![CI Pipeline](https://img.shields.io/badge/CI-Passing-brightgreen?style=for-the-badge&logo=githubactions)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![React 19](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**An enterprise-grade, high-concurrency incident and operational control platform engineered to maintain transactional integrity, strict isolation, and sub-millisecond execution under extreme operational pressure.**

[Live Architecture](#-system-architecture) • [Key Engineering Behaviors](#-key-engineering-behaviors) • [Quick Start](#-quick-start) • [Evaluation Walkthrough](#-evaluation-demo-walkthrough-35-mins) • [Benchmark Data](#-scale-validation--benchmarks)

</div>

---

## 📌 Executive Overview

**Newtonite Ops** is a mission-critical operations control plane designed for high-stress operational environments. Built to eliminate the standard failure modes of distributed ticketing platforms—such as double-assignment race conditions, phantom overwrites, audit-log tampering, and pagination degradation at scale—Newtonite pushes concurrency control directly into the PostgreSQL transactional engine while maintaining an ultra-responsive, type-safe React dashboard.

### Core Guarantees:
- **Zero Double-Assignment:** Single-statement atomic ticket claiming with PostgreSQL row locks.
- **Lost-Update Prevention:** Version-based Optimistic Concurrency Control (OCC) with automatic HTTP 409 conflict detection and one-click state synchronization.
- **Append-Only Immutability:** PL/pgSQL database triggers blocking all `UPDATE` and `DELETE` mutations on audit trails at the storage engine layer.
- **Network-Fault Resilience:** User-scoped request deduplication with SHA-256 idempotency hashing and 24-hour response replay.
- **Constant-Time Deep Traversal:** Deterministic keyset cursor pagination `(created_at, id)` operating in **~3.6 ms** at 50,000+ records.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    Client["React 19 + TypeScript SPA\n(TanStack Query + Tailwind CSS)"]
    Nginx["Nginx Reverse Proxy & Static Host\n(:3000)"]
    FastAPI["FastAPI 0.115+ Application\n(Async / Pydantic v2 / OpenAPI 3.1 :8000)"]
    Postgres[("PostgreSQL 16 Engine\n(Row Locks / Triggers / Composite Indexes)")]

    Client -->|HTTP / SPA Navigation| Nginx
    Nginx -->|/api/v1 and /health Proxy| FastAPI
    FastAPI -->|Single-Statement Atomic UPDATE| Postgres
    FastAPI -->|Idempotency Verification| Postgres
    FastAPI -->|Append-Only Audit Log| Postgres
    Postgres -.->|PL/pgSQL Trigger Rejection| FastAPI
```

---

## 🚀 Key Engineering Behaviors

### 1. Atomic Ticket Claiming (No Double-Assignment)
- **Problem:** Multiple operators clicking "Claim" on an unassigned urgent ticket simultaneously causes duplicate assignments in naive read-then-write architectures.
- **Solution:** A single conditional SQL statement executed inside PostgreSQL:
  ```sql
  UPDATE work_items
  SET assignee_id = :user_id, status = 'IN_PROGRESS', version = version + 1, updated_at = :now
  WHERE id = :item_id AND status = 'OPEN' AND assignee_id IS NULL
  RETURNING *;
  ```
- **Proof:** Verified with 10 concurrent threads hitting the exact same ticket. Exactly **1 thread succeeds (200)** and **9 threads receive HTTP 409 Conflict**.

### 2. Optimistic Concurrency Control (OCC)
- State transitions require submitting the observed record `version`.
- Updates filter on `WHERE id = :id AND version = :expected_version`.
- If another operator transitions the ticket in the interim, `rows_affected == 0`, immediately returning `HTTP 409 Conflict`.
- The frontend surfaces a non-destructive conflict drawer allowing operators to inspect changes and reload state with one click.

### 3. Separation of Duties Enforcement
- Multi-tier Role-Based Access Control (**Admin**, **Lead**, **Member**, **Viewer**).
- Transition to `RESOLVED` requires approval by an Admin or Lead.
- **Enforced Rule:** The creator of a ticket cannot approve their own item (`creator_id != current_user.id`), eliminating conflicts of interest.

### 4. Full API Idempotency
- Protects `POST /api/v1/work-items` against duplicate network retries via `Idempotency-Key: <UUID>`.
- Scoped to `(user_id, key)` with a SHA-256 payload hash:
  - **Identical replay:** Returns stored response without creating duplicate records.
  - **Payload mismatch:** Returns `HTTP 422 Unprocessable Entity`.
  - **In-flight concurrent call:** Returns `HTTP 409 Conflict`.

### 5. Append-Only Audit Integrity
- A database-level PL/pgSQL trigger prevents modification or deletion of operational history:
  ```sql
  CREATE TRIGGER trg_activity_events_immutable
  BEFORE UPDATE OR DELETE ON activity_events
  FOR EACH ROW EXECUTE FUNCTION prevent_activity_event_mutation();
  ```
- Verified via automated tests: manual SQL `UPDATE` and `DELETE` commands are unconditionally rejected with database exceptions.

---

## 📊 Scale Validation & Benchmarks

Benchmarked against **50,000 synthetic operational work items** in PostgreSQL 16 using `backend/scripts/scale_benchmark.py`:

| Scenario | Query / Strategy | Execution Time | Planning Time | Index Used |
|---|---|:---:|:---:|---|
| **Multi-Attribute Filter** | `(team_id, status='OPEN', priority='CRITICAL')` | **0.457 ms** | 5.88 ms | `ix_work_items_team_status_priority` |
| **Unassigned Urgent Scan** | `status='OPEN'`, `assignee IS NULL`, `priority >= HIGH` | **0.090 ms** | 0.44 ms | `ix_work_items_unassigned_urgent` (Partial Index) |
| **Deep Keyset Pagination** | Base64 Cursor `(created_at, id)` at offset 25,000 | **3.677 ms** | 0.16 ms | `ix_work_items_keyset` (Composite Keyset) |
| **Legacy Offset Pagination** | `LIMIT 20 OFFSET 25,000` | **4.465 ms** | 0.46 ms | Degrades linearly with row depth |

---

## 👥 Seeded Demo Personas

The system seeds two teams (`Team Alpha`, `Team Beta`) with five role-delineated test personas. Password for all seeded users is:  
`Password123!`

| Persona | Email | Assigned Role | Capabilities |
|---|---|---|---|
| **Alice Admin** | `admin@newtonite.io` | **Admin** (Team Alpha & Beta) | Full management, member assignment, approvals, transitions |
| **Bob Lead** | `lead@newtonite.io` | **Lead** (Team Alpha) | Ticket creation, claiming, transitions, ticket approval |
| **Charlie Engineer** | `engineer@newtonite.io` | **Member** (Team Alpha) | Ticket creation, claiming, transitions (cannot self-approve) |
| **Dana Viewer** | `viewer@newtonite.io` | **Viewer** (Team Alpha) | Read-only inspection; all mutations return `HTTP 403` |
| **Oscar Outsider** | `outsider@newtonite.io` | **Member** (Team Beta) | Isolated to Team Beta; cross-team access blocked |

---

## ⚡ Quick Start

### Option A: Docker Compose (Recommended)

Spins up PostgreSQL 16, backend migrations, demo seeding, and the Nginx-hosted React frontend:

```bash
# 1. Clone the repository
git clone https://github.com/your-org/newtonite.git
cd newtonite

# 2. Start all services
docker compose up --build -d

# 3. Verify health
curl -f http://localhost:8000/health
```

- **Frontend Operations Console**: [http://localhost:3000](http://localhost:3000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option B: Local Development Setup

#### Prerequisites
- Python 3.12+
- Node.js 20+ & npm
- PostgreSQL 16 running on `localhost:5432` with databases `newtonite` and `newtonite_test`

#### 1. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Seed demo users & teams
python -m app.db.seed

# Start FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Automated Test Suite (52/52 Passing)

The project includes a comprehensive test suite covering unit, integration, and parallel stress scenarios:

```bash
cd backend
pytest -v tests
```

```text
collected 52 items

backend/tests/test_activity_integrity.py::test_activity_events_are_append_only_update_rejected PASSED
backend/tests/test_activity_integrity.py::test_activity_events_are_append_only_delete_rejected PASSED
backend/tests/test_activity_integrity.py::test_transaction_rollback_leaves_no_orphaned_activity_event PASSED
backend/tests/test_auth.py (9 tests: Login, Token, RBAC, Seed Idempotency) PASSED
backend/tests/test_claims.py (6 tests: Claim, Viewer 403, 10-Thread Parallel Concurrency) PASSED
backend/tests/test_health.py (2 tests: DB health & outage simulation) PASSED
backend/tests/test_idempotency.py (5 tests: Replay, Hash Mismatch, Concurrent Replay) PASSED
backend/tests/test_membership_management.py (10 tests: Team Role Hierarchy & Scoping) PASSED
backend/tests/test_migrations.py (1 test: Full Upgrade/Downgrade Consistency) PASSED
backend/tests/test_pagination_and_search.py (3 tests: Keyset Cursors & Search Filter) PASSED
backend/tests/test_transitions.py (7 tests: Optimistic Locking, Separation of Duties) PASSED
backend/tests/test_work_items.py (6 tests: Creation, Isolation, Validation) PASSED

====================== 52 passed, 12 warnings in 32.89s =======================
```

---

## 🕹️ Evaluation Demo Walkthrough (3–5 Mins)

Follow this structured script to evaluate all core engineering behaviors:

1. **Quick Login & Role Awareness**:
   - Navigate to [http://localhost:3000](http://localhost:3000) (or `http://localhost:5173`).
   - Click the **Emma / Charlie (Member)** persona card to authenticate instantly.
   - Observe the live backend health status pill in the top navigation bar.

2. **Idempotent Ticket Creation**:
   - Click **+ New Ticket**.
   - Enter `High Priority Outage`, select Type: `BUG`, Priority: `CRITICAL`.
   - Submit the form. Notice the server response in `< 15ms`. Network inspector confirms a fresh `Idempotency-Key` UUID was dispatched.

3. **Atomic Ticket Claiming**:
   - Click on the newly created ticket to open the **Ticket Details Drawer**.
   - Click **Claim Ticket**.
   - Notice the status immediately changes to `IN_PROGRESS`, version advances to `v2`, and the immutable activity timeline records `CLAIMED by Charlie`.

4. **Optimistic Locking Conflict Simulation**:
   - Open a secondary incognito window and log in as **Bob Lead**.
   - In both windows, view the same ticket.
   - In window 1 (Bob), transition the ticket to `AWAITING_APPROVAL`.
   - In window 2 (Charlie), click any action without refreshing.
   - **Result:** The system catches the stale version conflict, displays the **HTTP 409 Conflict Modal**, and offers a one-click reload.

5. **Separation of Duties Verification**:
   - As **Charlie (Creator)**, attempt to approve the ticket to `RESOLVED`.
   - **Result:** The button is disabled with an explanatory tooltip, and the server strictly rejects any direct API attempt with `HTTP 403 Forbidden: Only a Lead or Admin may approve work items (creator self-approval forbidden)`.
   - Switch to **Alice Admin** or **Bob Lead** and click **Approve Ticket**. The transition succeeds.

6. **Append-Only Activity Audit Timeline**:
   - In the drawer, inspect the timeline: `CREATED` $\rightarrow$ `CLAIMED` $\rightarrow$ `STATUS_CHANGED`.
   - Timestamps, actor UUIDs, and transitions are cryptographically unchangeable.

---

## 📁 Repository Structure

```text
newtonite/
├── .github/workflows/ci.yml       # CI Pipeline (Postgres 16, Migrations, Pytest, Vite)
├── docker-compose.yml             # Orchestration: db + backend + frontend
├── ENGINEERING_DECISIONS.md       # Deep architectural decisions, trade-offs & benchmark proofs
├── README.md                      # Project documentation & evaluation guide
│
├── backend/
│   ├── alembic/versions/          # 3 schema migrations (initial, trigger, performance indexes)
│   ├── app/
│   │   ├── api/routes/            # auth, health, teams, work-items
│   │   ├── core/                  # config (pydantic-settings), security (bcrypt/jwt)
│   │   ├── db/                    # session, seed, base declarative
│   │   ├── models/                # User, Team, Membership, WorkItem, ActivityEvent, IdempotencyKey
│   │   ├── schemas/               # Typed Pydantic request/response models
│   │   └── services/              # work_item, auth, authorization, workflow, idempotency, activity
│   ├── scripts/
│   │   ├── scale_benchmark.py     # 50,000-record benchmark suite
│   │   └── start.sh               # Container entrypoint with health polling
│   └── tests/                     # 52 automated tests covering all requirements
│
└── frontend/
    ├── src/
    │   ├── api/client.ts          # Centralized typed API client & error normalizer
    │   ├── components/            # ConflictModal, CreateTicketModal, Drawer, Navbar, Badges
    │   ├── context/AuthContext.tsx# Demo persona authentication & token session store
    │   ├── pages/                 # Dashboard (metrics, keyset table) & Login
    │   └── types/index.ts         # Shared TypeScript domain contracts
    ├── Dockerfile                 # Multi-stage build (Node 22 -> Nginx Alpine)
    └── nginx.conf                 # SPA routing fallback & backend proxy
```

---

## ⚖️ License & Integrity Notice

Developed as a high-concurrency software engineering benchmark solution.  
All concurrency, idempotency, and audit immutability guarantees are enforced at the database level and verified with automated test suites.
