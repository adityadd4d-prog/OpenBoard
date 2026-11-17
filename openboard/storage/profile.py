"""
openboard.storage.profile
~~~~~~~~~~~~~~~~~~~~~~~~~
Player profile persistence (JSON).
No pygame, no engine imports.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from openboard import config

log = logging.getLogger("openboard.storage.profile")

_CTRL_RE = re.compile(r"[\x00-\x1f]")  # ord < 32


@dataclass(slots=True)
class PlayerProfile:
    """Persistent player identity."""

    id: str                              # uuid4 hex
    name: str = "Player 1"
    preferred_time_control: str = "rapid"
    created_at: str = ""                 # ISO UTC


class ProfileStore:
    """Loads and persists a single player profile."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._profile: PlayerProfile | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> PlayerProfile:
        """Load profile from disk, or create a fresh one if absent/corrupt."""
        if self._path.exists():
            try:
                data: dict = json.loads(self._path.read_text(encoding="utf-8"))
                self._profile = PlayerProfile(
                    id=data.get("id", uuid.uuid4().hex),
                    name=data.get("name", "Player 1"),
                    preferred_time_control=data.get("preferred_time_control", "rapid"),
                    created_at=data.get("created_at", ""),
                )
                return self._profile
            except (json.JSONDecodeError, OSError, TypeError) as exc:
                log.warning("Corrupt profile (%s); resetting.", exc)

        # Create a brand-new profile
        self._profile = PlayerProfile(
            id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save()
        return self._profile

    def rename(self, name: str) -> None:
        """Rename the player.

        Validation:
        - Strip outer whitespace; collapse internal runs to a single space.
        - 1..NAME_MAX characters after normalisation.
        - Reject any character with ord < 32 (control characters).
        - Emoji are allowed (length by len()).

        Raises ValueError with a human-readable message on failure.
        """
        if self._profile is None:
            self.load()

        # Collapse whitespace
        normalised = " ".join(name.split())

        if _CTRL_RE.search(normalised):
            raise ValueError("Name must not contain control characters.")

        if not normalised:
            raise ValueError("Name must not be empty.")

        if len(normalised) > config.NAME_MAX:
            raise ValueError(
                f"Name is too long (max {config.NAME_MAX} characters, got {len(normalised)})."
            )

        self._profile.name = normalised  # type: ignore[union-attr]
        self._save()

    def set_time_control(self, key: str) -> None:
        """Persist the preferred time control key."""
        if self._profile is None:
            self.load()
        self._profile.preferred_time_control = key  # type: ignore[union-attr]
        self._save()

    @property
    def profile(self) -> PlayerProfile | None:
        return self._profile

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Atomically persist the current profile."""
        assert self._profile is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self._profile), indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
