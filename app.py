#!/usr/bin/env python3
"""
Real-Time Polling & Survey Platform
Flask Backend Application
"""

import os
import uuid
import hashlib
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    abort,
    g,
    Response,
    redirect,
    url_for,
)

# Load environment variables
load_dotenv()

from db import get_db, close_db, init_db, get_db_path

app = Flask(__name__)

# Configuration
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-dev-secret-key-change-in-prod")
app.config["DATABASE_PATH"] = os.getenv("DATABASE_PATH", "polling.db")
app.config["IP_HASH_SALT"] = os.getenv("IP_HASH_SALT", "default-salt-value")
app.config["ENFORCE_IP_LIMIT"] = os.getenv("ENFORCE_IP_LIMIT", "true").lower() in ("true", "1", "yes")

# Register database teardown
app.teardown_appcontext(close_db)


@app.template_filter("format_date")
def format_date_filter(val: Any) -> str:
    """Format datetime or string timestamp to YYYY-MM-DD."""
    if not val:
        return "Recently"
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]


@app.before_request
def ensure_voter_token() -> None:
    """Ensure every visitor receives a unique persistent voter token."""
    token = request.cookies.get("voter_token")
    if not token:
        g.voter_token = str(uuid.uuid4())
        g.is_new_voter_token = True
    else:
        g.voter_token = token
        g.is_new_voter_token = False


@app.after_request
def set_voter_token_cookie(response: Response) -> Response:
    """Attach the HttpOnly voter_token cookie if it was newly minted."""
    if getattr(g, "is_new_voter_token", False):
        response.set_cookie(
            "voter_token",
            g.voter_token,
            max_age=365 * 24 * 3600,  # 1 year
            httponly=True,
            samesite="Lax",
        )
    return response


def get_client_ip() -> str:
    """Extract client IP respecting reverse proxies (e.g., Render, Nginx)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def compute_ip_hash() -> str:
    """Compute SHA-256 hash of client IP with server salt. Never stores raw IP."""
    client_ip = get_client_ip()
    salt = app.config["IP_HASH_SALT"]
    return hashlib.sha256(f"{client_ip}:{salt}".encode("utf-8")).hexdigest()


def check_user_voted(poll_id: int) -> Tuple[bool, Optional[int]]:
    """
    Check if the current visitor has already voted on this poll.
    Returns (has_voted, voted_option_id).
    """
    db = get_db()
    voter_token = getattr(g, "voter_token", "")
    enforce_ip = app.config["ENFORCE_IP_LIMIT"]
    ip_hash = compute_ip_hash() if enforce_ip else None

    if enforce_ip and ip_hash:
        row = db.execute(
            """
            SELECT option_id FROM votes
            WHERE poll_id = ? AND (voter_token = ? OR ip_hash = ?)
            LIMIT 1
            """,
            (poll_id, voter_token, ip_hash),
        ).fetchone()
    else:
        row = db.execute(
            """
            SELECT option_id FROM votes
            WHERE poll_id = ? AND voter_token = ?
            LIMIT 1
            """,
            (poll_id, voter_token),
        ).fetchone()

    if row:
        return True, row["option_id"]
    return False, None


def calculate_largest_remainder_percentages(options_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compute integer percentages using the Largest Remainder (Hare-Niemeyer) Method.
    Guarantees that:
    1. If total votes == 0, every option gets 0%.
    2. If total votes > 0, the sum of all option percentages is ALWAYS exactly 100%.
    """
    total_votes = sum(item["votes"] for item in options_list)
    if total_votes == 0:
        return [{**item, "percentage": 0} for item in options_list]

    exact_items = []
    for idx, item in enumerate(options_list):
        votes = item["votes"]
        exact_pct = (votes / total_votes) * 100.0
        floor_pct = int(exact_pct)
        remainder = exact_pct - floor_pct
        exact_items.append({
            "index": idx,
            "data": item,
            "floor": floor_pct,
            "remainder": remainder,
        })

    allocated_sum = sum(entry["floor"] for entry in exact_items)
    discrepancy = 100 - allocated_sum

    # Sort descending by remainder; stable tie-break by original index
    sorted_by_remainder = sorted(
        exact_items,
        key=lambda e: (e["remainder"], -e["index"]),
        reverse=True,
    )

    percentages = {entry["index"]: entry["floor"] for entry in exact_items}
    for i in range(discrepancy):
        target_idx = sorted_by_remainder[i]["index"]
        percentages[target_idx] += 1

    return [
        {**item, "percentage": percentages[idx]}
        for idx, item in enumerate(options_list)
    ]


