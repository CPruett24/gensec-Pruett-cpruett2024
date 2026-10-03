"""Deterministic local file fingerprints using only Python's standard library."""

import hashlib
import os
import stat
from pathlib import Path

from langchain_core.tools import tool


def analyze_file(file_path: str) -> dict:
    """Validate a regular file and stream its bytes into three hash algorithms.

    Relative paths use the process working directory; home-directory shorthand
    is supported. Expected path/read failures return structured errors.
    """
    if not file_path.strip():
        return {"status": "error", "error": "File path must not be blank."}
    try:
        path = Path(file_path).expanduser().resolve()
        if not stat.S_ISREG(path.stat().st_mode):
            return {"status": "error", "error": "Path is not a regular file.", "path": str(path)}
        hashes = {
            "sha256": hashlib.sha256(),
            "sha1": hashlib.sha1(usedforsecurity=False),
            "md5": hashlib.md5(usedforsecurity=False),
        }
        size = 0
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return {"status": "error", "error": "Path is not a regular file.", "path": str(path)}
            while chunk := handle.read(1024 * 1024):
                size += len(chunk)
                for digest in hashes.values():
                    digest.update(chunk)
        return {
            "status": "ok",
            "file_name": path.name,
            "path": str(path),
            "size_bytes": size,
            "hashes": {name: digest.hexdigest() for name, digest in hashes.items()},
        }
    except FileNotFoundError:
        return {"status": "error", "error": "File does not exist.", "input_path": file_path}
    except PermissionError:
        return {"status": "error", "error": "Permission denied while accessing the file.", "input_path": file_path}
    except (OSError, ValueError, RuntimeError) as exc:
        return {"status": "error", "error": f"Unable to analyze file: {exc}", "input_path": file_path}


@tool
def file_security_analysis(file_path: str) -> dict:
    """Calculate SHA-256, SHA-1, and MD5 hashes and basic metadata for a local file.

    Use for file fingerprints, integrity checks, file name, and byte size instead
    of Terminal or security_knowledge. Supply a file path, not a shell command;
    relative paths use the CLI's working directory. Reads a regular file without
    executing or modifying it. Returns hashes, resolved path, name, and size,
    or a clear error for invalid or unreadable paths. Does not classify malware.
    """
    return analyze_file(file_path)
