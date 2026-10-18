# Contributing (backend)

## Setup
    uv sync                      # installs Python 3.12 deps from uv.lock
    cp .env.example .env         # then: uv run python -m scripts.gen_secret  -> SECRET_KEY
    uv run uvicorn app.main:app --reload     # SQLite (dev.db) if DATABASE_URL is not set
    docker compose up --build    # PostgreSQL + Mailpit (emails at http://localhost:8025)

## Branches and pull requests
- `main` is always working. `release` is what goes to production. `bugfix/<name>` fixes bugs.
- One branch per task: `feat/<name>`, `fix/<name>`. Open a pull request into `main`; CI must be green.
- Commit messages: `feat:`, `fix:`, `docs:`, `chore:`, `style:`, `revert:`.

## Before you push
    uv run ruff check . --fix && uv run ruff format .
    uv run pytest -q

## Database changes
Never edit tables by hand. Change `app/models.py`, then:

    uv run alembic revision --autogenerate -m "what changed"
    uv run alembic upgrade head

Check the generated file in `alembic/versions/` before committing.

## Layout
    app/api/v1   routes (thin: no business logic)
    app/services business logic
    app/core     settings, security
    alembic/     migrations        scripts/  dev helpers
