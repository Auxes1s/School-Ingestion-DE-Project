"""Stable hashing for file identity and synthetic pseudonymous identifiers."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 20


def file_hash(path: Path) -> str:
    """SHA-256 of a file's bytes.

    Drives ingestion idempotency (TDS §14.2): unchanged hash means the file is skipped,
    changed hash at a known path means a new version.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(*parts: object, prefix: str = "", length: int = 16) -> str:
    """Deterministic identifier from its parts.

    Used for surrogate keys that must be reproducible across runs, so that re-running the
    pipeline on identical input yields identical IDs.
    """
    joined = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{digest}" if prefix else digest


def hash_lrn(lrn: str | None, salt: str) -> str | None:
    """Pseudonymize a synthetic learner reference number.

    Synthetic throughout, but hashed anyway so the codebase demonstrates the handling a
    real deployment would require (TDS §21.1).
    """
    if lrn is None or lrn == "":
        return None
    return hashlib.sha256(f"{salt}:{lrn}".encode()).hexdigest()[:20]
