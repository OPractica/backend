# Voice Office Booking: backend

The API behind Voice Office Booking. Employees book office desks and meeting rooms on an SVG floor map, by typing a request, or by voice through an AI assistant. This service stores users, desks, meeting rooms and bookings in PostgreSQL, applies the booking rules, runs the AI assistant and sends booking emails.

Stack: FastAPI, async SQLAlchemy 2 with asyncpg, PostgreSQL 16, Alembic, pydantic-settings, LangChain and LangGraph, uv, Python 3.11.

The web client lives in [OPractica/frontend](https://github.com/OPractica/frontend).

## Architecture

[![Backend architecture: the frontend calls the REST, AI chat and voice routers; services and CRUD read and write PostgreSQL; the AI chat runs a LangGraph dialog, a booking agent with an LLM and tools; voice goes to Groq Whisper; emails go through Microsoft Graph or SMTP](docs/architecture.svg)](docs/architecture.svg)

*The routers in `app/api/v1` stay thin and call `app/services` and `app/crud`. The AI assistant in `app/ai` books through the same services as the REST API. Click the image to open it at full size.*

```
app/
  api/v1/     routers: auth, seats, bookings, meeting, health, ai, voice
  services/   booking rules, meeting rooms, email, voice processing, preference parser
  crud/       database queries for users, seats and refresh tokens
  models/     SQLAlchemy models
  schemas/    Pydantic schemas
  ai/         AI assistant: LangGraph dialog, agent, tools, LLM provider, chat memory
  core/       settings, database session, password hashing and JWT
alembic/      database migrations
scripts/      developer scripts, including the local database reset
tests/        pytest tests
```

## Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose, for PostgreSQL and Mailpit (or for the whole stack)

## Setup

```bash
uv sync
cp .env.example .env
```

Then fill in `.env`. Never commit it. The table lists every setting from `.env.example` and `app/core/config.py`. Names are case-insensitive.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | yes | | Database connection, `postgresql+asyncpg://<user>:<password>@<host>:5432/<db>`. Use `localhost` for the local Docker database. For a cloud database such as Supabase, add `?ssl=require` |
| `JWT_SECRET` | yes | | Key that signs access tokens (HS256). Use a random string of at least 32 bytes, for example from `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GROQ_API_KEY` | yes | | Groq API key for voice transcription. The app doesn't start without it; any value works if you don't use voice |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | for Docker | `office`, `office`, `office_booking` | Credentials of the `db` container in `docker-compose.yml` |
| `GOOGLE_API_KEY` | for the AI chat with Gemini | empty | Gemini API key. Without it `/ai/chat` answers `503` |
| `LLM_PROVIDER` | no | `gemini` | `gemini` (cloud) or `ollama` (local model) |
| `LLM_MODEL` | no | `gemini-3.5-flash-lite` | Model name for the chosen provider |
| `LLM_FALLBACK_MODELS` | no | `gemini-3.1-flash-lite,gemini-3.5-flash` | Comma-separated Gemini models to try when the main one fails |
| `OLLAMA_BASE_URL` | no | `http://localhost:11434` | Ollama server, used when `LLM_PROVIDER=ollama` |
| `OFFICE_TIMEZONE` | no | `Europe/Chisinau` | Time zone of the office for booking rules and the assistant |
| `ACCESS_TOKEN_MINUTES` | no | `15` | Access token lifetime |
| `REFRESH_TOKEN_DAYS` | no | `7` | Refresh token lifetime |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated frontend origins allowed to call the API |
| `CORS_ORIGIN_REGEX` | no | empty | Extra origin pattern, for example for preview deployments |
| `SMTP_HOST`, `SMTP_PORT` | no | `localhost`, `1025` | SMTP server. The defaults point to Mailpit |
| `SMTP_USER`, `SMTP_PASSWORD` | no | empty | SMTP login. When `SMTP_USER` is set, the connection uses STARTTLS |
| `EMAIL_FROM` | no | `noreply@office-booking.local` | Sender address for SMTP |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER` | no | empty | Microsoft Graph mail. When all four are set, emails go through Graph and fall back to SMTP on error |
| `OFFICE_OPEN_HOUR`, `OFFICE_CLOSE_HOUR` | no | `9`, `19` | Office hours for bookings |
| `BOOKING_MIN_MINUTES`, `BOOKING_MAX_HOURS` | no | `15`, `10` | Shortest and longest booking |
| `CHECKIN_MINUTES` | no | `10` | Minutes after the start of a desk booking to check in before it is cancelled |
| `BOOKING_RETENTION_DAYS` | no | `30` | Cancelled bookings created earlier than this are deleted |

The last four rows aren't in `.env.example`. Add them only to change the defaults.

## Run with Docker

```bash
docker compose up --build
```

This starts three containers:

- `db`: PostgreSQL 16 on port 5432, data in the `pgdata` volume
- `api`: runs `alembic upgrade head`, then serves the API on port 8000
- `mailpit`: catches outgoing emails, web UI at http://localhost:8025

The `api` container reads `.env`, but `docker-compose.yml` overrides two values: it connects to `postgresql+asyncpg://office:office@db:5432/office_booking` and sends mail to `mailpit`. So for this setup keep `POSTGRES_USER=office`, `POSTGRES_PASSWORD=office` and `POSTGRES_DB=office_booking` in `.env`.

Open http://localhost:8000/docs.

## Run locally

Start the database (and Mailpit, if you want to see emails), apply the migrations and start the API with auto-reload:

```bash
docker compose up -d db mailpit
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

`DATABASE_URL` in `.env` must use `localhost` and the same user, password and database as `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`. The API runs at http://localhost:8000, the docs at http://localhost:8000/docs.

## Database migrations

Alembic reads `DATABASE_URL` from `.env`.

```bash
uv run alembic upgrade head                                # apply all migrations
uv run alembic revision --autogenerate -m "add something"  # new migration after a model change
uv run alembic heads                                       # must show one head
```

Pull the latest `main` before you generate a migration. If `alembic heads` shows two heads, merge them with `uv run alembic merge heads`. See [CONTRIBUTING.md](CONTRIBUTING.md#database-migrations).

## Seed data

> [!WARNING]
> `scripts/dev_reset_db.py` deletes all data in the database from `DATABASE_URL`. Use it only on your local database.

```bash
uv run python -m scripts.dev_reset_db
```

The script:

- refuses to run when the database host isn't `localhost`, `127.0.0.1` or `::1`
- drops and recreates the tables from the SQLAlchemy models (not through Alembic) and enables the `btree_gist` extension
- adds 12 desks on floor 7 (`7-A01` to `7-D02`) in the window, quiet, open and cozy zones, with attributes like window, quiet, monitors and dock
- adds five meeting rooms to office 1, the office the AI assistant and the frontend use: three rooms for 6 to 10 people, all with a TV and two with a whiteboard, and two one-person booths
- adds one user, `test.user@orange.local`, with a placeholder password hash, so you can't log in as this user

To log in, register your own user with `POST /api/v1/auth/register`.

## Lint and tests

CI runs ruff and pytest on every pull request. Fix lint and formatting before you push:

```bash
uv run ruff check --fix . && uv run ruff format .
```

Tests need a running PostgreSQL:

```bash
docker compose up -d db
uv run pytest
```

The tests create their own database next to the one in `DATABASE_URL`, with a `_test` suffix (for example `office_booking_test`), and rebuild its tables on every run. CI runs them without real Groq or Gemini keys, but the settings still need `DATABASE_URL`, `GROQ_API_KEY` (any value) and `JWT_SECRET`.

## API overview

All endpoints are under `/api/v1`. The interactive docs at http://localhost:8000/docs (Swagger) and the schema at `/openapi.json` are generated from the code. [API_CONTRACT.md](API_CONTRACT.md) explains authorization, the error format, dates and a typical frontend flow. When the two disagree, trust `/docs`.

| Group | Endpoints | Login |
|---|---|---|
| Health | `GET /health/live` (process is up), `GET /health` (database is reachable) | no |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | only `/auth/me` |
| Seats | `GET /seats`, `GET /seats/availability` | no |
| Desk bookings | `POST /bookings`, `GET /bookings/me`, `PATCH /bookings/{booking_id}/cancel`, `POST /bookings/{booking_id}/check-in` | yes |
| Meeting rooms | `GET /meeting/getMeetingRoomsWithStatusByOfficeId`, `GET /meeting/getBusyMeetingRoomsByOfficeId` | no |
| Meeting room bookings | `POST /meeting/bookings`, `GET /meeting/bookings/me`, `PATCH /meeting/bookings/{booking_id}/cancel` | yes |
| AI assistant | `POST /ai/chat` | yes |
| Voice | `POST /voice/transcribe` | yes |

- Protected endpoints take `Authorization: Bearer <access_token>`. `POST /auth/login` returns an access token and a refresh token. A refresh token works once: `POST /auth/refresh` returns a new pair, and reusing an old refresh token revokes the whole login session.
- Every error has the same shape: `{"detail": "...", "code": "..."}`.
- Booking rules: weekdays only, inside office hours, start and end on the same day, not in the past, from 15 minutes to 10 hours, no overlapping bookings.
- Check-in for a desk booking opens 5 minutes before the start. A background task checks every minute and cancels desk bookings without check-in `CHECKIN_MINUTES` after the start. Once a day it deletes old cancelled bookings.

## AI assistant

The code is in `app/ai/`. `POST /ai/chat` takes `{"text": "...", "session_id": "...", "language": "ru"}`, where `session_id` and `language` are optional, and returns `{"answer": "...", "session_id": "..."}`. Send the `session_id` back to continue the conversation.

- **Chat memory.** The history of each conversation is stored in the `ai_chat_sessions` table, keyed by user and `session_id`, so a user can't open someone else's conversation. The model gets the last 60 messages. Conversations older than 7 days are deleted. If the database fails, the assistant falls back to an in-memory copy of the history.
- **LangGraph dialog** (`graph.py`). First, code picks the reply language: the `language` from the request, otherwise the language of the user's messages (Russian, Romanian or English). If the assistant asked to confirm a cancellation and the user answers yes, code cancels the booking without the model. A no keeps the booking. Any other message goes to the agent.
- **Agent** (`agent.py`). A LangChain agent with a system prompt that only allows searching, booking and cancelling desks and meeting rooms, and refuses everything else. The prompt contains the current date, a small calendar and the office hours. The agent retries a failed model call once.
- **Tools** (`tools.py`). `search_free_seats`, `book_seat`, `cancel_my_booking`, `list_my_bookings`, `search_free_meeting_rooms` (by number of people and equipment), `book_meeting_room`, `cancel_meeting_room_booking` and `list_my_meeting_room_bookings`. They call the same booking services as the REST API. The current user's id is built into the tools, so the model can't book or cancel for someone else. In the chat, the cancel tools don't cancel anything: they return the booking, and the dialog asks the user to confirm.
- **LLM provider** (`llm.py`). `LLM_PROVIDER=gemini` uses Google Gemini with `GOOGLE_API_KEY` and switches to `LLM_FALLBACK_MODELS` when the main model fails. `LLM_PROVIDER=ollama` uses a local model from `OLLAMA_BASE_URL`, without fallback models. When the provider hits a rate limit, `/ai/chat` answers `429`, and when it's not configured or fails, `503`.
- **Voice** (`app/services/voice/`). `POST /voice/transcribe` takes an audio file (flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav or webm, up to 24 MB) and an optional `language` (`auto`, `ru`, `ro` or `en`). It transcribes the audio with Groq Whisper (`whisper-large-v3-turbo`) and extracts desk preferences from the text (near a window, quiet, two monitors, docking station, cozy). It returns the text, the language and the preferences. It doesn't book anything: the frontend sends the text on to `/ai/chat`. The audio file goes to `audio_storage/` and a row to `voice_records`. Both are deleted after 24 hours.
- **Booking emails** (`app/services/email.py`). Booking or cancelling a desk sends a confirmation or cancellation email, both through the REST API and through the assistant (then the email says it was done with the AI assistant). Meeting room bookings don't send emails. A failed email is logged and doesn't affect the booking.

To try the agent without the frontend, run `uv run python -m scripts.chat_cli` (add `--trace` to see the tool calls). `uv run python -m scripts.check_llm` checks the connection to the model.

## Contributing

Branches, commit messages, pull requests and CI checks are described in [CONTRIBUTING.md](CONTRIBUTING.md). Rules for AI coding agents are in [AGENTS.md](AGENTS.md).
