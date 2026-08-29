import sqlite3
from pathlib import Path

import structlog

from modules.leetcode.settings import leetcode_settings

logger = structlog.get_logger(__name__)

# Schema changes made after a table's initial CREATE TABLE go here as
# numbered *.sql files (see migrations/0001_... for the pattern), applied in
# filename order and tracked in that DB's own schema_migrations table —
# never edit a SCHEMA constant below for an existing table once it's
# shipped, since that only affects a brand-new DB; an existing one only
# picks up the change via a migration.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
SUBMISSIONS_MIGRATIONS_DIR = Path(__file__).parent / "migrations_submissions"

# problems/tags/problem_tags/pending_cache: community/public data (safe to
# commit/share) plus local sync bookkeeping — always used together (joined
# for filtering, or read alongside submissions for rendering), so they share
# one file (leetcode_settings.DSA_DB_PATH). Personal submission data is
# deliberately NOT in here — see SUBMISSIONS_SCHEMA below.
SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    slug                     TEXT PRIMARY KEY,
    id                       INTEGER UNIQUE,
    title                    TEXT,
    url                      TEXT,
    difficulty               TEXT,
    category                 TEXT,
    raw_question_html        TEXT,
    has_images               INTEGER,
    imgs_local_paths         TEXT,
    content_remote_markdown  TEXT,
    content_local_html       TEXT,
    content_local_markdown   TEXT,
    content_text             TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS problem_tags (
    problem_slug TEXT NOT NULL REFERENCES problems(slug) ON DELETE CASCADE,
    tag_id       INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (problem_slug, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_problem_tags_tag_id ON problem_tags(tag_id);

CREATE TABLE IF NOT EXISTS pending_cache (
    slug        TEXT PRIMARY KEY,
    description INTEGER NOT NULL DEFAULT 0,
    images      INTEGER NOT NULL DEFAULT 0,
    submission  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# submissions: personal solution code, in its own file
# (leetcode_settings.SUBMISSIONS_DB_PATH) so leetcode.db can be committed
# without leaking anyone's solutions. slug is deliberately a plain column,
# not a FOREIGN KEY, and not even in the same database — ProblemStorage
# .delete() leaves a slug's submission data untouched by design, and the two
# tables are only ever joined at the Python level (see combined.py), never
# via SQL, so there's no cross-database query to preserve.
SUBMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    slug            TEXT PRIMARY KEY,
    lang            TEXT NOT NULL,
    code            TEXT NOT NULL,
    submission_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _run_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> None:
    """
    Applies every migrations_dir/*.sql file not yet recorded in that
    connection's schema_migrations, in filename order (numeric prefix, e.g.
    0001_add_pending_cache_metadata.sql) — so a DB created before a given
    schema change picks it up automatically the next time it connects,
    exactly once. A brand-new DB runs every migration too (a SCHEMA constant
    only ever reflects the *original* shape of each table — see the note by
    MIGRATIONS_DIR), so there's a single source of truth for the current
    schema regardless of when the DB file was first created.
    """
    applied = {
        row["version"] for row in conn.execute("SELECT version FROM schema_migrations")
    }
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        logger.info("schema_migration_applying", version=version)
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
        logger.info("schema_migration_applied", version=version)


def _open(path: Path, schema: str, migrations_dir: Path) -> sqlite3.Connection:
    """Shared connection setup: WAL mode (so a read doesn't block a
    concurrent write), foreign keys enforced, row_factory set so query
    results can be accessed by column name, the base schema applied
    idempotently, then every not-yet-applied migration. Creates the file and
    its parent directory on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(schema)
    conn.commit()
    _run_migrations(conn, migrations_dir)
    return conn


def get_connection() -> sqlite3.Connection:
    """Opens the shared leetcode.db connection (problems/tags/pending_cache — see SCHEMA)."""
    path = leetcode_settings.DSA_DB_PATH
    conn = _open(path, SCHEMA, MIGRATIONS_DIR)
    logger.info("leetcode_db_connected", path=str(path))
    return conn


def get_submissions_connection() -> sqlite3.Connection:
    """Opens the submissions.db connection (personal solution code — see SUBMISSIONS_SCHEMA)."""
    path = leetcode_settings.SUBMISSIONS_DB_PATH
    conn = _open(path, SUBMISSIONS_SCHEMA, SUBMISSIONS_MIGRATIONS_DIR)
    logger.info("submissions_db_connected", path=str(path))
    return conn
