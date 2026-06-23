"""
daily_run.py  —  the once-a-day job.

This is what the daily scheduled task runs. It:
  1. Finds new leads (up to the daily cap, respecting anything already found today).
  2. Enriches the new leads (summary, contact, 10 questions).
  3. Writes a one-line summary to daily_log.txt so you can see what happened,
     including the geography and company-size breakdown.

You can also run it by hand anytime:  python daily_run.py
"""

from datetime import datetime

import config
import database
import discover
import enrich
import store


def _log(line):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{stamp}] {line}"
    print(entry)
    with open(config.DAILY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def run():
    database.init_db()

    if not store.get_auto_enabled():
        _log("Auto-run is paused in Settings — skipping today's run.")
        return 0

    # Archive untouched leads from prior days so the queue stays fresh and the
    # same people are never surfaced twice.
    archived = database.archive_stale(store.get_archive_hours())

    already = database.count_added_on()
    _log(f"Daily run starting. Archived {archived} stale lead(s). "
         f"{already}/{config.DAILY_LEAD_CAP} leads already found today.")

    added = discover.discover(progress=lambda m: print("  " + m))
    enriched = enrich.enrich_all(progress=lambda m: print("  " + m))

    regions = database.region_distribution()
    sizes = database.size_distribution()
    _log(
        f"Added {added} new lead(s); enriched {enriched}. "
        f"Totals by region: {regions or '{}'} | by size: {sizes or '{}'}."
    )
    return added


if __name__ == "__main__":
    run()
