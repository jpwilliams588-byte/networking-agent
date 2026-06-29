"""
store.py  —  your editable settings (topics + research questions).

These two lists are the ones you change most, so they live in a small editable
file called settings.json that you manage from inside the app. This module reads
and writes that file. If the file doesn't exist yet, it falls back to the
starting defaults in config.py.

The rest of the tool always asks this module for the *current* topics and
questions, so edits you make in the app take effect on the very next run — no
restart needed.
"""

import json
import os

import config
import database

SETTINGS_PATH = "settings.json"


def _load():
    """Read all settings — from Turso when cloud storage is on, else settings.json."""
    if config.USE_TURSO:
        try:
            return database.get_all_settings()
        except Exception:
            return {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(data):
    """Persist settings — to Turso when cloud storage is on, else settings.json."""
    if config.USE_TURSO:
        for key, value in data.items():
            database.set_setting(key, value)
        return
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---- Research questions --------------------------------------------------- #
def get_research_questions():
    """Current questions as a list of {"question": str, "priority": int}."""
    qs = _load().get("research_questions")
    if not qs:
        return [dict(q) for q in config.DEFAULT_RESEARCH_QUESTIONS]
    return qs


def set_research_questions(questions):
    """Validate and save the questions list. Returns the cleaned list."""
    clean = []
    for q in questions:
        text = (q.get("question") or "").strip()
        if not text:
            continue
        try:
            priority = int(q.get("priority", 1))
        except (TypeError, ValueError):
            priority = 1
        clean.append({"question": text, "priority": max(1, priority)})
    data = _load()
    data["research_questions"] = clean
    _save(data)
    return clean


# ---- Biggest questions (top-tier, max 3) ---------------------------------- #
def get_biggest_questions():
    """The up-to-3 highest-priority questions as [{"question", "notes"}]."""
    bq = _load().get("biggest_questions")
    if not bq:
        return [dict(q) for q in config.DEFAULT_BIGGEST_QUESTIONS]
    return [{"question": (q.get("question") or "").strip(),
             "notes": (q.get("notes") or "").strip()} for q in bq]


def set_biggest_questions(questions):
    """Validate + save the biggest questions (drops empties, hard-caps at 3)."""
    clean = []
    for q in questions:
        text = (q.get("question") or "").strip()
        if not text:
            continue
        clean.append({"question": text, "notes": (q.get("notes") or "").strip()})
        if len(clean) >= config.MAX_BIGGEST_QUESTIONS:
            break
    data = _load()
    data["biggest_questions"] = clean
    _save(data)
    return clean


# ---- Topics --------------------------------------------------------------- #
def get_topics():
    """Current topics as a list of strings."""
    topics = _load().get("topics")
    if not topics:
        return list(config.DEFAULT_TOPICS)
    return topics


def set_topics(topics):
    """Validate and save the topics list. Returns the cleaned list."""
    clean = [t.strip() for t in topics if t and t.strip()]
    data = _load()
    data["topics"] = clean
    _save(data)
    return clean


# ---- Connections (warm-intro "bridge" list) ------------------------------- #
def get_connections():
    """Current connections as a list of {"name", "kind", "active", "callout"}."""
    conns = _load().get("connections")
    if not conns:
        return [dict(c) for c in config.DEFAULT_CONNECTIONS]
    return [_normalize_connection(c) for c in conns]


def _normalize_connection(c):
    """Coerce one connection dict into a clean, valid shape."""
    name = (c.get("name") or "").strip()
    kind = (c.get("kind") or "direct").strip().lower()
    if kind not in config.CONNECTION_KINDS:
        kind = "direct"
    callout = (c.get("callout") or "").strip() or name
    active = c.get("active", True)
    return {"name": name, "kind": kind, "active": bool(active), "callout": callout}


def set_connections(connections):
    """Validate and save the connections list. Returns the cleaned list."""
    clean = []
    for c in connections:
        nc = _normalize_connection(c)
        if not nc["name"]:
            continue
        clean.append(nc)
    data = _load()
    data["connections"] = clean
    _save(data)
    return clean


def active_connections():
    """Only the connections currently toggled active."""
    return [c for c in get_connections() if c.get("active")]


# ---- Email templates ------------------------------------------------------ #
def _normalize_template(t):
    """
    Ensure a template has separate name/subject/body. Migrates older templates
    that stored everything in 'body' (with a leading 'Subject:' line).
    """
    name = (t.get("name") or "").strip()
    body = (t.get("body") or "")
    subject = t.get("subject")
    if subject is None:  # legacy shape — split a leading "Subject:" line out
        subject = ""
        lines = body.splitlines()
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0].split(":", 1)[1].strip()
            body = "\n".join(lines[1:]).lstrip("\n")
    return {"name": name, "subject": (subject or "").strip(), "body": body.strip()}


