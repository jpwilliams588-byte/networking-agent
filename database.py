"""
database.py  —  the local database (SQLite).

Stores every person we find in a single file called "networking.db" that lives
next to this script. SQLite needs no setup or server — it's just a file.

You normally never call this file directly; the rest of the tool uses it.
The functions here create the table, add people (without creating duplicates),
read them back with filters, and update their status / flag / email draft.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

import config

# Columns we store for each person. Keeping this in one place makes add_expert()
# tolerant of missing fields (anything not provided is just left blank/NULL).
COLUMNS = [
    "name", "title", "company", "company_size", "region", "country",
    "industry", "vertical", "email", "email_source", "linkedin_url",
    "photo_url", "topics", "answers_questions", "summary", "draft_questions",
    "education_flag", "connection_flag", "status", "flagged", "email_draft", "draft_template",
    "source_url", "discovered_on", "outreach_channel", "message_channel",
    "meeting_location", "meeting_time", "notes",
]


@contextmanager
def _conn():
    """Open the database, hand back a connection, and always close it."""
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row  # lets us read rows like dictionaries
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    """Create the experts table if it doesn't already exist. Safe to re-run."""
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS experts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT,
                title            TEXT,
                company          TEXT,
                company_size     TEXT,
                region           TEXT,
                country          TEXT,
                industry         TEXT,
                vertical         TEXT,
                email            TEXT,
                email_source     TEXT DEFAULT 'none',
                linkedin_url     TEXT,
                photo_url        TEXT,
                topics           TEXT,
                answers_questions TEXT,
                summary          TEXT,
                draft_questions  TEXT,
                education_flag   TEXT,
                connection_flag  TEXT,
                status           TEXT DEFAULT 'Found',
                flagged          INTEGER DEFAULT 0,
                email_draft      TEXT,
                draft_template   TEXT,
                source_url       TEXT,
                discovered_on    TEXT,
                outreach_channel TEXT,
                message_channel  TEXT DEFAULT 'Email',
                meeting_location TEXT,
                meeting_time     TEXT,
                notes            TEXT,
                archived         INTEGER DEFAULT 0,
                archived_at      TEXT,
                created_at       TEXT,
                updated_at       TEXT
            )
            """
        )
        # Helps the dedupe lookups stay fast as the table grows.
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_linkedin ON experts(linkedin_url)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_name_company ON experts(name, company)"
        )
        # Migration guard: add any newer columns to databases created earlier.
        existing = {row["name"] for row in con.execute("PRAGMA table_info(experts)")}
        for col in ("photo_url", "education_flag", "connection_flag",
                    "outreach_channel", "message_channel", "meeting_location",
                    "meeting_time", "notes", "draft_template", "archived_at"):
            if col not in existing:
                con.execute(f"ALTER TABLE experts ADD COLUMN {col} TEXT")
        if "archived" not in existing:
            con.execute("ALTER TABLE experts ADD COLUMN archived INTEGER DEFAULT 0")

        # Log of emails you've sent — powers the A/B testing view.
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_emails (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                expert_id    INTEGER,
                template_name TEXT,
                subject      TEXT,
                body         TEXT,
                sent_at      TEXT,
                replied      INTEGER DEFAULT 0,
                replied_at   TEXT
            )
            """
        )


def _is_duplicate(con, person):
    """
    Return True if we already have this person. We match on LinkedIn URL first
    (most reliable), then fall back to name + company.
    """
    linkedin = (person.get("linkedin_url") or "").strip().lower()
    if linkedin:
        row = con.execute(
            "SELECT 1 FROM experts WHERE lower(linkedin_url) = ? LIMIT 1",
            (linkedin,),
        ).fetchone()
        if row:
            return True

    name = (person.get("name") or "").strip().lower()
    company = (person.get("company") or "").strip().lower()
    if name and company:
        row = con.execute(
            "SELECT 1 FROM experts WHERE lower(name) = ? AND lower(company) = ? LIMIT 1",
            (name, company),
        ).fetchone()
        if row:
            return True
    return False


