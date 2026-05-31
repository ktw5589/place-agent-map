import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()

DB_PATH = Path(__file__).parent / "places.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)


def get_conn():
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _dict(row):
    return dict(row) if row else None


def _execute(conn, query: str, params=()):
    if USE_POSTGRES:
        query = query.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(query, params)
        return cur
    return conn.execute(query, params)


def init_db():
    with get_conn() as conn:
        if USE_POSTGRES:
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS places (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    user_rating DOUBLE PRECISION NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'google',
                    provider_place_id TEXT,
                    address TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    provider_rating DOUBLE PRECISION,
                    category TEXT,
                    photo_refs TEXT DEFAULT '[]',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS place_search_logs (
                    id SERIAL PRIMARY KEY,
                    query TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """,
            )
        else:
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
        conn.commit()


def add_place(place: dict) -> int:
    with get_conn() as conn:
        query = """
            INSERT INTO places (
                name, user_rating, provider, provider_place_id, address,
                latitude, longitude, provider_rating, category, photo_refs
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        if USE_POSTGRES:
            query += " RETURNING id"
        cur = _execute(
            conn,
            query,
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
        if USE_POSTGRES:
            row = cur.fetchone()
            conn.commit()
            return int(row["id"])
        conn.commit()
        return int(cur.lastrowid)


def list_places() -> list[dict]:
    with get_conn() as conn:
        rows = _execute(
            conn,
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
        row = _execute(conn, "SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    return _dict(row)


def log_search(query: str, result_count: int) -> None:
    with get_conn() as conn:
        _execute(
            conn,
            "INSERT INTO place_search_logs (query, result_count) VALUES (?, ?)",
            (query, result_count),
        )
        conn.commit()
