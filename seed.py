#!/usr/bin/env python3
"""
Seed script for Real-Time Polling & Survey Platform.
Creates tables if needed and inserts 3 realistic sample polls with votes.
Safe to run multiple times (idempotent).
"""

import os
import uuid
import hashlib
import sqlite3
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from db import init_db, get_db_path

SAMPLE_POLLS = [
    {
        "question": "What is your primary programming language for web development?",
        "options": ["Python", "JavaScript", "TypeScript", "Go", "Rust"],
        "votes": {
            "Python": 15,
            "JavaScript": 12,
            "TypeScript": 14,
            "Go": 6,
            "Rust": 5,
        },
    },
    {
        "question": "Which remote work model do you prefer?",
        "options": ["Fully Remote", "Hybrid (2-3 days office)", "In-Office Full Time"],
        "votes": {
            "Fully Remote": 24,
            "Hybrid (2-3 days office)": 15,
            "In-Office Full Time": 3,
        },
    },
    {
        "question": "What database do you use most frequently in production?",
        "options": ["PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis"],
        "votes": {
            "PostgreSQL": 19,
            "MySQL": 11,
            "SQLite": 9,
            "MongoDB": 5,
            "Redis": 4,
        },
    },
]


def generate_fake_ip(index: int) -> str:
    """Generate deterministic fake client IP address for testing."""
    return f"192.168.{(index // 250) + 1}.{(index % 250) + 1}"


def seed() -> None:
    db_path = get_db_path()
    print(f"Ensuring database schema exists at: {db_path}")
    init_db(db_path)

    salt = os.getenv("IP_HASH_SALT", "default-seed-salt-2026")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        total_polls_seeded = 0
        total_votes_seeded = 0

        for poll_data in SAMPLE_POLLS:
            question = poll_data["question"]
            cursor.execute("SELECT id FROM polls WHERE question = ?", (question,))
            row = cursor.fetchone()

            if row:
                poll_id = row[0]
                print(f"Poll already exists (ID: {poll_id}): '{question}' - checking votes...")
            else:
                cursor.execute(
                    "INSERT INTO polls (question) VALUES (?)",
                    (question,),
                )
                poll_id = cursor.lastrowid
                print(f"Created poll (ID: {poll_id}): '{question}'")
                total_polls_seeded += 1

                for pos, opt_text in enumerate(poll_data["options"]):
                    cursor.execute(
                        "INSERT INTO options (poll_id, text, position) VALUES (?, ?, ?)",
                        (poll_id, opt_text, pos),
                    )

            # Check if votes already exist for this poll
            cursor.execute("SELECT COUNT(*) FROM votes WHERE poll_id = ?", (poll_id,))
            existing_votes_count = cursor.fetchone()[0]

            if existing_votes_count == 0:
                # Map option text to option id
                cursor.execute("SELECT id, text FROM options WHERE poll_id = ?", (poll_id,))
                opt_map = {r[1]: r[0] for r in cursor.fetchall()}

                voter_idx = 0
                for opt_text, count in poll_data["votes"].items():
                    opt_id = opt_map.get(opt_text)
                    if not opt_id:
                        continue
                    for _ in range(count):
                        voter_idx += 1
                        fake_token = f"seed-voter-{poll_id}-{voter_idx}-{uuid.uuid4().hex[:8]}"
                        fake_ip = generate_fake_ip(voter_idx + (poll_id * 500))
                        ip_hash = hashlib.sha256(f"{fake_ip}:{salt}".encode("utf-8")).hexdigest()

                        cursor.execute(
                            """
                            INSERT INTO votes (poll_id, option_id, voter_token, ip_hash)
                            VALUES (?, ?, ?, ?)
                            """,
                            (poll_id, opt_id, fake_token, ip_hash),
                        )
                        total_votes_seeded += 1
                print(f"  Inserted {voter_idx} simulated votes for poll {poll_id}.")
            else:
                print(f"  Poll {poll_id} already has {existing_votes_count} votes. Skipping vote seeding.")

        conn.commit()
        print(f"Seed complete. Polls added: {total_polls_seeded}, Votes added: {total_votes_seeded}.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
