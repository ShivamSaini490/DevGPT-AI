from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return naive UTC to match the existing timestamp-without-time-zone schema."""

    return datetime.now(UTC).replace(tzinfo=None)

