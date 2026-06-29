"""
migrate_to_turso.py  —  one-time: copy your LOCAL data up to Turso (cloud).

Run this ONCE after you've put your Turso credentials in .env. It reads your
local networking.db (and settings.json) and writes everything into your Turso
database, so your existing contacts and settings show up in the cloud app.

    python migrate_to_turso.py

It's safe to stop and re-run: if Turso already has contacts, it won't duplicate
them (it just tells you and stops). Use --force to copy anyway.
"""

import json
import os
import sqlite3
import sys

import config
import database


def _local_rows(table):
    """Read every row from the LOCAL sqlite file as a list of dicts."""
    if not os.path.exists(config.DB_PATH):
        return []
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []  # table doesn't exist locally yet
    finally:
        con.close()


def _insert_rows(table, rows):
    """Insert dict rows (preserving ids) into the active DB (Turso)."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    n = 0
    with database._conn() as con:
        for r in rows:
            con.execute(sql, [r.get(c) for c in cols])
            n += 1
    return n


def main(force=False):
    if not config.USE_TURSO:
        print("Turso is not configured. Put TURSO_DATABASE_URL and "
              "TURSO_AUTH_TOKEN in your .env first, then re-run.")
        return 1

    database.init_db()  # creates the tables in Turso

    existing = database.get_experts(include_archived=True)
    if existing and not force:
        print(f"Turso already has {len(existing)} contact(s). Nothing copied. "
              f"Re-run with --force to copy your local data anyway.")
        return 0

    experts = _local_rows("experts")
    sent = _local_rows("sent_emails")
    n_exp = _insert_rows("experts", experts)
    n_sent = _insert_rows("sent_emails", sent)

    # Settings: copy settings.json into the cloud settings table.
    n_set = 0
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                database.set_setting(key, value)
                n_set += 1
        except (json.JSONDecodeError, OSError) as e:
            print(f"  (couldn't read settings.json: {e})")

    print(f"Done. Copied {n_exp} contact(s), {n_sent} sent-email log row(s), "
          f"and {n_set} setting(s) to Turso.")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