def get_templates():
    """Current email templates as a list of {"name", "subject", "body"}."""
    templates = _load().get("email_templates")
    if not templates:
        return [dict(t) for t in config.DEFAULT_EMAIL_TEMPLATES]
    return [_normalize_template(t) for t in templates]


def set_templates(templates):
    """Validate and save the templates list. Returns the cleaned list."""
    clean = []
    for t in templates:
        nt = _normalize_template(t)
        if not nt["name"] and not nt["subject"] and not nt["body"]:
            continue
        nt["name"] = nt["name"] or "Untitled"
        clean.append(nt)
    data = _load()
    data["email_templates"] = clean
    _save(data)
    return clean


# ---- About me ------------------------------------------------------------- #
def get_about():
    """Current 'about me' as {"bio": str, "voice_samples": str}."""
    about = _load().get("about")
    if not about:
        return dict(config.DEFAULT_ABOUT)
    # Be tolerant of partial/old data.
    return {
        "bio": about.get("bio", config.DEFAULT_ABOUT["bio"]),
        "voice_samples": about.get("voice_samples", ""),
    }


def set_about(about):
    """Save the 'about me' dict (bio + voice_samples). Returns the cleaned dict."""
    clean = {
        "bio": (about.get("bio") or "").strip(),
        "voice_samples": (about.get("voice_samples") or "").strip(),
    }
    data = _load()
    data["about"] = clean
    _save(data)
    return clean


# ---- Message channel best-practice guides --------------------------------- #
def get_channel_guides():
    """Per-channel best-practice text as {channel: text} for all MESSAGE_CHANNELS."""
    saved = _load().get("channel_guides") or {}
    guides = {}
    for ch in config.MESSAGE_CHANNELS:
        text = saved.get(ch)
        if text is None:
            text = config.DEFAULT_CHANNEL_GUIDES.get(ch, "")
        guides[ch] = text
    return guides


def get_channel_guide(channel):
    """Best-practice text for one channel (falls back to the default, then '')."""
    return get_channel_guides().get(channel, config.DEFAULT_CHANNEL_GUIDES.get(channel, ""))


def set_channel_guides(guides):
    """Save the per-channel guides. Keeps only known channels. Returns cleaned dict."""
    clean = {ch: (str(guides.get(ch, "")) or "").strip() for ch in config.MESSAGE_CHANNELS}
    data = _load()
    data["channel_guides"] = clean
    _save(data)
    return clean


# ---- Automation (daily run on/off + archive window) ----------------------- #
def get_auto_enabled():
    """Whether the daily auto-run should do its work (default True)."""
    val = _load().get("auto_enabled")
    return config.DEFAULT_AUTO_ENABLED if val is None else bool(val)


def set_auto_enabled(enabled):
    data = _load()
    data["auto_enabled"] = bool(enabled)
    _save(data)


def get_archive_hours():
    """Hours of inactivity before an untouched lead is archived (default 24)."""
    val = _load().get("archive_after_hours")
    try:
        return max(1, int(val))
    except (TypeError, ValueError):
        return config.DEFAULT_ARCHIVE_HOURS


def set_archive_hours(hours):
    data = _load()
    try:
        data["archive_after_hours"] = max(1, int(hours))
    except (TypeError, ValueError):
        data["archive_after_hours"] = config.DEFAULT_ARCHIVE_HOURS
    _save(data)
