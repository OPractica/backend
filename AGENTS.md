# AGENTS.md

Backend of Voice Office Booking: employees book office desks on an SVG map or by voice. FastAPI, async SQLAlchemy 2 with asyncpg, PostgreSQL 16, Alembic, pydantic-settings, uv, Python 3.11.

## Commands

```bash
uv sync                                            # install dependencies
cp .env.example .env                               # then fill in the values
docker compose up -d db                            # start PostgreSQL
uv run fastapi dev app/main.py                     # API with docs at http://localhost:8000/docs
uv run ruff check --fix . && uv run ruff format .  # CI fails on any ruff error
uv run pytest                                      # tests
```

## Where things go

- `app/api/v1/`: thin routers. Take the input, call a service or crud function, return a schema.
- `app/services/`: business logic, like booking rules. `app/crud/`: database queries.
- `app/models/`: SQLAlchemy models. `app/schemas/`: Pydantic schemas.
- `app/core/config.py`: settings. A new setting goes into `Settings` and `.env.example`, never hardcoded.
- `app/core/db.py`: the database session. Use `SessionDep` in endpoints.

## Read when relevant

- Branches, commit messages, pull requests, CI checks: `CONTRIBUTING.md`
- Pull request description: `.github/PULL_REQUEST_TEMPLATE.md`
- What to build and when it's done: the GitHub issue, `gh issue view <number>`

## Never

- Never push to `main` or `release`, force-push, or merge pull requests. Work in a task branch and open a pull request, as described in `CONTRIBUTING.md`.
- Never commit or print secrets. Don't read `.env` values into the chat or logs. Never commit `__pycache__`, `*.db` or other generated files.
- Never change `.github/`, `CONTRIBUTING.md`, `AGENTS.md` or repository settings unless the task is about them. Never turn off a ruff rule or a CI check to make CI pass. Fix the code instead.
- Never add `Co-Authored-By` trailers or "Generated with" lines to commits or pull requests.

## Use your judgment

- Stay inside the task. If you notice something else worth fixing, mention it instead of fixing it in the same pull request.
- Read the nearby code first and write in the same style. A small change to an existing file beats a new layer or abstraction.
- Ask before big or shared changes: a new dependency, a change to models or the database schema, or rewriting someone else's code.
- Before you say the work is done, run ruff and the related tests, and say plainly what you didn't check.
