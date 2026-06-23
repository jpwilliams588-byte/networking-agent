"""
enrich.py  —  fill in each new lead.

For every person still at the "Found" stage, this:
  1. Runs a focused web search on their name + company to learn more.
  2. Tries to find a public email in the results; if none, makes a careful
     best-effort guess from their name and company domain (clearly marked as a
     guess). If neither works, we just keep their LinkedIn URL for manual reach-out.
  3. Asks Claude to write a short summary, tag which of your topics and research
     questions they can help with, and draft 10 tailored interview questions.
  4. Moves them to the "Reviewed" stage.

Safe to stop and re-run — it only touches people still at "Found".
"""

import re
from urllib.parse import urlparse

import config
import database
import store
from clients import ask_json, tavily

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Domains we should never treat as a person's company website.
_NON_COMPANY_DOMAINS = (
    "linkedin.", "twitter.", "x.com", "facebook.", "instagram.", "youtube.",
    "crunchbase.", "bloomberg.", "wikipedia.", "medium.", "github.",
    "google.", "reddit.", "forbes.", "techcrunch.",
)

_LEAD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "answers_questions": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "education_flag": {
            "type": "string",
            "enum": ["", "MIT Sloan", "MIT (undergrad)", "MIT Sloan; MIT (undergrad)"],
        },
        "connection_flag": {"type": "string"},
    },
    "required": ["summary", "topics", "answers_questions", "questions",
                 "education_flag", "connection_flag"],
}


def _search(name, company):
    client = tavily()
    query = f'"{name}" {company} fintech background role contact'
    resp = client.search(
        query=query,
        search_depth=config.TAVILY_SEARCH_DEPTH,
        max_results=config.TAVILY_RESULTS_PER_QUERY,
    )
    return resp.get("results", [])


# Generic mailboxes we'd rather not present as someone's personal email.
_GENERIC_PREFIXES = (
    "info", "investors", "support", "contact", "press", "sales", "hello",
    "admin", "help", "media", "careers", "jobs", "marketing", "team",
    "office", "enquiries", "inquiries", "noreply", "no-reply", "webmaster",
)


def _find_email(results, name, company_domain):
    """
    Look for a TRUSTWORTHY email in the page contents. We only accept an address
    if it (a) contains the person's first or last name, or (b) sits on the
    company's own website domain and isn't a generic inbox. Random third-party
    addresses that merely appear on a page are ignored, to avoid false matches.
    """
    blob = " ".join((r.get("content") or "") for r in results)
    name_parts = [p.lower() for p in re.split(r"\s+", (name or "").strip()) if p.isalpha()]

    company_match = None
    for candidate in _EMAIL_RE.findall(blob):
        low = candidate.lower()
        if any(low.endswith(bad) for bad in (".png", ".jpg", ".gif", ".webp")):
            continue
        if "example.com" in low or "sentry" in low or "wixpress" in low:
            continue
        local, _, host = low.partition("@")
        if name_parts and any(part in local for part in name_parts):
            return candidate  # best: clearly this person's address
        if company_domain and host == company_domain and local not in _GENERIC_PREFIXES:
            company_match = company_match or candidate
    return company_match


def _company_domain(results, company):
    """Find a plausible company website domain from the result URLs."""
    tokens = [t.lower() for t in re.findall(r"[A-Za-z]+", company or "") if len(t) > 2]
    for r in results:
        host = urlparse(r.get("url", "")).netloc.lower().lstrip("www.")
        if not host or any(bad in host for bad in _NON_COMPANY_DOMAINS):
            continue
        if any(tok in host for tok in tokens):
            return host
    return None


def _guess_email(name, domain):
    """Conservative first.last@domain guess; only used when no real email found."""
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p.isalpha()]
    if len(parts) < 2 or not domain:
        return None
    first, last = parts[0].lower(), parts[-1].lower()
    return f"{first}.{last}@{domain}"


def _results_to_text(results):
    return "\n".join(
        f"- {r.get('title','')}: {(r.get('content') or '')[:800]} ({r.get('url','')})"
        for r in results
    )


def _find_photo(name, company):
    """
    Best-effort: try to find a headshot image URL via Tavily image search.
    Returns a URL string or None. Photos are often missing or imperfect — this
    is a hint, not a guarantee.
    """
    try:
        client = tavily()
        resp = client.search(
            query=f"{name} {company} headshot photo",
            search_depth="basic",
            max_results=3,
            include_images=True,
        )
        images = resp.get("images") or []
        for img in images:
            # Tavily may return plain URL strings or {"url": ...} dicts.
            url = img.get("url") if isinstance(img, dict) else img
            if url and str(url).lower().startswith("http"):
                return url
    except Exception:
        pass
    return None


