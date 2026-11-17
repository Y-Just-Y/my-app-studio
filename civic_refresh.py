#!/usr/bin/env python3
"""Refresh the fixed official council/budget sources once, without model calls."""

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from app.civic_refresh import run_refresh

ROOT = Path(__file__).resolve().parent


def main(arguments=None):
    """A trusted CLI chooses only a local database/date/limit, never source URLs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "runtime" / "civic.sqlite3"
    )
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 6))
    args = parser.parse_args(arguments)
    try:
        result = run_refresh(args.database, args.as_of, limit=args.limit)
    except (OSError, ValueError, RuntimeError, sqlite3.Error):
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": (
                        "Refresh could not finish. "
                        "Inspect the saved source status before retrying."
                    ),
                }
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"ok", "busy"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
