#!/usr/bin/env python3
"""Import an explicit bounded snapshot of Newark council records for local testing."""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from app.civic_etl import CivicImportError, MEETING_TIMEZONE, run_import

ROOT = Path(__file__).resolve().parent


def main():
    """Refresh public evidence only when the operator explicitly runs the command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(ZoneInfo(MEETING_TIMEZONE)).date(),
    )
    parser.add_argument(
        "--database", type=Path, default=ROOT / "runtime" / "civic.sqlite3"
    )
    arguments = parser.parse_args()
    try:
        result = run_import(arguments.database, arguments.as_of, arguments.limit)
        print(json.dumps(result, indent=2))
    except (CivicImportError, ValueError) as error:
        print(f"Import stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
