"""Make stable file hashes and safe fake IDs."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 20


def file_hash(path: Path) -> str:
    """Get the SHA-256 hash of a file.

    TDS §14.2 uses it to make reloads safe. Skip a file if its hash is the same. If a
    known path has a new hash, treat it as a new copy.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(*parts: object, prefix: str = "", length: int = 16) -> str:
    """Make the same ID from the same parts.

    This keeps made-up keys the same when the same input runs twice.
    """
    joined = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{digest}" if prefix else digest


def hash_lrn(lrn: str | None, salt: str) -> str | None:
    """Hide a fake learner number with a salted hash.

    The number is fake, but TDS §21.1 asks us to treat it like real private data.
    """
    if lrn is None or lrn == "":
        return None
    return hashlib.sha256(f"{salt}:{lrn}".encode()).hexdigest()[:20]
