"""Slow down password guessing: a few wrong passwords pause sign-in for that username.

Keyed by username, not by address: phones reach the API through the web proxy, so every
request arrives from the same IP. Held in memory (the app runs as one API process).
"""

import time
from collections import deque

MAX_FAILURES = 10
WINDOW_SEC = 60.0
# all names together: stops guessing across thousands of made-up usernames
MAX_ALL_PER_WINDOW = 120
_MAX_TRACKED = 1000

_failures: dict[str, deque[float]] = {}
_all: deque[float] = deque()


def retry_after(username: str) -> int:
    """Seconds this username must wait, or 0. Counts this call as an attempt when allowed.

    The attempt is counted before the password is checked, so a burst of parallel requests
    cannot all slip through. A correct password clears the count.
    """
    now = time.monotonic()
    key = username.casefold()
    while _all and now - _all[0] > WINDOW_SEC:
        _all.popleft()
    if key not in _failures and len(_failures) >= _MAX_TRACKED:
        _forget_quiet_names(now)
    queue = _failures.setdefault(key, deque())
    while queue and now - queue[0] > WINDOW_SEC:
        queue.popleft()
    if len(queue) >= MAX_FAILURES:
        return int(WINDOW_SEC - (now - queue[0])) + 1
    if len(_all) >= MAX_ALL_PER_WINDOW:
        return int(WINDOW_SEC - (now - _all[0])) + 1
    queue.append(now)
    _all.append(now)
    return 0


def _forget_quiet_names(now: float) -> None:
    """Drop expired entries, then the least active one that is not paused."""
    for key in [k for k, q in _failures.items() if not q or now - q[-1] > WINDOW_SEC]:
        del _failures[key]
    if len(_failures) >= _MAX_TRACKED:
        waiting = [k for k, q in _failures.items() if len(q) < MAX_FAILURES]
        del _failures[min(waiting or _failures, key=lambda k: len(_failures[k]))]


def clear(username: str) -> None:
    queue = _failures.pop(username.casefold(), None)
    if queue:  # a correct password does not count against everyone else
        for stamp in queue:
            if stamp in _all:
                _all.remove(stamp)


def reset() -> None:
    """For tests."""
    _failures.clear()
    _all.clear()
