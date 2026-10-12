# Health Chart Backend

Python + FastAPI + PostgreSQL backend for an offline-first hospital records
system.

## Stack

- FastAPI with OAuth2 bearer authentication
- SQLAlchemy 2.0 and Alembic
- PostgreSQL via psycopg 3
- bcrypt password hashing and python-jose JWTs
- pytest with isolated in-memory SQLite test fixtures

## Roles

- **administrator**: all API endpoints, including user management and reports
- **clinician**: patients, appointments, consultations, prescriptions and sync
- **pharmacist**: prescriptions, drug stock and sync
- **registry_officer**: patients, appointments and sync

Sync requests are limited to the same entity permissions as the corresponding
resource endpoints. Self-registration creates a `registry_officer` account and
requires an existing `clinic_id`. Administrators can create accounts with
arbitrary roles through `POST /api/v1/users`.

## Local setup

1. Start PostgreSQL and create an application database. For example:

   ```bash
   docker run --name health-chart-db -e POSTGRES_PASSWORD=devpassword \
     -p 5432:5432 -d postgres:16
   docker exec -it health-chart-db psql -U postgres -c \
     "CREATE USER health_chart WITH PASSWORD 'devpassword' CREATEDB;"
   docker exec -it health-chart-db psql -U postgres -c \
     "CREATE DATABASE health_chart OWNER health_chart;"
   ```

2. Copy `.env.example` to `.env`, configure `DATABASE_URL`, and replace
   `SECRET_KEY` with a unique random secret. Never commit `.env`; rotate its
   signing key if it has been shared.

3. Install dependencies, migrate the database, and optionally seed local data:

   ```bash
   uv sync
   uv run alembic upgrade head
   uv run python -m scripts.seed
   ```

   The idempotent seed command creates one clinic and four role-specific
   sample users. The administrator is `r.mwape` / `adminpass123`; other sample
   accounts use `password123`. Do not use these credentials in production.

4. Run the server:

   ```bash
   uv run fastapi dev app/main.py
   ```

   Open `http://127.0.0.1:8000/docs` for the API documentation.

## Running tests

```bash
uv run pytest
```

Tests use an isolated in-memory SQLite database and do not require a running
PostgreSQL instance.

## Container

Build the API image from the repository root:

```bash
docker build -f dockerfile -t health-chart-api .
```

## Migrations

After changing a model in `app/models/`:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Review generated migrations before applying them.
