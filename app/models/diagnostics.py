"""Diagnostics: the transform explains itself instead of failing or guessing silently.

Structural problems (malformed codes, bad checksums, missing fields) are
Pydantic validation errors and become HTTP 422 — they never get this far.
Diagnostics are *business* signals riding on a 200: the claim was built, and
a human needs to see what was decided along the way.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    ERROR = "error"      # a payer would deny this, but we built it anyway
    WARNING = "warning"  # probably fine, flagged for review
    INFO = "info"        # we defaulted something


class Diagnostic(BaseModel):
    severity: Severity
    code: str = Field(description='machine-readable, e.g. "SERVICE_LINES_SPLIT"')
    message: str
    path: str | None = Field(
        default=None,
        description='where in the output, e.g. "claim.items[6]" (0-based array indexes)',
    )
