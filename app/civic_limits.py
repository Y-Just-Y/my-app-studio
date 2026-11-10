"""Persistent request ceilings for a small public classroom chatbot."""

from contextlib import contextmanager
import math
from pathlib import Path
import sqlite3
import threading
import time

from fastapi import HTTPException

from app.private_files import private_directory, private_file

_ACTIVE = threading.BoundedSemaphore(1)


def consume(database, client, *, now=None):
    """Atomically reserve a request; restarts do not reset daily ceilings."""
    timestamp = int(time.time() if now is None else now)
    path = Path(database).with_name("civic-limits.sqlite3")
    private_directory(path.parent)
    with sqlite3.connect(path, timeout=5) as connection:
        private_file(path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS request_limits "
            "(bucket TEXT PRIMARY KEY, window INTEGER NOT NULL, count INTEGER NOT NULL)"
        )
        connection.execute("BEGIN IMMEDIATE")
        limits = [("client:" + client, 300, 5), ("application", 86400, 30)]
        for bucket, period, maximum in limits:
            window = timestamp // period
            row = connection.execute(
                "SELECT count FROM request_limits WHERE bucket=? AND window=?",
                (bucket, window),
            ).fetchone()
            if row and row[0] >= maximum:
                remaining = math.ceil((window + 1) * period - timestamp)
                raise HTTPException(
                    429,
                    "This test site has reached its request limit. Try again later.",
                    headers={"Retry-After": str(remaining)},
                )
        for bucket, period, _maximum in limits:
            connection.execute(
                "INSERT INTO request_limits VALUES (?, ?, 1) "
                "ON CONFLICT(bucket) DO UPDATE SET "
                "count=CASE WHEN window=excluded.window THEN count+1 ELSE 1 END, "
                "window=excluded.window",
                (bucket, timestamp // period),
            )
        connection.execute(
            "DELETE FROM request_limits WHERE bucket LIKE 'client:%' AND window < ?",
            (timestamp // 300 - 2,),
        )


@contextmanager
def one_request():
    """Reject overlapping model calls instead of creating an unbounded queue."""
    if not _ACTIVE.acquire(blocking=False):
        raise HTTPException(
            429,
            "Another answer is being prepared. Please try again shortly.",
            headers={"Retry-After": "10"},
        )
    try:
        yield
    finally:
        _ACTIVE.release()
