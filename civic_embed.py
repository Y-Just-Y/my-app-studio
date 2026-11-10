#!/usr/bin/env python3
"""Explicit, bounded embedding import; this command can incur OpenAI API usage."""

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

from app import civic_ai, civic_vectors

ROOT = Path(__file__).resolve().parent


def main(arguments=None):
    """Require a private configured key and explicit consent before API usage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "runtime" / "civic.sqlite3"
    )
    parser.add_argument(
        "--confirm-api-usage",
        action="store_true",
        help="Allow paid embedding requests for at most 100 imported public chunks.",
    )
    args = parser.parse_args(arguments)
    if not args.confirm_api_usage:
        parser.error(
            "No API call was made. Review your OpenAI billing/limits, then add "
            "--confirm-api-usage to permit embedding requests."
        )
    if arguments is None:
        load_dotenv(ROOT / ".env", override=False)
    configuration = civic_ai.configuration_status()
    if not configuration["configured"]:
        parser.error("Configure OPENAI_API_KEY privately on this computer first.")
    try:
        result = civic_vectors.index_chunks(
            args.database,
            civic_ai.embed_texts,
            configuration["embedding_model"],
        )
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
