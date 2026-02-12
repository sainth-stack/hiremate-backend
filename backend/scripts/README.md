# Database Setup

## 1. Create the database on Neon

Your `.env` uses `DATABASE_URL` with database name `hiremate`. If that database doesn't exist:

1. Go to [Neon Dashboard](https://console.neon.tech) → your project
2. Open **SQL Editor**
3. Connect to the **default database** (e.g. `neondb`)
4. Run: `CREATE DATABASE hiremate;`

## 2. Run migrations

From **project root** (hiremate-backend/):

```bash
pip install -r backend/requirements.txt
PYTHONPATH=. alembic -c backend/alembic.ini upgrade head
```

Or with venv:
```bash
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=. .venv/bin/alembic -c backend/alembic.ini upgrade head
```

## 3. Create new migrations (after changing models)

From project root:

```bash
PYTHONPATH=. alembic -c backend/alembic.ini revision --autogenerate -m "description of changes"
PYTHONPATH=. alembic -c backend/alembic.ini upgrade head
```
