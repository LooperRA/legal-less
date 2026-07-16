"""Shared provenance helpers.

The projects treat provenance as first-class data.  Every analysis records where the
input came from, when it was processed, which parser handled it, and a content digest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

PARSER_VERSION = "0.1.0"


@dataclass(slots=True)
class Provenance:
    """Evidence needed to reproduce or challenge an imported record."""

    source_description: str
    source_url: str | None
    retrieved_at: str
    sha256: str
    parser_version: str = PARSER_VERSION
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def digest_text(text: str) -> str:
    """Return a stable SHA-256 digest for Unicode text."""

    return sha256(text.encode("utf-8")).hexdigest()


def build_provenance(
    text: str,
    *,
    source_description: str,
    source_url: str | None = None,
    retrieved_at: str | None = None,
    warnings: list[str] | None = None,
) -> Provenance:
    """Create a provenance record for imported text."""

    timestamp = retrieved_at or datetime.now(UTC).isoformat()
    return Provenance(
        source_description=source_description,
        source_url=source_url,
        retrieved_at=timestamp,
        sha256=digest_text(text),
        warnings=list(warnings or []),
    )


def read_text_input(path: str | Path) -> str:
    """Read a UTF-8 text-like input without making network requests."""

    return Path(path).read_text(encoding="utf-8")
