#!/usr/bin/env python3
"""Store a locally entered API key privately, without a network request."""

from getpass import getpass
import os
from pathlib import Path
import tempfile

from dotenv import dotenv_values


def main():
    """The human enters this credential in their own terminal, never in chat."""
    root = Path(__file__).resolve().parent
    destination = root / ".env"
    if destination.is_symlink():
        raise ValueError("The private .env must be an ordinary file.")
    print("Paste the OpenAI project key at the hidden prompt. It will not be printed.")
    key = getpass("OpenAI API key (hidden): ").strip()
    if not key.startswith("sk-") or any(c.isspace() for c in key) or len(key) > 1024:
        raise ValueError("That does not look like an OpenAI project API key.")
    values = dict(dotenv_values(destination)) if destination.exists() else {}
    values.update(
        OPENAI_API_KEY=key,
        OPENAI_CHAT_MODEL="gpt-5-mini",
        OPENAI_EMBEDDING_MODEL="text-embedding-3-small",
        CIVIC_AI_ENABLED="1",
    )
    descriptor, temporary = tempfile.mkstemp(prefix=".civic-env-", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for name, value in values.items():
                if value is not None:
                    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
                    stream.write(f"{name}='{escaped}'\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Private configuration saved. No API request was made.")
    print("Restart the local app, then explicitly build embeddings when ready.")


if __name__ == "__main__":
    main()
