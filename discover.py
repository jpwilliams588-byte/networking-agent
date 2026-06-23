"""
discover.py  —  find new expert leads (the heaviest lift).

What it does, in order:
  1. Works out how many new people to find today (respects the daily cap and how
     many you've already found today).
  2. Splits that budget across your RESEARCH_QUESTIONS by priority — higher
     priority questions get more leads and more searches.
  3. For each question, runs diverse web searches that deliberately spread across
     geographies, company sizes, and seniority levels (so you don't only get
     famous US CEOs). It prioritizes geographies/sizes you have fewer of so far.
  4. Uses Claude to read the search results and pull out real individual people.
  5. Saves them (skipping anyone already in the database) up to the cap.

You can run this directly ("python discover.py") or let daily_run.py call it.
"""

import math
import random
import re

import config
import database
import store
from clients import ask_json, tavily

# The shape we ask Claude to return: a list of people with structured fields.
_PEOPLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "company_size": {"type": "string", "enum": config.COMPANY_SIZES + [""]},
                    "region": {"type": "string", "enum": config.TARGET_REGIONS + [""]},
                    "country": {"type": "string"},
                    "seniority": {"type": "string"},
                    "linkedin_url": {"type": "string"},
                    "source_url": {"type": "string"},
                    "connection_flag": {"type": "string"},
                },
                "required": [
                    "name", "title", "company", "company_size", "region",
                    "country", "seniority", "linkedin_url", "source_url",
                    "connection_flag",
                ],
            },
        }
    },
    "required": ["people"],
}


def allocate_budget(total):
    """
    Split `total` leads across the research questions in proportion to priority.
    Returns a list of (question_dict, count) with counts summing to `total`.
    """
    questions = store.get_research_questions()
    if not questions or total <= 0:
        return []
    weight_sum = sum(max(0, q.get("priority", 1)) for q in questions) or len(questions)

    counts = [int(total * max(0, q.get("priority", 1)) / weight_sum) for q in questions]
    # Hand out any leftover (from rounding down) to the highest-priority questions.
    leftover = total - sum(counts)
    order = sorted(range(len(questions)),
                   key=lambda i: questions[i].get("priority", 1), reverse=True)
    for i in range(leftover):
        counts[order[i % len(order)]] += 1
    return [(questions[i], counts[i]) for i in range(len(questions))]


def _least_covered_first(values, distribution):
    """Order `values` so the ones we have fewest of so far come first."""
    return sorted(values, key=lambda v: distribution.get(v, 0))


# Words that signal an organization rather than a person's name.
_ORG_WORDS = {
    "inc", "llc", "ltd", "plc", "gmbh", "group", "authority", "association",
    "bank", "capital", "partners", "ventures", "technologies", "technology",
    "solutions", "labs", "holdings", "foundation", "institute", "agency",
    "department", "council", "committee", "corp", "corporation", "company",
    "systems", "network", "exchange", "fund", "trust", "limited", "co",
}


def _looks_like_person(name, company):
    """
    True if `name` looks like a real individual rather than an organization.
    Rejects org-sounding names so we don't store companies as people.
    """
    name = (name or "").strip()
    if not name:
        return False
    tokens = [t for t in re.split(r"[\s.,]+", name) if t]
    alpha_tokens = [t for t in tokens if any(c.isalpha() for c in t)]
    if len(alpha_tokens) < 2:               # real names have a first + last
        return False
    if name.strip().lower() == (company or "").strip().lower():
        return False
    lowered = {t.lower().strip(".") for t in tokens}
    if lowered & _ORG_WORDS:                # contains an org keyword
        return False
    if "&" in name or "/" in name:
        return False
    return True


def _connection_phrase(conn):
    """A short search-query phrase that biases toward one connection's bridge people."""
    name = conn.get("name", "")
    if conn.get("kind") == "indirect":
        # Go DOWN the hierarchy: we want accessible insiders, not the figureheads.
        return (f"who currently or formerly works closely with {name} "
                f"(junior analyst, associate, recent hire, or portfolio founder — "
                f"not a partner or C-level executive)")
    return f"who is personally connected to {name} (e.g. attended or worked at {name})"


def _connection_guidance(connections):
    """A natural-language block describing the active connections for Claude."""
    if not connections:
        return ""
    lines = []
    for c in connections:
        if c.get("kind") == "indirect":
            lines.append(
                f"- \"{c['callout']}\" (indirect — anchor: {c['name']}): the person "
                f"currently or formerly works closely WITH {c['name']}. STRONGLY prefer "
                f"JUNIOR, accessible people (associates, analysts, recent hires, "
                f"portfolio founders). Do NOT return partners, C-suite, or well-known "
                f"figureheads — they are the goal, not the bridge."
            )
        else:
            lines.append(
                f"- \"{c['callout']}\" (direct — anchor: {c['name']}): the person "
                f"personally shares this attribute (e.g. attended/worked at {c['name']})."
            )
    return (
        "\n\nWARM-INTRO CONNECTIONS — these are a FIRST-FILTER lens. We are building "
        "relationships with people who could later offer a warm intro to someone hard "
        "to reach. Prefer people who match one of these connections AND can still help "
        "answer the research question:\n" + "\n".join(lines) +
        "\n\nFor each person, set 'connection_flag' to the matching connection "
        "callout(s) joined by '; ' (e.g. \"Sequoia network\"), or \"\" if none apply. "
        "Only set it on clear evidence — never guess."
    )


