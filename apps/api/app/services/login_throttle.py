"""Slow down password guessing: a few wrong passwords pause sign-in for that username.

Keyed by username, not by address: phones reach the API through the web proxy, so every
request arrives from the same IP. Held in memory (the app runs as one API process).
"""

import time
from collections import deque

MAX_FAILURES = 10
WINDOW_SEC = 60.0
_MAX_TRACKED = 1000

_failures: dict[str, deque[float]] = {}


def retry_after(username: str) -> int:
    """Seconds this username must wait, or 0. Counts this call as an attempt when allowed.

    The attempt is counted before the password is checked, so a burst of parallel requests
    cannot all slip through. A correct password clears the count.
    """
    now = time.monotonic()
    key = username.casefold()
    if key not in _failures and len(_failures) >= _MAX_TRACKED:
        del _failures[next(iter(_failures))]
    queue = _failures.setdefault(key, deque())
    while queue and now - queue[0] > WINDOW_SEC:
        queue.popleft()
    if len(queue) >= MAX_FAILURES:
        return int(WINDOW_SEC - (now - queue[0])) + 1
    queue.append(now)
    return 0


def clear(username: str) -> None:
    _failures.pop(username.casefold(), None)


def reset() -> None:
    """For tests."""
    _failures.clear()
