# Voice Office Booking: API Contract for the Frontend

Based on the current `origin/main` (includes PR #78 `/ai/chat` and PR #82 refresh token reuse detection).
The auto-generated schema is always available at `GET /docs` and `GET /openapi.json`;
a client can be generated from `openapi.json`.

## General

| | |
|---|---|
| Base URL (local) | `http://localhost:8000/api/v1` |
| Base URL (Render) | `https://opractica-office-booking-api.onrender.com/api/v1` |
| Format | JSON, `Content-Type: application/json` |
| Office time zone | `Europe/Chisinau` |

### Authorization

Protected endpoints (marked 🔒) require the header:

```
Authorization: Bearer <access_token>
```

- The `access_token` lives for **15 minutes**, the `refresh_token` for **7 days**.
- When the `access_token` expires, any 🔒 endpoint returns `401` with `detail: "token expired"`.
  Then call `POST /auth/refresh`, store the new token pair and repeat the request.
- A refresh token is **single-use** (rotation): after `/auth/refresh` the old one stops working,
  so always save the new one. If an old token is used again, the server treats it as stolen
  and revokes all tokens of that login session (the user has to log in again).
- `401` on a 🔒 endpoint: `{"detail": "token expired" | "invalid token"}`.
- `403` `{"detail": "user is not active"}`: the user is deactivated.

### Error format

All errors: `{"detail": "<text>"}`.
Validation errors (`422`) use the standard FastAPI format:

```json
{"detail": [{"type": "...", "loc": ["body", "email"], "msg": "...", "input": "..."}]}
```

There is no unified `code` field yet (issue #25).
Note: `detail` texts of booking rule errors are currently in Russian. Do not rely on the text for logic;
rely on the status code (see `POST /bookings`).

### Dates and time

- Send dates in ISO 8601 **with a time zone**: `2026-11-10T09:00:00+02:00` or with `Z`.
- In `GET /seats/availability` a time without a zone is treated as office time (`Europe/Chisinau`).
- In `POST /bookings` the server does not apply the office zone to a time without a zone
  (unlike `/seats/availability`); the result for such a time was not verified. Always include the offset.
- Responses contain ISO 8601 dates with a zone. Convert to office time on the client for display.

### CORS

CORS is **not available on `main` yet** (issue #25, in progress on branch `feat/25-cors`). The allowed
origins will come from the `CORS_ORIGINS` setting. Until it is merged and deployed, browser requests
from another origin are blocked; use a dev-server proxy in the meantime. Tell the backend which
frontend origins you need (production and local dev server, e.g. `http://localhost:5173`).

---

## Health

### `GET /health/live`
Checks that the process is alive. No auth.
- **200** `{"status": "ok"}`

### `GET /health`
Checks the process and the database. No auth.
- **200** `{"status": "ok"}`
- **503** `{"detail": "database unavailable"}`

---

## Auth

### `POST /auth/register`
Registration. No auth. Tokens are **not** issued on registration; call `/auth/login` afterwards.

Request:
```json
{"email": "user@example.com", "password": "string", "full_name": "Ivan Petrov"}
```
| field | type | notes |
|---|---|---|
| `email` | string (email) | lowercased by the server |
| `password` | string | no complexity rules on the server |
| `full_name` | string | |

Responses:
- **201** `User`
- **409** `{"detail": "email is already in use"}`
- **422** invalid email or fields

### `POST /auth/login`
Log in. No auth.

Request: `{"email": "user@example.com", "password": "string"}`

Responses:
- **200** `Tokens`
- **401** `{"detail": "invalid email or password"}`
- **403** `{"detail": "user is not active"}`
- **422**

### `POST /auth/refresh`
Exchange a refresh token for a new token pair. No Authorization header.

Request: `{"refresh_token": "string"}`

Responses:
- **200** `Tokens` (new pair; the old refresh token no longer works)
- **401** `{"detail": "invalid refresh token"}`: the token is unknown, expired, already used,
  or the user is deactivated. The user must log in again.
- **422**

### `POST /auth/logout`
Log out: revokes the given refresh token. No Authorization header.

Request: `{"refresh_token": "string"}`

Responses:
- **204** no body. Always, even if the token is unknown or already revoked.
- **422**

### 🔒 `GET /auth/me`
The current user.
- **200** `User`
- **401**, **403** (see "Authorization")

---

## Seats

### `GET /seats`
List of active seats. No auth.

Query (all optional):
| parameter | type | |
|---|---|---|
| `floor` | int | filter by floor |
| `zone` | string | filter by zone |

- **200** `Seat[]` (order is not guaranteed)

### `GET /seats/availability`
Status of every active seat for a time interval. No auth. Use it to colour the SVG map.

Query (required):
| parameter | type | |
|---|---|---|
| `starts_at` | datetime | start (no zone = office time) |
| `ends_at` | datetime | end, must be later than `starts_at` |

Example: `/seats/availability?starts_at=2026-11-10T09:00:00%2B02:00&ends_at=2026-11-10T10:00:00%2B02:00`
(a `+` in a URL must be encoded as `%2B`).

- **200** `SeatAvailability[]`, ordered by `id`:
  ```json
  [{"id": 1, "label": "A1", "status": "free"}, {"id": 2, "label": "A2", "status": "booked"}]
  ```
- **422** `starts_at` is not earlier than `ends_at` (`detail`: `"starts_at must be earlier than ends_at"`)
  or the parameters are missing

A seat is "booked" if it has a `confirmed` booking overlapping the interval.
Back-to-back bookings (9–10 and 10–11) do not overlap. Cancelled bookings do not block a seat.

---

## Bookings

### 🔒 `POST /bookings`
Create a booking for the current user. A confirmation email is sent to the user
(a failed email does not affect the response).

Request:
```json
{
  "seat_id": 1,
  "starts_at": "2026-11-10T09:00:00+02:00",
  "ends_at": "2026-11-10T10:00:00+02:00",
  "source": "manual"
}
```
| field | type | notes |
|---|---|---|
| `seat_id` | int | id from `/seats` |
| `starts_at`, `ends_at` | datetime **with zone** | |
| `source` | string, default `"manual"` | where the booking came from. The AI agent uses `"ai"`. Send `"manual"` from the map |

Responses:
- **201** `Booking`
- **422** a booking rule is broken. `detail` is a string (currently in Russian). The rules:
  - the end must be later than the start;
  - the start must not be in the past (a 2-minute tolerance);
  - the booking must start and end on the same day;
  - the office is closed on Saturday and Sunday;
  - it must be inside office hours, 09:00–19:00 office time (configurable on the server);
  - maximum duration 10 hours, minimum 15 minutes (configurable on the server);
  - the user must not already have a confirmed booking that overlaps this time.

  Standard validation errors (wrong types, missing fields) also return 422, but with `detail` as a list
  (see "Error format"). Check `typeof detail === "string"` to tell them apart.
- **409** `{"detail": "..."}`: the seat does not exist or is inactive, or it is already booked for that time.
- **401**, **403**

Rules are checked first (422), seat availability afterwards (409).

### 🔒 `GET /bookings/me`
My confirmed bookings that have not ended yet, ordered by `starts_at` ascending.
Cancelled and past bookings are not returned.
- **200** `Booking[]`
- **401**, **403**

### 🔒 `PATCH /bookings/{booking_id}/cancel`
Cancel your own booking. No request body. A cancellation email is sent to the user.

Responses:
- **200** `Booking` (with `status: "cancelled"`)
- **404** `{"detail": "..."}`: the booking does not exist, belongs to someone else
  (the response is intentionally identical), or is already cancelled. Cancelling a past booking is not blocked
- **401**, **403**, **422** (`booking_id` is not a number)

---

## AI chat

### 🔒 `POST /ai/chat`
Send a text message to the assistant. The agent searches for seats, books and cancels
on behalf of the current user and answers in the language of the message (ru, ro, en).
Requests that are not about booking are declined.

Request:
```json
{"text": "Book me a seat by the window tomorrow from 10 to 12", "session_id": null}
```
| field | type | |
|---|---|---|
| `text` | string, 1–2000 characters | |
| `session_id` | string, up to 64, optional | omit in the first message. In following messages send the value from the previous response so the agent remembers the dialog |

Responses:
- **200**
  ```json
  {"answer": "Booked seat A3 on 2026-11-10 10:00–12:00, booking no. 15.", "session_id": "9f1c..."}
  ```
- **401**, **403**
- **422** empty text, text too long, or invalid `session_id`
- **429** `{"detail": "the AI assistant is busy, try again in a minute"}`: model rate limit
- **503** `{"detail": "the AI assistant is temporarily unavailable"}`

Important:
- The response is plain text only, with no structured data. After a booking made through the agent,
  refresh the map and the bookings list with separate requests (`/seats/availability`, `/bookings/me`).
- Dialog history is kept in server memory: after a server restart the context is lost;
  the `session_id` stays accepted, but the agent starts without history.
- A response can take several seconds, show a loading indicator.
- Voice input, clarification options and the "manual input" flag are not implemented yet.

---

## Models

### User
```json
{"id": 1, "email": "user@example.com", "full_name": "Ivan Petrov", "role": "employee", "is_active": true}
```
`role`: string, `"employee"` by default.

### Tokens
```json
{"access_token": "eyJ...", "refresh_token": "Zk3...", "token_type": "bearer"}
```

### Seat
```json
{"id": 1, "label": "A1", "floor": 7, "zone": "window", "is_active": true, "attributes": {"window": true, "quiet": false}}
```
`attributes`: a free-form JSON object. Keys the agent uses: `window`, `quiet`, `monitors`, `dock`.
Zones named in the agent prompt: `window`, `quiet`, `open`, `cozy`.
The actual set is defined by the data in the database. There is no seat map file
(`data/seats.json`, issue #9) and no SVG coordinates yet, so the mapping of `label` or `id`
to SVG elements must be agreed with the backend separately.

### SeatAvailability
```json
{"id": 1, "label": "A1", "status": "free"}
```
`status`: `"free"` | `"booked"`.

### Booking
```json
{
  "id": 15, "user_id": 1, "seat_id": 1,
  "starts_at": "2026-11-10T07:00:00Z", "ends_at": "2026-11-10T08:00:00Z",
  "status": "confirmed", "source": "manual",
  "is_checked_in": false, "created_at": "2026-11-09T12:00:00Z"
}
```
`status`: `"confirmed"` | `"cancelled"`. `source`: `"manual"` | `"ai"`.
`is_checked_in` is currently always `false`; there is no check-in endpoint.

---

## Not implemented yet

- CORS on `main` (#25 in progress) and a unified error format with `code`
- Database-level protection against double booking (#17): the check is done in code only, so two
  simultaneous requests for the same seat can theoretically both succeed
- Seat filters by attributes and ranking (#21)
- Check-in and booking update endpoints (a `BookingUpdate` schema exists, but no route)
- Voice input and recording endpoints (#64, #66, #68 in progress)
- Seat data and coordinates for the map (#9, #10)

## Typical flow

1. `POST /auth/login` → store `access_token` and `refresh_token`.
2. `GET /seats` → draw the map. `GET /seats/availability?...` → colour it for the chosen interval.
3. `POST /bookings` when the user clicks a free seat → on `409` or `422` with a string `detail`, show it.
4. `GET /bookings/me` → "My bookings"; `PATCH /bookings/{id}/cancel` → cancel.
5. On `401 token expired` → `POST /auth/refresh`, repeat the request. If refresh returns `401` → login screen.
6. Chat or voice input: `POST /ai/chat`, then refresh the map and "My bookings".