def add_expert(person):
    """
    Add one person. `person` is a dict with any of the COLUMNS keys.
    Skips the insert if we already have them (returns False); returns True if
    a new row was created.
    """
    name = (person.get("name") or "").strip()
    if not name:
        return False  # nothing useful to store

    with _conn() as con:
        if _is_duplicate(con, person):
            return False

        now = datetime.now().isoformat(timespec="seconds")
        person.setdefault("status", "Found")
        person.setdefault("flagged", 0)  # never NULL, so flagged=0 filters match
        person.setdefault("discovered_on", date.today().isoformat())
        person.setdefault("message_channel", "Email")

        values = [person.get(col) for col in COLUMNS]
        placeholders = ", ".join(["?"] * (len(COLUMNS) + 2))
        con.execute(
            f"INSERT INTO experts ({', '.join(COLUMNS)}, created_at, updated_at) "
            f"VALUES ({placeholders})",
            values + [now, now],
        )
        return True


def count_added_on(day=None):
    """How many people were discovered on a given date (default: today)."""
    day = day or date.today().isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM experts WHERE discovered_on = ?", (day,)
        ).fetchone()
        return row["n"]


def get_experts(status=None, flagged=None, region=None, company_size=None,
                has_email=None, topic=None, education_like=None,
                connection_like=None, message_channel=None,
                include_archived=False, archived_only=False,
                order_by="updated_at DESC"):
    """
    Read people back with optional filters. Returns a list of dict-like rows.
    Pass None for any filter to ignore it. By default archived people are hidden;
    set archived_only=True to see just them, or include_archived=True for both.
    """
    clauses, params = [], []
    if archived_only:
        clauses.append("archived = 1")
    elif not include_archived:
        clauses.append("(archived = 0 OR archived IS NULL)")
    if status:
        clauses.append("status = ?"); params.append(status)
    if flagged is True:
        clauses.append("flagged = 1")
    elif flagged is False:
        clauses.append("(flagged = 0 OR flagged IS NULL)")
    if region:
        clauses.append("region = ?"); params.append(region)
    if company_size:
        clauses.append("company_size = ?"); params.append(company_size)
    if has_email is True:
        clauses.append("email IS NOT NULL AND email != ''")
    elif has_email is False:
        clauses.append("(email IS NULL OR email = '')")
    if topic:
        clauses.append("topics LIKE ?"); params.append(f"%{topic}%")
    if education_like:
        clauses.append("education_flag LIKE ?"); params.append(f"%{education_like}%")
    if connection_like:
        clauses.append("connection_flag LIKE ?"); params.append(f"%{connection_like}%")
    if message_channel:
        clauses.append("message_channel = ?"); params.append(message_channel)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM experts {where} ORDER BY {order_by}", params
        ).fetchall()
        return [dict(r) for r in rows]


