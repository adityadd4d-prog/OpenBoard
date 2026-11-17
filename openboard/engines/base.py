"""
openboard.engines.base
~~~~~~~~~~~~~~~~~~~~~~~
Abstract base class for chess engine backends.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from openboard.engines.types import Backend, SearchRequest, SearchResult


class EngineError(Exception):
    """Raised by a backend when it cannot complete a search.

    Args:
        message: Human-readable description of the error.
        recoverable: True if the caller may retry on the other backend.
    """

    def __init__(self, message: str, recoverable: bool = False) -> None:
        super().__init__(message)
        self.recoverable = recoverable


class EngineBackend(ABC):
    """Abstract base for chess engine backends.

    All implementations must be thread-safe: ``search`` may be called from a
    dedicated worker thread while ``stop``/``new_game`` are called from the
    main thread.
    """

    name: Backend
    available: bool

    @abstractmethod
    def start(self) -> None:
        """Initialise the backend.  Called once before any searches."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Release all resources.  Idempotent."""
        ...

    @abstractmethod
    def new_game(self) -> None:
        """Reset internal state for a new game (clears hash tables etc.)."""
        ...

    @abstractmethod
    def search(self, request: SearchRequest, cancel: threading.Event) -> SearchResult:
        """Blocking search.

        Contract:
        - Returns within ``request.time_s + 1`` seconds (best effort).
        - Checks ``cancel`` frequently; stops and returns current best when set.
        - Never raises for a legal position (returns ``SearchResult(error=...)``
          instead).
        - Fills the ``backend`` and ``reason`` fields of the returned result.
        """
        ...

    @abstractmethod
    def configure(self, **options: object) -> None:
        """Apply backend-specific key/value options."""
        ...
