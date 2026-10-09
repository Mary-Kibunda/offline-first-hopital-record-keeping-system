# Health Chart — Backend

Python + FastAPI + PostgreSQL backend for the offline-first hospital
records system. This is the central server the Next.js frontend's sync
engine talks to — see the main project proposal for the full architecture.

## Stack

- **FastAPI** (`fastapi[standard]`) — REST API
- **SQLAlchemy 2.0** — ORM, using the modern `Mapped[]`/`mapped_column()` style
- **PostgreSQL** via `psycopg` (v3) — central database
- **Alembic** — schema migrations
- **bcrypt** (used directly, not via passlib — see note below) — password hashing
- **PyJWT** — auth tokens
- **pytest** + real PostgreSQL — the test suite runs against an actual
  Postgres database (`health_chart_test`), not SQLite-in-memory, so the
  tests reflect what production actually does

### Why bcrypt directly, not passlib

`passlib` (last released 2020) is incompatible with `bcrypt>=4.1` — its
internal version-detection code raises a spurious "password cannot be
longer than 72 bytes" error even for short passwords, because it expects an
attribute (`bcrypt.__about__`) modern bcrypt no longer ships. This is a
known, unresolved upstream issue. `app/core/security.py` calls `bcrypt`
directly instead, and explicitly rejects (rather than silently truncates)
passwords over bcrypt's real 72-byte limit.

## Project layout

```
app/
├── main.py              FastAPI app instance, CORS, router mounting
├── core/
│   ├── config.py        Settings (reads .env / environment variables)
│   ├── database.py      SQLAlchemy engine, session factory, Base
│   └── security.py      Password hashing (bcrypt) + JWT create/verify
├── models/               One SQLAlchemy model per entity + SyncMixin
├── schemas/              Pydantic request/response models
├── api/
│   ├── deps.py           get_current_user, require_roles
│   └── v1/               One router per resource + the aggregator
└── services/             Business logic kept out of the route handlers
    ├── auth_service.py
    ├── sync_service.py    The conflict-detection policy — see its docstring
    └── report_service.py
alembic/                  Migrations (env.py wired to app.core.config)
scripts/seed.py            Creates a sample clinic + 3 users for local dev
tests/                     36 tests, ~90% coverage, run against real Postgres
```

## Local setup

1. **Install [uv](https://docs.astral.sh/uv/)** if you don't have it:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Start PostgreSQL** (two databases: one for the app, one for tests):
   ```bash
   docker run --name health-chart-db -e POSTGRES_PASSWORD=devpassword \
     -p 5432:5432 -d postgres:16
   docker exec -it health-chart-db psql -U postgres -c \
     "CREATE USER health_chart WITH PASSWORD 'devpassword' CREATEDB;"
   docker exec -it health-chart-db psql -U postgres -c \
     "CREATE DATABASE health_chart OWNER health_chart;"
   docker exec -it health-chart-db psql -U postgres -c \
     "CREATE DATABASE health_chart_test OWNER health_chart;"
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   ```

4. **Install dependencies and run migrations**:
   ```bash
   uv sync
   uv run alembic upgrade head
   ```

5. **Seed some local data** (optional, but the fastest way to get a login):
   ```bash
   uv run python -m scripts.seed
   ```
   Creates one clinic and three users, all with password `password123`
   except the admin (`r.mwape` / `adminpass123`).

6. **Run it**:
   ```bash
   uvicorn main:app --reload
   ```
   Visit `http://127.0.0.1:8000/docs` for the interactive API docs.

## Running tests

```bash
DATABASE_URL=postgresql+psycopg://health_chart:devpassword@localhost:5432/health_chart_test \
  uv run alembic upgrade head   # once, to create the test DB's schema

uv run pytest                       # run the suite
uv run pytest --cov=app --cov-report=term-missing   # with coverage
```

Each test runs inside a transaction that's rolled back afterwards, so the
suite can be run repeatedly without resetting the database by hand.

## Adding a migration

After changing a model in `app/models/`:
```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```
Always read the generated migration file before applying it — autogenerate
is a strong starting point, not a guarantee.

## The sync protocol, briefly

- `POST /api/v1/sync/push` — a device sends a batch of locally
  created/edited records (each carrying its own client-generated UUID and
  version number). Each item comes back as `created`, `updated`,
  `conflict`, or `rejected`.
- `GET /api/v1/sync/pull?since=<timestamp>` — returns every record changed
  after `since`, across all syncable entities.
- `GET /api/v1/sync/log` — returns the authenticated user's sync history;
  administrators can review all users' history, with the owner shown per row.
- `POST /api/v1/sync/conflicts/{entity_type}/{entity_id}/resolve` — applies
  a staff member's manual "keep this device's version" / "keep server
  version" decision.

The full conflict-detection policy is documented in the docstring at the
top of `app/services/sync_service.py`.