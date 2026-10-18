# Workplace Booking (FastAPI + PostgreSQL)

Site + API in one app. Accounts, bookings and settings are stored in PostgreSQL.
The site is served from `static/index.html`, so there is nothing else to host.

## Run (Docker)

    cp .env.example .env
    docker compose up --build

- Site: http://localhost:8000 (API docs: http://localhost:8000/docs)
- Mailpit (catches every email in dev): http://localhost:8025

Open the site, press **Book**, register with an Outlook address. The 6-digit code appears in Mailpit.

## Run without Docker (SQLite, for quick tests)

    uv sync
    uv run uvicorn app.main:app --reload      # uses ./dev.db, codes are printed in the terminal
    uv run pytest -q

## Codes and booking emails in a real Outlook inbox

Set the `SMTP_*` variables in `.env` to any SMTP provider (Brevo, Resend, SendGrid, Gmail app password...).
The recipient can be any Outlook/Hotmail/Live address. Send from a domain with SPF/DKIM so mail does not land in Junk.
If `SMTP_HOST` is empty, emails are only printed in the log (dev mode).

## What it does

- Register (Outlook addresses only) -> 6-digit code by email -> the account is created only after the code is confirmed.
- Login: Outlook email + password. JWT access token (15 min) + refresh token with rotation.
- Seats: 100+ seats from the floor plan (`app/seed.py`, ids `s1`, `s2`...). Availability per date: free (green), booked by someone else (red), yours (orange).
- Booking: 09:00-18:00 by default (`start`/`end` supported by the API for hourly). No double booking: service check + a PostgreSQL `EXCLUDE USING gist` constraint.
- Emails with the date and time on booking and on cancellation (can be switched off in Settings).
- Profile page (edit name/phone, upcoming bookings, cancel) and Settings (theme, email notifications).

## API (`/api/v1`)

    POST /auth/register  /auth/resend  /auth/verify  /auth/login  /auth/refresh  /auth/logout
    GET|PATCH /users/me
    GET /seats    GET /seats/availability?date=YYYY-MM-DD
    POST /bookings    GET /bookings/me    PATCH /bookings/{id}/cancel

## Still to do

- Alembic is set up (`alembic/`); on PostgreSQL the container runs `alembic upgrade head` at start.
- Hourly booking in the UI, check-in with automatic cancel, the AI voice agent (see the plan document).
- Microsoft Graph as an alternative to SMTP.
- Check that `btree_gist` is available on your PostgreSQL host (Neon, Supabase, Render...).
