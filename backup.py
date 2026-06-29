"""
backup.py  —  save a local snapshot of your data.

Writes a timestamped SQLite file into the backups/ folder containing all your
contacts, sent-email log, and settings — read from wherever your data currently
lives (Turso cloud if configured, otherwise the local file). It's a real,
openable SQLite database, so you always have an offline copy you can keep.

    python backup.py

The daily 5 AM job also calls this automatically. Only the most recent 14
snapshots are kept; older ones are pruned.
"""

import json
import os
import sqlite3
from datetime import datetime

import database
import store

BACKUP_DIR = "backups"
KEEP = 14  # how many recent snapshots to retain


def _write_table(con, table, rows, pk="id"):
    """Create `table` from dict rows and insert them into the backup connection."""
    if not rows:
        return 0
    cols = list(rows[0].keys())

    def _coldef(c):
        if c != pk:
            return c
        return f"{c} INTEGER PRIMARY KEY" if c == "id" else f"{c} TEXT PRIMARY KEY"

    defs = ", ".join(_coldef(c) for c in cols)
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defs})")
    placeholders = ", ".join(["?"] * len(cols))
    con.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
        [tuple(r.get(c) for c in cols) for r in rows],
    )
    return len(rows)


def _prune():
    """Keep only the most recent KEEP snapshots."""
    files = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("networking-") and f.endswith(".db")
    )
    for old in files[:-KEEP]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass


def run():
    """Create one snapshot. Returns its path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    database.init_db()

    experts = database.get_experts(include_archived=True, order_by="id ASC")
    sent = database.get_sent_emails()
    settings = store._load() or {}
    settings_rows = [{"key": k, "value": __import__("json").dumps(v, ensure_ascii=False)}
                     for k, v in settings.items()]

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"networking-{ts}.db")

    con = sqlite3.connect(path)
    try:
        _write_table(con, "experts", experts)
        _write_table(con, "sent_emails", sent)
        _write_table(con, "app_settings", settings_rows, pk="key")
        con.commit()
    finally:
        con.close()

    _prune()
    print(f"Backed up {len(experts)} contact(s) and {len(sent)} sent-email row(s) "
          f"to {path}")
    return path


if __name__ == "__main__":
    run()
