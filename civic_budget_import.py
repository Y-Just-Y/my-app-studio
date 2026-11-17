#!/usr/bin/env python3
"""Import selected reviewed introduced-budget facts; never infer budget adoption."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from app import civic_documents, civic_store
from app.civic_refresh import RefreshBusy, writer_lock

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    """Run a bounded explicit import with no OCR, embeddings or model requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Verify a local copy instead of fetching the fixed URL.",
    )
    parser.add_argument(
        "--database", type=Path, default=ROOT / "runtime" / "civic.sqlite3"
    )
    arguments = parser.parse_args(argv)
    try:
        with writer_lock(arguments.database):
            documents = (
                civic_documents.documents_from_pdf(arguments.pdf)
                if arguments.pdf is not None
                else civic_documents.fetch_documents()
            )
            counts = civic_store.upsert_documents(arguments.database, documents)
    except (
        civic_documents.DocumentFetchError,
        civic_documents.DocumentReviewRequired,
        RefreshBusy,
        ValueError,
    ) as error:
        print(f"Budget import stopped: {error}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error):
        print(
            "Budget storage could not be updated. Existing records were kept.",
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": "imported",
                "budget_status": "introduced",
                "verification": "reviewed PDF SHA-256",
                "local_pdf": arguments.pdf is not None,
                "documents": len(documents),
                "load": counts,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