# -----------------------------------------------------------------------------
# Web Page Views
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    """Home page: Displays all active polls with total votes."""
    db = get_db()
    polls = db.execute(
        """
        SELECT p.id, p.question, p.created_at, COUNT(v.id) AS total_votes
        FROM polls p
        LEFT JOIN votes v ON p.id = v.poll_id
        GROUP BY p.id
        ORDER BY p.created_at DESC, p.id DESC
        """
    ).fetchall()
    return render_template("index.html", polls=polls)


@app.route("/create")
def create_poll_page():
    """Poll creation page with dynamic option builder."""
    return render_template("create.html")


@app.route("/poll/<int:poll_id>")
def poll_page(poll_id: int):
    """Public voting and real-time results page for a single poll."""
    db = get_db()
    poll = db.execute("SELECT id, question, created_at FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        abort(404)

    options = db.execute(
        "SELECT id, text, position FROM options WHERE poll_id = ? ORDER BY position ASC, id ASC",
        (poll_id,),
    ).fetchall()

    has_voted, voted_option_id = check_user_voted(poll_id)

    return render_template(
        "poll.html",
        poll=poll,
        options=options,
        has_voted=has_voted,
        voted_option_id=voted_option_id,
    )


# -----------------------------------------------------------------------------
# REST API Endpoints (/api)
# -----------------------------------------------------------------------------

@app.route("/api/polls", methods=["GET"])
def api_get_polls():
    """GET /api/polls -> list of polls with total votes."""
    db = get_db()
    rows = db.execute(
        """
        SELECT p.id, p.question, p.created_at, COUNT(v.id) AS total_votes
        FROM polls p
        LEFT JOIN votes v ON p.id = v.poll_id
        GROUP BY p.id
        ORDER BY p.created_at DESC, p.id DESC
        """
    ).fetchall()

    polls = [
        {
            "id": r["id"],
            "question": r["question"],
            "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            "total_votes": r["total_votes"],
        }
        for r in rows
    ]
    return jsonify(polls), 200


@app.route("/api/polls", methods=["POST"])
def api_create_poll():
    """
    POST /api/polls
    Body: { "question": str, "options": [str, ...] }
    Validation:
      - question: non-empty, max 200 chars
      - options: 2 to 6 non-empty items, max 100 chars each, unique
    Returns: 201 with created poll id
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid request body. Expected JSON object."}), 400

    raw_question = data.get("question")
    if not isinstance(raw_question, str):
        return jsonify({"error": "Question is required and must be a string."}), 400

    question = raw_question.strip()
    if not question:
        return jsonify({"error": "Poll question cannot be empty."}), 400
    if len(question) > 200:
        return jsonify({"error": "Question exceeds the maximum length of 200 characters."}), 400

    raw_options = data.get("options")
    if not isinstance(raw_options, list):
        return jsonify({"error": "Options must be an array of strings."}), 400

    if len(raw_options) < 2 or len(raw_options) > 6:
        return jsonify({"error": "A poll must have between 2 and 6 options."}), 400

    cleaned_options = []
    seen_normalized = set()
    for opt in raw_options:
        if not isinstance(opt, str):
            return jsonify({"error": "All options must be non-empty strings."}), 400
        cleaned = opt.strip()
        if not cleaned:
            return jsonify({"error": "Option text cannot be blank."}), 400
        if len(cleaned) > 100:
            return jsonify({"error": f"Option '{cleaned[:20]}...' exceeds 100 characters limit."}), 400

        normalized = cleaned.lower()
        if normalized in seen_normalized:
            return jsonify({"error": f"Duplicate option detected: '{cleaned}'. All options must be unique."}), 400
        seen_normalized.add(normalized)
        cleaned_options.append(cleaned)

    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO polls (question) VALUES (?)", (question,))
    poll_id = cursor.lastrowid

    for pos, opt_text in enumerate(cleaned_options):
        cursor.execute(
            "INSERT INTO options (poll_id, text, position) VALUES (?, ?, ?)",
            (poll_id, opt_text, pos),
        )

    db.commit()

    return jsonify({
        "id": poll_id,
        "question": question,
        "message": "Poll created successfully.",
    }), 201


@app.route("/api/polls/<int:poll_id>", methods=["GET"])
def api_get_poll(poll_id: int):
    """GET /api/polls/<id> -> poll details with options."""
    db = get_db()
    poll = db.execute("SELECT id, question, created_at FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        return jsonify({"error": "Poll not found."}), 404

    options_rows = db.execute(
        "SELECT id, text, position FROM options WHERE poll_id = ? ORDER BY position ASC, id ASC",
        (poll_id,),
    ).fetchall()

    has_voted, voted_option_id = check_user_voted(poll_id)

    created_str = (
        poll["created_at"].isoformat()
        if hasattr(poll["created_at"], "isoformat")
        else str(poll["created_at"])
    )

    return jsonify({
        "id": poll["id"],
        "question": poll["question"],
        "created_at": created_str,
        "has_voted": has_voted,
        "voted_option_id": voted_option_id,
        "options": [
            {
                "id": opt["id"],
                "text": opt["text"],
                "position": opt["position"],
            }
            for opt in options_rows
        ],
    }), 200


@app.route("/api/polls/<int:poll_id>/vote", methods=["POST"])
def api_vote(poll_id: int):
    """
    POST /api/polls/<id>/vote
    Body: { "option_id": int }
    Validation:
      - poll must exist (404)
      - option_id must belong to poll (400)
      - duplicate vote check via token + IP hash (409)
    Returns: 200 on success
    """
    db = get_db()
    poll = db.execute("SELECT id FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        return jsonify({"error": "Poll not found."}), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body. Expected { 'option_id': <int> }."}), 400

    option_id = data.get("option_id")
    if option_id is None or not isinstance(option_id, int):
        return jsonify({"error": "Valid integer 'option_id' is required."}), 400

    # Ensure option belongs to this poll
    opt = db.execute(
        "SELECT id FROM options WHERE id = ? AND poll_id = ?",
        (option_id, poll_id),
    ).fetchone()
    if not opt:
        return jsonify({"error": "The specified option does not belong to this poll."}), 400

    # Check for duplicate vote
    has_voted, _ = check_user_voted(poll_id)
    if has_voted:
        return jsonify({
            "error": "You have already voted on this poll.",
            "code": "DUPLICATE_VOTE",
        }), 409

    voter_token = getattr(g, "voter_token", "")
    enforce_ip = app.config["ENFORCE_IP_LIMIT"]
    ip_hash = compute_ip_hash() if enforce_ip else None

    try:
        db.execute(
            """
            INSERT INTO votes (poll_id, option_id, voter_token, ip_hash)
            VALUES (?, ?, ?, ?)
            """,
            (poll_id, option_id, voter_token, ip_hash),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({
            "error": "You have already voted on this poll.",
            "code": "DUPLICATE_VOTE",
        }), 409

    return jsonify({
        "message": "Vote recorded successfully.",
        "poll_id": poll_id,
        "option_id": option_id,
    }), 200


@app.route("/api/polls/<int:poll_id>/results", methods=["GET"])
def api_get_results(poll_id: int):
    """
    GET /api/polls/<id>/results
    Returns: per-option votes, percentages calculated with largest remainder method,
    total votes, and has_voted / voted_option_id for current visitor.
    """
    db = get_db()
    poll = db.execute("SELECT id, question FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if not poll:
        return jsonify({"error": "Poll not found."}), 404

    options_rows = db.execute(
        """
        SELECT o.id, o.text, o.position, COUNT(v.id) AS votes
        FROM options o
        LEFT JOIN votes v ON o.id = v.option_id
        WHERE o.poll_id = ?
        GROUP BY o.id
        ORDER BY o.position ASC, o.id ASC
        """,
        (poll_id,),
    ).fetchall()

    raw_options = [
        {
            "id": r["id"],
            "text": r["text"],
            "position": r["position"],
            "votes": r["votes"],
        }
        for r in options_rows
    ]

    total_votes = sum(item["votes"] for item in raw_options)
    processed_results = calculate_largest_remainder_percentages(raw_options)

    has_voted, voted_option_id = check_user_voted(poll_id)

    return jsonify({
        "poll_id": poll["id"],
        "question": poll["question"],
        "total_votes": total_votes,
        "has_voted": has_voted,
        "voted_option_id": voted_option_id,
        "results": processed_results,
    }), 200


@app.errorhandler(404)
def not_found_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource not found."}), 404
    return render_template("index.html", error_message="The requested page was not found."), 404


@app.errorhandler(500)
def server_error_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error."}), 500
    return render_template("index.html", error_message="An unexpected error occurred."), 500


if __name__ == "__main__":
    # Ensure database tables exist before starting
    init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
