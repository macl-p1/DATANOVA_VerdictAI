"""Retention window for case records.

The upload bucket already expires objects after 7 days, but the facts derived
from them — the accused's name, the sections charged, the arrest date — were
written to DynamoDB with no expiry at all, so the most sensitive form of the
data outlived the document it came from. Every case row now carries `expiresAt`
and the table has TTL enabled on that attribute.

DynamoDB deletes expired items within roughly 48 hours of the timestamp, not at
the instant it passes, so this is a retention policy rather than a guarantee.
"""
import os
import time

DEFAULT_RETENTION_DAYS = 90


def retention_days() -> int:
    try:
        days = int(os.environ.get("CASE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return days if days > 0 else DEFAULT_RETENTION_DAYS


def expires_at(now: float | None = None) -> int:
    """Epoch seconds at which this case record becomes eligible for deletion."""
    return int((now if now is not None else time.time()) + retention_days() * 86400)
