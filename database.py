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
                    rating_count INTEGER NOT NULL DEFAULT 1,
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
                    rating_count INTEGER NOT NULL DEFAULT 1,
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
        _ensure_rating_count_column(conn)
        _dedupe_places(conn)
        conn.commit()


def _column_exists(conn, table: str, column: str) -> bool:
    if USE_POSTGRES:
        row = _execute(
            conn,
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            """,
            (table, column),
        ).fetchone()
        return bool(row)
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _ensure_rating_count_column(conn) -> None:
    if _column_exists(conn, "places", "rating_count"):
        return
    _execute(conn, "ALTER TABLE places ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 1")


def _place_key(place: dict) -> str:
    provider_id = (place.get("provider_place_id") or "").strip()
    if provider_id:
        return f"provider:{provider_id}"
    name = " ".join((place.get("name") or "").lower().split())
    address = " ".join((place.get("address") or "").lower().split())
    return f"fallback:{name}|{address}"


def _dedupe_places(conn) -> None:
    rows = _execute(
        conn,
        """
        SELECT id, name, user_rating, provider, provider_place_id, address,
               latitude, longitude, provider_rating, category, photo_refs,
               rating_count, created_at
        FROM places
        ORDER BY id ASC
        """,
    ).fetchall()
    groups: dict[str, list[dict]] = {}
    for row in rows:
        place = dict(row)
        groups.setdefault(_place_key(place), []).append(place)

    for places in groups.values():
        if len(places) < 2:
            continue
        keep = places[0]
        total_count = sum(int(place.get("rating_count") or 1) for place in places)
        weighted_sum = sum(
            float(place["user_rating"]) * int(place.get("rating_count") or 1)
            for place in places
        )
        avg_rating = round(weighted_sum / total_count, 2)
        _execute(
            conn,
            """
            UPDATE places
            SET user_rating = ?, rating_count = ?
            WHERE id = ?
            """,
            (avg_rating, total_count, keep["id"]),
        )
        for duplicate in places[1:]:
            _execute(conn, "DELETE FROM places WHERE id = ?", (duplicate["id"],))


def add_place(place: dict) -> int:
    with get_conn() as conn:
        existing = None
        provider_place_id = place.get("provider_place_id")
        if provider_place_id:
            existing = _execute(
                conn,
                "SELECT id, user_rating, rating_count FROM places WHERE provider_place_id = ? ORDER BY id ASC LIMIT 1",
                (provider_place_id,),
            ).fetchone()
        if not existing:
            existing = _execute(
                conn,
                """
                SELECT id, user_rating, rating_count
                FROM places
                WHERE lower(name) = lower(?) AND COALESCE(address, '') = COALESCE(?, '')
                ORDER BY id ASC
                LIMIT 1
                """,
                (place["name"], place.get("address")),
            ).fetchone()

        if existing:
            existing = dict(existing)
            old_rating = float(existing["user_rating"])
            old_count = int(existing["rating_count"] or 1)
            new_rating = float(place["user_rating"])
            new_count = old_count + 1
            avg_rating = round(((old_rating * old_count) + new_rating) / new_count, 2)
            _execute(
                conn,
                """
                UPDATE places
                SET user_rating = ?,
                    rating_count = ?,
                    provider = ?,
                    provider_place_id = COALESCE(provider_place_id, ?),
                    address = COALESCE(address, ?),
                    latitude = COALESCE(latitude, ?),
                    longitude = COALESCE(longitude, ?),
                    provider_rating = COALESCE(provider_rating, ?),
                    category = COALESCE(category, ?),
                    photo_refs = CASE WHEN photo_refs IS NULL OR photo_refs = '[]' THEN ? ELSE photo_refs END
                WHERE id = ?
                """,
                (
                    avg_rating,
                    new_count,
                    place.get("provider", "google"),
                    place.get("provider_place_id"),
                    place.get("address"),
                    place.get("latitude"),
                    place.get("longitude"),
                    place.get("provider_rating"),
                    place.get("category"),
                    place.get("photo_refs", "[]"),
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"])

        query = """
            INSERT INTO places (
                name, user_rating, provider, provider_place_id, address,
                latitude, longitude, provider_rating, category, photo_refs, rating_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1,
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
                   latitude, longitude, provider_rating, category, photo_refs, created_at,
                   rating_count
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


def delete_place(place_id: int) -> bool:
    with get_conn() as conn:
        cur = _execute(conn, "DELETE FROM places WHERE id = ?", (place_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
