import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent / "places.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_rating REAL NOT NULL,
                provider TEXT NOT NULL DEFAULT 'google',
                provider_place_id TEXT,
                address TEXT,
                latitude REAL,
                longitude REAL,
                provider_rating REAL,
                category TEXT,
                photo_refs TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS place_search_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                result_count INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def add_place(place: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO places (
                name, user_rating, provider, provider_place_id, address,
                latitude, longitude, provider_rating, category, photo_refs
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                place["name"],
                float(place["user_rating"]),
                place.get("provider", "google"),
                place.get("provider_place_id"),
                place.get("address"),
                place.get("latitude"),
                place.get("longitude"),
                place.get("provider_rating"),
                place.get("category"),
                place.get("photo_refs", "[]"),
            ),
        )
        return int(cur.lastrowid)


def list_places() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, user_rating, provider, provider_place_id, address,
                   latitude, longitude, provider_rating, category, photo_refs, created_at
            FROM places
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_place(place_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    return dict(row) if row else None


def log_search(query: str, result_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO place_search_logs (query, result_count) VALUES (?, ?)",
            (query, result_count),
        )
