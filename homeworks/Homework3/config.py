"""Shared environment configuration for the CLI and document indexer."""

import os


def required_env(name: str) -> str:
    """Return an environment variable or explain which setting is missing."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in your environment before running this command.")
    return value