def build_queries(question_text, target):
    """
    Build a handful of diverse search queries for one research question, biased
    toward the geographies and company sizes we currently have the fewest of, and
    toward our active warm-intro connections when any are set.
    """
    regions = _least_covered_first(config.TARGET_REGIONS, database.region_distribution())
    sizes = _least_covered_first(config.COMPANY_SIZES, database.size_distribution())
    seniorities = list(config.SENIORITIES)
    random.shuffle(seniorities)  # vary which seniorities lead, run to run

    connections = store.active_connections()

    # Roughly one query per ~3 desired leads, but at least 2 and at most 10.
    num_queries = max(2, min(10, math.ceil(target / 3)))

    queries = []
    for i in range(num_queries):
        region = regions[i % len(regions)]
        size = sizes[i % len(sizes)]
        seniority = seniorities[i % len(seniorities)]
        query = (
            f"fintech {seniority} at a {size} company in the {region} United States "
            f"— expert relevant to: {question_text}."
        )
        if connections:
            conn = connections[i % len(connections)]
            query += f" {_connection_phrase(conn)}."
        query += " LinkedIn profile."
        queries.append(query)
    return queries


def _search(query):
    """Run one Tavily search and return its result records."""
    client = tavily()
    resp = client.search(
        query=query,
        search_depth=config.TAVILY_SEARCH_DEPTH,
        max_results=config.TAVILY_RESULTS_PER_QUERY,
    )
    return resp.get("results", [])


def _results_to_text(results):
    """Flatten Tavily results into a readable blob for Claude to mine."""
    chunks = []
    for r in results:
        chunks.append(
            f"TITLE: {r.get('title','')}\n"
            f"URL: {r.get('url','')}\n"
            f"CONTENT: {(r.get('content') or '')[:1500]}\n---"
        )
    return "\n".join(chunks)


def extract_people(question_text, results, target):
    """Use Claude to pull real, diverse individuals out of the search results."""
    if not results:
        return []
    system = (
        "You extract real individual professionals from web search results for "
        "market research. The 'name' field MUST be one real individual's full "
        "name (first and last) — NEVER a company, organization, agency, "
        "authority, department, team, fund, or product. If a result is about an "
        "organization rather than a person, skip it. Only include people based in "
        "the United States. Prefer a DIVERSE mix across seniority levels (founders, "
        "executives, mid-level practitioners, individual contributors) and company "
        "sizes (small/medium/large). Use the LinkedIn URL from the results when "
        "present; otherwise leave it blank. If a field is unknown, use an empty "
        "string. Make a best-effort estimate for company_size. The 'region' field "
        "MUST be exactly one of these US markets: "
        + "; ".join(config.TARGET_REGIONS)
        + ". Put the specific US state (e.g. 'California') in 'country'."
        + _connection_guidance(store.active_connections())
    )
    user = (
        f"Research question we want answered:\n{question_text}\n\n"
        f"Find up to {target * 2} distinct people who could credibly help answer "
        f"it, from these search results:\n\n{_results_to_text(results)}"
    )
    data = ask_json(config.DISCOVERY_MODEL, system, user, _PEOPLE_SCHEMA)
    return data.get("people", [])


def discover(max_new=None, progress=None):
    """
    Discover and save new leads. Returns the number actually added.
    `max_new` optionally lowers today's limit (handy for testing).
    `progress` is an optional callback(message) for the UI.
    """
    database.init_db()

    already = database.count_added_on()
    headroom = max(0, config.DAILY_LEAD_CAP - already)
    if max_new is not None:
        headroom = min(headroom, max_new)
    if headroom == 0:
        if progress:
            progress("Daily limit already reached — nothing to do.")
        return 0

    added = 0
    for question, target in allocate_budget(headroom):
        if added >= headroom:
            break
        qtext = question["question"]
        if progress:
            progress(f"Searching for ~{target} leads on: {qtext[:60]}…")

        results = []
        for query in build_queries(qtext, target):
            try:
                results.extend(_search(query))
            except Exception as e:  # one bad query shouldn't kill the run
                if progress:
                    progress(f"  (search issue, skipping one query: {e})")

        people = extract_people(qtext, results, target)
        for person in people:
            if added >= headroom:
                break
            if not _looks_like_person(person.get("name"), person.get("company")):
                if progress:
                    progress(f"  (skipped non-person: {person.get('name')})")
                continue
            record = {
                "name": person.get("name"),
                "title": person.get("title"),
                "company": person.get("company"),
                "company_size": person.get("company_size") or "",
                "region": person.get("region") or "",
                "country": person.get("country") or "",
                "linkedin_url": person.get("linkedin_url") or "",
                "source_url": person.get("source_url") or "",
                "connection_flag": person.get("connection_flag") or "",
                "topics": "",  # filled during enrichment
                "answers_questions": qtext,
                "status": "Found",
            }
            if database.add_expert(record):
                added += 1
                if progress:
                    progress(f"  + {record['name']} ({record.get('company','')})")

    if progress:
        progress(f"Done. Added {added} new lead(s).")
    return added


if __name__ == "__main__":
    n = discover(progress=print)
    print(f"Discovered {n} new leads.")