def get_expert(expert_id):
    """Fetch a single person by id."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM experts WHERE id = ?", (expert_id,)
        ).fetchone()
        return dict(row) if row else None


def update_fields(expert_id, **fields):
    """Update arbitrary columns for one person, plus the updated_at timestamp."""
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as con:
        con.execute(
            f"UPDATE experts SET {sets} WHERE id = ?",
            list(fields.values()) + [expert_id],
        )


def update_status(expert_id, status):
    update_fields(expert_id, status=status)


def advance_status(expert_id, new_status):
    """
    Move a lead FORWARD to new_status only (never regress). Returns True if it
    actually advanced. Used by the Gmail/Calendar sync so a reply never gets
    bumped back to 'Contacted', etc.
    """
    order = {s: i for i, s in enumerate(config.STATUSES)}
    person = get_expert(expert_id)
    if not person:
        return False
    current = person.get("status") or "Found"
    if order.get(new_status, -1) > order.get(current, -1):
        update_status(expert_id, new_status)
        return True
    return False


def set_flag(expert_id, flagged=True):
    update_fields(expert_id, flagged=1 if flagged else 0)


def save_draft(expert_id, draft):
    update_fields(expert_id, email_draft=draft)


def _distribution(column):
    """Count by column value (active, non-archived) — for dashboards/steering."""
    with _conn() as con:
        rows = con.execute(
            f"SELECT {column} AS k, COUNT(*) AS n FROM experts "
            f"WHERE {column} IS NOT NULL AND {column} != '' "
            f"AND (archived = 0 OR archived IS NULL) GROUP BY {column}"
        ).fetchall()
        return {r["k"]: r["n"] for r in rows}


def region_distribution():
    return _distribution("region")


def size_distribution():
    return _distribution("company_size")


def stats():
    """Counts per pipeline status (active, non-archived), used by the dashboard."""
    with _conn() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) AS n FROM experts "
            "WHERE (archived = 0 OR archived IS NULL) GROUP BY status"
        ).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
    # Make sure every known status appears, even if zero.
    return {s: counts.get(s, 0) for s in config.STATUSES}


def archived_count():
    """How many people are currently archived."""
    with _conn() as con:
        return con.execute(
            "SELECT COUNT(*) AS n FROM experts WHERE archived = 1"
        ).fetchone()["n"]


def archive_stale(max_hours):
    """
    Archive UNTOUCHED stale leads: un-flagged, still in Found/Reviewed, and older
    than max_hours. Flagged or advanced leads are never touched. Returns the count.
    """
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=max(1, int(max_hours)))).isoformat(timespec="seconds")
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        cur = con.execute(
            "UPDATE experts SET archived = 1, archived_at = ? "
            "WHERE (archived = 0 OR archived IS NULL) "
            "AND (flagged = 0 OR flagged IS NULL) "
            "AND status IN ('Found', 'Reviewed') AND created_at < ?",
            (now, cutoff),
        )
        return cur.rowcount


# --------------------------------------------------------------------------- #
# Sent-email log + A/B testing
# --------------------------------------------------------------------------- #
def log_sent_email(expert_id, template_name, subject, body, sent_at=None):
    """Record an email you've sent, for the A/B log."""
    sent_at = sent_at or datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO sent_emails (expert_id, template_name, subject, body, "
            "sent_at, replied) VALUES (?, ?, ?, ?, ?, 0)",
            (expert_id, template_name or "", subject or "", body or "", sent_at),
        )


def mark_email_replied(expert_id):
    """Mark this lead's most recent un-replied logged email as 'got a reply'."""
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM sent_emails WHERE expert_id = ? AND replied = 0 "
            "ORDER BY sent_at DESC, id DESC LIMIT 1",
            (expert_id,),
        ).fetchone()
        if row:
            con.execute(
                "UPDATE sent_emails SET replied = 1, replied_at = ? WHERE id = ?",
                (now, row["id"]),
            )


def get_sent_emails():
    """All logged emails, newest first, joined to the lead's name."""
    with _conn() as con:
        rows = con.execute(
            "SELECT s.*, e.name AS lead_name FROM sent_emails s "
            "LEFT JOIN experts e ON e.id = s.expert_id ORDER BY s.sent_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def _ab_group(column):
    """Reply-rate aggregate grouped by a sent_emails column (template or subject)."""
    with _conn() as con:
        rows = con.execute(
            f"SELECT COALESCE(NULLIF({column}, ''), '(none)') AS k, "
            f"COUNT(*) AS sent, SUM(replied) AS replies "
            f"FROM sent_emails GROUP BY k ORDER BY "
            f"(CAST(SUM(replied) AS REAL) / COUNT(*)) DESC, sent DESC"
        ).fetchall()
    out = []
    for r in rows:
        sent = r["sent"] or 0
        replies = r["replies"] or 0
        rate = round(100 * replies / sent, 1) if sent else 0.0
        out.append({"key": r["k"], "sent": sent, "replies": replies, "reply_rate_%": rate})
    return out


def ab_stats():
    """Return (by_template, by_subject) reply-rate tables for the A/B view."""
    return _ab_group("template_name"), _ab_group("subject")


if __name__ == "__main__":
    # Running "python database.py" just creates/repairs the database file.
    init_db()
    print(f"Database ready at {config.DB_PATH}")
