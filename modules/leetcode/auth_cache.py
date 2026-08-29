"""Tiny on-disk cache remembering the last time LEETCODE_SESSION/CSRF_TOKEN
were confirmed valid against LeetCode, so LeetCodeClient.ensure_authenticated
doesn't need a network round trip on every fresh CLI invocation (a new
process each time — an in-memory-only cache on the client instance wouldn't
survive between separate commands).

Stores only a one-way hash of the credentials plus a timestamp — never the
raw SESSION/CSRF_TOKEN values themselves. A single JSON file rather than a
SQLite table since this is one scalar record, not queryable data.
"""

import json

import structlog

from .settings import leetcode_settings

logger = structlog.get_logger(__name__)


def load_auth_cache() -> dict | None:
    """Returns {"credential_hash", "verified_at"} from disk, or None if
    there's no cache yet or it's unreadable/corrupt (treated the same as
    "no cache" — the caller just re-checks with LeetCode)."""
    path = leetcode_settings.AUTH_CACHE_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError, OSError:
        logger.warning("auth_cache_read_failed", path=str(path))
        return None


def save_auth_cache(credential_hash: str, verified_at: float) -> None:
    """Persists a successful authentication check. Atomic write (tmp file,
    then replace) so a crash mid-write can't corrupt the cache."""
    path = leetcode_settings.AUTH_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps({"credential_hash": credential_hash, "verified_at": verified_at})
    )
    tmp_path.replace(path)
    logger.info("auth_cache_saved", path=str(path))


def clear_auth_cache() -> None:
    """Invalidates any cached 'this session works' record — called whenever
    a live check finds the session is actually no longer valid, so a
    still-unexpired-TTL cache entry from before it went stale doesn't keep
    fooling a later, separate CLI invocation into skipping its own check."""
    path = leetcode_settings.AUTH_CACHE_PATH
    if path.exists():
        path.unlink()
        logger.info("auth_cache_cleared", path=str(path))
