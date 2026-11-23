# Campus Connect API

Flask API backed by Supabase, following `apiendpoint.png` and `database.png`.
The database fields match the diagram: users, events, and registrations.

## Run it

1. In the Supabase SQL Editor, run [`schema.sql`](schema.sql).
2. Copy `.env.example` to `.env` and set `SUPABASE_URL` and
   `SUPABASE_PUBLISHABLE_KEY` from your Supabase project.
3. Install dependencies and start Flask:

   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```

The API listens on `http://localhost:5000`. Keep `.env` private. The server
uses only the publishable key; do not put a Supabase secret/service-role key in
this app's environment.

## Endpoints

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/events` | Browse events; supports `page`, `per_page` (max 100), and optional `status`. |
| GET | `/api/events/{id}` | Event details. |
| POST | `/api/registrations` | Register a user for an event. JSON: `{"user_id":"<uuid>","event_id":"<uuid>"}`. Returns 201; returns 409 for duplicate registration or full event. |
| GET | `/api/me/registrations?user_id={uuid}` | List registrations for the supplied user; supports pagination. |
| GET | `/api/events/{id}/registrations` | List event attendees, including their IDs and emails; supports pagination. |

Responses use JSON. List responses have `data`, `page`, and `per_page`; single
items have `data`; errors have `error`.

## No authentication or authorization

This follows your request to omit authentication and authorization, even though
the endpoint diagram labels registration and private lists as requiring
authentication. The `user_id` is supplied by the caller and is not verified.
Anyone who can reach the API can register as any user and view any user's
registrations and any event's attendee list. The SQL enables RLS with public
read access and public registration inserts so the publishable key can reach
the tables. Use this only where that open access is intended.

The registration endpoint calls a database function that serializes signups
per event and enforces the capacity and duplicate-registration constraints.
Create user rows and events in Supabase before using the endpoints; this API
does not include user or event creation routes because they are absent from the
provided endpoint diagram.
