"""
SQLite-backed cache with TTL for search results.
Avoids hammering scraped sites on repeated identical queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

from config.settings import get_settings
from models.property import Property

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._db_path = self._settings.SQLITE_DB_PATH
        self._ttl = self._settings.CACHE_TTL_SECONDS
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    data      TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def make_key(params: dict) -> str:
        serialized = json.dumps(params, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def get(self, key: str) -> list[Property] | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT data, expires_at FROM search_cache WHERE cache_key = ?", (key,)
            ).fetchone()

        if row is None:
            return None

        data_json, expires_at = row
        if time.time() > expires_at:
            self._delete(key)
            return None

        try:
            raw = json.loads(data_json)
            if not raw:
                self._delete(key)
                return None
            return [Property.model_validate(item) for item in raw]
        except Exception as exc:
            logger.warning("Cache deserialization error: %s", exc)
            return None

    def set(self, key: str, properties: list[Property]) -> None:
        if not properties:
            return
        expires_at = time.time() + self._ttl
        data_json = json.dumps([p.model_dump(mode="json") for p in properties])
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO search_cache (cache_key, data, expires_at) VALUES (?,?,?)",
                (key, data_json, expires_at),
            )
            conn.commit()

    def _delete(self, key: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
            conn.commit()

    def clear_all(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            deleted = conn.execute("DELETE FROM search_cache").rowcount
            conn.commit()
        return deleted