def _generate_package(expert, results):
    """Ask Claude for the summary, tags, and interview questions."""
    system = (
        "You prepare a market-research brief on a single professional. Be concise "
        "and grounded only in the information given. When choosing topics, pick "
        "ONLY from the provided topic list. When choosing which research questions "
        "they can help answer, pick ONLY from the provided question list. Draft "
        f"exactly {config.QUESTIONS_PER_LEAD} specific, open-ended interview "
        "questions tailored to this person's likely expertise. "
        "Set 'education_flag' ONLY if the information clearly shows they attended "
        "MIT: use 'MIT Sloan' for the MIT Sloan School of Management (MBA/graduate "
        "business), 'MIT (undergrad)' for an MIT undergraduate degree, or both "
        "joined by '; '. If there is no clear MIT evidence, use an empty string — "
        "never guess."
    )
    topics = store.get_topics()
    questions = store.get_research_questions()
    connections = store.active_connections()
    if connections:
        conn_lines = []
        for c in connections:
            if c.get("kind") == "indirect":
                conn_lines.append(
                    f"- \"{c['callout']}\" (indirect — anchor: {c['name']}): set this "
                    f"if the person works or worked closely WITH {c['name']} "
                    f"(e.g. employee, portfolio founder, close collaborator)."
                )
            else:
                conn_lines.append(
                    f"- \"{c['callout']}\" (direct — anchor: {c['name']}): set this if "
                    f"the person personally shares this attribute (e.g. attended/worked "
                    f"at {c['name']})."
                )
        system += (
            "\nSet 'connection_flag' to the matching warm-intro connection callout(s), "
            "joined by '; ', ONLY on clear evidence (never guess); use an empty string "
            "if none apply. Connections:\n" + "\n".join(conn_lines)
        )
    else:
        system += "\nSet 'connection_flag' to an empty string."
    user = (
        f"PERSON:\n"
        f"Name: {expert.get('name')}\n"
        f"Title: {expert.get('title')}\n"
        f"Company: {expert.get('company')} ({expert.get('company_size')})\n"
        f"Region: {expert.get('region')} {expert.get('country')}\n\n"
        f"TOPIC LIST (choose from these):\n- " + "\n- ".join(topics) + "\n\n"
        f"RESEARCH QUESTION LIST (choose from these):\n- "
        + "\n- ".join(q["question"] for q in questions) + "\n\n"
        f"WHAT WE FOUND ONLINE:\n{_results_to_text(results) or '(little found)'}\n\n"
        f"Write: a 2-3 sentence summary of who they are and why they're relevant; "
        f"the topics they fit; the research questions they can help answer; and "
        f"{config.QUESTIONS_PER_LEAD} interview questions to ask them."
    )
    return ask_json(config.DISCOVERY_MODEL, system, user, _LEAD_SCHEMA)


def enrich_one(expert, progress=None):
    """Enrich a single expert record (a dict from the database)."""
    name, company = expert.get("name"), expert.get("company") or ""
    results = []
    try:
        results = _search(name, company)
    except Exception as e:
        if progress:
            progress(f"  (search issue for {name}: {e})")

    # Email: trustworthy match first, then a careful guess, else fall back to LinkedIn.
    domain = _company_domain(results, company)
    email = _find_email(results, name, domain)
    email_source = "found" if email else "none"
    if not email:
        guess = _guess_email(name, domain)
        if guess:
            email, email_source = guess, "guessed"

    # AI brief + questions.
    try:
        pkg = _generate_package(expert, results)
    except Exception as e:
        if progress:
            progress(f"  (AI issue for {name}: {e})")
        pkg = {}

    questions = pkg.get("questions", [])
    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    # Best-effort photo (may be missing).
    photo = _find_photo(name, company)

    database.update_fields(
        expert["id"],
        email=email,
        email_source=email_source,
        photo_url=photo or "",
        topics=", ".join(pkg.get("topics", [])),
        answers_questions=" | ".join(pkg.get("answers_questions", []))
                          or expert.get("answers_questions", ""),
        summary=pkg.get("summary", ""),
        draft_questions=numbered,
        education_flag=pkg.get("education_flag", ""),
        connection_flag=pkg.get("connection_flag", "")
                        or expert.get("connection_flag", ""),
        status="Reviewed",
    )
    if progress:
        tag = {"found": "email found", "guessed": "email guessed",
               "none": "LinkedIn only"}[email_source]
        edu = pkg.get("education_flag", "")
        extra = f", 🎓 {edu}" if edu else ""
        progress(f"  reviewed {name} — {tag}{extra}")


def enrich_all(progress=None):
    """Enrich every lead still at the 'Found' stage. Returns the count processed."""
    database.init_db()
    pending = database.get_experts(status="Found", order_by="created_at ASC")
    if progress:
        progress(f"Enriching {len(pending)} new lead(s)…")
    for expert in pending:
        enrich_one(expert, progress=progress)
    if progress:
        progress(f"Done. Enriched {len(pending)} lead(s).")
    return len(pending)


if __name__ == "__main__":
    enrich_all(progress=print)
