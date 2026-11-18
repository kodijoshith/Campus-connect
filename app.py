"""Campus Connect events and registrations API."""

import os
from functools import lru_cache
from uuid import UUID

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from postgrest import APIError
from supabase import Client, create_client

load_dotenv()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set")
    return create_client(url, key)


def api_error(message: str, status: int):
    return jsonify({"error": message}), status


def parse_uuid(value, field: str):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{field} must be a valid UUID")


def positive_int(value, field: str, default: int, maximum: int = 100) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer")
    if parsed < 1:
        raise ValueError(f"{field} must be at least 1")
    return min(parsed, maximum)


def run_query(query):
    try:
        return query.execute().data
    except APIError as error:
        app.logger.warning("Supabase request failed: %s", getattr(error, "message", str(error)))
        raise


@app.errorhandler(404)
def not_found(_error):
    return api_error("Endpoint not found", 404)


@app.get("/")
def index():
    return jsonify({"service": "Campus Connect API", "status": "ok"})


@app.get("/api/events")
def list_events():
    try:
        page = positive_int(request.args.get("page"), "page", 1, 1_000_000)
        per_page = positive_int(request.args.get("per_page"), "per_page", 20)
        query = get_supabase().table("events").select(
            "id,organizer_id,title,capacity,status"
        )
        status_filter = request.args.get("status")
        if status_filter:
            query = query.eq("status", status_filter)
        rows = run_query(
            query.order("title").range((page - 1) * per_page, page * per_page - 1)
        )
        return jsonify({"data": rows, "page": page, "per_page": per_page})
    except ValueError as error:
        return api_error(str(error), 400)
    except RuntimeError as error:
        return api_error(str(error), 503)
    except APIError:
        return api_error("Unable to load events", 502)


@app.get("/api/events/<event_id>")
def get_event(event_id):
    try:
        event_id = parse_uuid(event_id, "event_id")
        rows = run_query(
            get_supabase()
            .table("events")
            .select("id,organizer_id,title,capacity,status")
            .eq("id", event_id)
            .limit(1)
        )
        if not rows:
            return api_error("Event not found", 404)
        return jsonify({"data": rows[0]})
    except ValueError as error:
        return api_error(str(error), 400)
    except RuntimeError as error:
        return api_error(str(error), 503)
    except APIError:
        return api_error("Unable to load event", 502)


@app.post("/api/registrations")
def create_registration():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return api_error("Request body must be a JSON object", 400)
    try:
        user_id = parse_uuid(payload.get("user_id"), "user_id")
        event_id = parse_uuid(payload.get("event_id"), "event_id")
        result = get_supabase().rpc(
            "register_for_event",
            {"p_user_id": user_id, "p_event_id": event_id},
        ).execute().data
        registration = result[0] if isinstance(result, list) and result else result
        return jsonify({"data": registration}), 201
    except ValueError as error:
        return api_error(str(error), 400)
    except RuntimeError as error:
        return api_error(str(error), 503)
    except APIError as error:
        code = getattr(error, "code", None)
        message = getattr(error, "message", str(error)).lower()
        if code == "P0002" or "event_not_found" in message:
            return api_error("Event not found", 404)
        if code == "23503":
            return api_error("User not found", 404)
        if "already_registered" in message or code == "23505":
            return api_error("User is already registered for this event", 409)
        if "event_full" in message:
            return api_error("Event has reached capacity", 409)
        app.logger.warning("Registration failed: %s", message)
        return api_error("Unable to create registration", 502)


@app.get("/api/me/registrations")
def list_user_registrations():
    try:
        user_id = parse_uuid(request.args.get("user_id"), "user_id")
        page = positive_int(request.args.get("page"), "page", 1, 1_000_000)
        per_page = positive_int(request.args.get("per_page"), "per_page", 20)
        rows = run_query(
            get_supabase()
            .table("registrations")
            .select("id,user_id,event_id,created_at,event:events(id,title,status)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range((page - 1) * per_page, page * per_page - 1)
        )
        return jsonify({"data": rows, "page": page, "per_page": per_page})
    except ValueError as error:
        return api_error(str(error), 400)
    except RuntimeError as error:
        return api_error(str(error), 503)
    except APIError:
        return api_error("Unable to load registrations", 502)


@app.get("/api/events/<event_id>/registrations")
def list_event_registrations(event_id):
    try:
        event_id = parse_uuid(event_id, "event_id")
        page = positive_int(request.args.get("page"), "page", 1, 1_000_000)
        per_page = positive_int(request.args.get("per_page"), "per_page", 20)
        rows = run_query(
            get_supabase()
            .table("registrations")
            .select("id,user_id,event_id,created_at,user:users(id,email)")
            .eq("event_id", event_id)
            .order("created_at")
            .range((page - 1) * per_page, page * per_page - 1)
        )
        return jsonify({"data": rows, "page": page, "per_page": per_page})
    except ValueError as error:
        return api_error(str(error), 400)
    except RuntimeError as error:
        return api_error(str(error), 503)
    except APIError:
        return api_error("Unable to load event registrations", 502)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
