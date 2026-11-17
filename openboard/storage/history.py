"""
openboard.storage.history
~~~~~~~~~~~~~~~~~~~~~~~~~
Match history backed by an SQLite database.
No pygame, no engine imports.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("openboard.storage.history")

_SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    opponent TEXT NOT NULL,
    engine_level INTEGER,
    time_control TEXT NOT NULL,
    player_color TEXT NOT NULL,
    result TEXT NOT NULL,
    reason TEXT NOT NULL,
    moves INTEGER NOT NULL,
    pgn TEXT NOT NULL,
    backends TEXT
);
"""


@dataclass(slots=True)
class MatchRecord:
    """A single completed game record."""

    id: int
    started_at: str
    mode: str
    opponent: str
    engine_level: int | None
    time_control: str
    player_color: str
    result: str
    reason: str
    moves: int
    pgn: str
    backends: str | None


@dataclass(slots=True)
class Stats:
    """Aggregate statistics across all stored matches."""

    played: int
    won: int
    lost: int
    drawn: int
    by_mode: dict[str, int]


class HistoryStore:
    """Thread-safe SQLite-backed match history store."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, record: dict) -> int:
        """Insert a match record and return its auto-assigned id."""
        sql = """
        INSERT INTO matches
            (started_at, mode, opponent, engine_level, time_control,
             player_color, result, reason, moves, pgn, backends)
        VALUES
            (:started_at, :mode, :opponent, :engine_level, :time_control,
             :player_color, :result, :reason, :moves, :pgn, :backends)
        """
        with self._lock:
            cur = self._conn.execute(sql, record)
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def stats(self) -> Stats:
        """Return aggregate statistics for all stored matches."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS played,"
                "       SUM(result='won') AS won,"
                "       SUM(result='lost') AS lost,"
                "       SUM(result='drawn') AS drawn"
                " FROM matches"
            ).fetchone()

            mode_rows = self._conn.execute(
                "SELECT mode, COUNT(*) AS cnt FROM matches GROUP BY mode"
            ).fetchall()

        played = row["played"] or 0
        won = row["won"] or 0
        lost = row["lost"] or 0
        drawn = row["drawn"] or 0
        by_mode = {r["mode"]: r["cnt"] for r in mode_rows}
        return Stats(played=played, won=won, lost=lost, drawn=drawn, by_mode=by_mode)

    def recent(self, limit: int = 50, offset: int = 0) -> list[MatchRecord]:
        """Return the most recent matches, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM matches ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, id: int) -> MatchRecord | None:
        """Fetch a single match by id, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM matches WHERE id = ?", (id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def clear(self) -> None:
        """Delete all match records."""
        with self._lock:
            self._conn.execute("DELETE FROM matches")
            self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(_DDL)
            version_row = self._conn.execute(
                "SELECT version FROM schema_version"
            ).fetchone()
            if version_row is None:
                self._conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (_SCHEMA_VERSION,),
                )
                self._conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MatchRecord:
        return MatchRecord(
            id=row["id"],
            started_at=row["started_at"],
            mode=row["mode"],
            opponent=row["opponent"],
            engine_level=row["engine_level"],
            time_control=row["time_control"],
            player_color=row["player_color"],
            result=row["result"],
            reason=row["reason"],
            moves=row["moves"],
            pgn=row["pgn"],
            backends=row["backends"],
        )
