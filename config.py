"""
config.py  —  settings and starting defaults.

You can edit everything here, but the two things you'll change most often —
your TOPICS and your RESEARCH_QUESTIONS — are now also editable right inside the
app (open the "⚙️ Research questions" tab). Edits made in the app are saved to a
small file called settings.json and take priority over the defaults below.

So: the lists below are just the STARTING values. Once you edit them in the app,
the app's version wins. (Delete settings.json to fall back to these defaults.)

Quick tour:
  1. DEFAULT_TOPICS             — starting broad areas (edit in-app anytime).
  2. DEFAULT_RESEARCH_QUESTIONS — starting questions + priorities (edit in-app).
  3. DAILY_LEAD_CAP             — how many NEW people to find per day (default 50).
  4. TARGET_REGIONS             — geographies to spread leads across.
  5. SENDER_PROFILE             — a few lines about you, used to personalize emails.
"""

# ---------------------------------------------------------------------------
# 1. DEFAULT_TOPICS — starting broad areas of interest. People get tagged with
#    the ones they fit. Editable in the app's Research-questions tab.
# ---------------------------------------------------------------------------
DEFAULT_TOPICS = [
    "Financial regulation & compliance (MiCA, AML/KYC)",
    "Venture capital & fintech funding",
    "Fintech founders & startups",
    "Banking infrastructure & APIs",
    "AI/ML in fintech",
    "Crypto & blockchain finance",
    "Payments & lending",
    "Wealth & investment tech",
    "Insurtech",
]

# ---------------------------------------------------------------------------
# 2. DEFAULT_RESEARCH_QUESTIONS — starting list of things you want to learn.
#    Each has a "priority" weight (any positive number). The daily lead budget
#    is split across these IN PROPORTION to priority, and higher-priority
#    questions get more search variations. Example: priorities 3 / 2 / 1 split
#    a 50-lead day into roughly 25 / 17 / 8 leads.
#
#    Edit these in the app's "⚙️ Research questions" tab (recommended), or here.
# ---------------------------------------------------------------------------
DEFAULT_RESEARCH_QUESTIONS = [
    {"question": "How are EU and UK firms operationalizing MiCA and AML/KYC compliance in practice?",
     "priority": 3},
    {"question": "What does it really cost and take to build modern banking-API / BaaS infrastructure?",
     "priority": 2},
    {"question": "How do early-stage fintech founders find and win their first 100 customers?",
     "priority": 2},
    {"question": "Where is AI/ML actually delivering value in fintech today versus hype?",
     "priority": 1},
    {"question": "How are payments and lending businesses managing fraud and unit economics?",
     "priority": 1},
]

# ---------------------------------------------------------------------------
# 2b. CONNECTIONS — your warm-intro "bridge" list (editable in-app).
#    A first-filter layer on top of the research questions: people who could
#    later offer a WARM INTRO to someone hard to reach. Two kinds:
#      - "direct"   = the person shares an attribute (e.g. attended MIT, ex-Stripe)
#      - "indirect" = the person is connected to a company/person (e.g. Sequoia);
#                     we look for people who work(ed) closely WITH that target,
#                     preferring JUNIOR/accessible folks (analysts, associates,
#                     recent hires, portfolio founders) — NOT the figureheads.
#    Starts empty; add your own in the app's Settings → 🔗 Connections.
# ---------------------------------------------------------------------------
CONNECTION_KINDS = ["direct", "indirect"]
DEFAULT_CONNECTIONS = []

# ---------------------------------------------------------------------------
# 3. HOW MANY / HOW DIVERSE
# ---------------------------------------------------------------------------
DAILY_LEAD_CAP = 50          # max NEW people discovered per day

# US markets to spread leads across (for geographic diversity within the US).
TARGET_REGIONS = [
    "Northeast",
    "Mid-Atlantic",
    "Southeast",
    "Midwest",
    "Southwest",
    "West",
]

# Company sizes to spread across. (Used in searches and tracked per lead.)
COMPANY_SIZES = ["small", "medium", "large"]

# Seniority levels to spread across, so you don't only get CEOs.
SENIORITIES = [
    "founder",
    "executive (VP/Director/C-level)",
    "mid-level practitioner / manager",
    "operator / individual contributor",
]

# How many tailored interview questions to draft for each person.
QUESTIONS_PER_LEAD = 10

# ---------------------------------------------------------------------------
# 4. ABOUT YOU — used to personalize outreach email drafts.
#    Replace this with a few honest lines about you and your startup.
# ---------------------------------------------------------------------------
SENDER_PROFILE = """\
I'm [Your Name], founder of [Your Startup], an early-stage fintech startup.
I'm doing market research and reaching out to experts for short (20-30 min)
conversations to learn from their experience. I am not selling anything.
"""

# Starting "About me" — editable in the app's Settings tab (saved to settings.json).
#   bio           = facts the AI uses to say WHAT to write
#   voice_samples = past emails you've written, so the AI matches HOW you write
DEFAULT_ABOUT = {
    "bio": SENDER_PROFILE,
    "voice_samples": "",
}

# Starting email templates — editable in the app's "Templates" tab. When you
# flag someone, the AI picks the most relevant template and adapts it.
# Each template has a separate subject and body. Use placeholders like
# [Name], [Company], [Topic], [Your Name] — the AI fills them in.
DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Short & direct",
        "subject": "Quick question about [Topic]",
        "body": (
            "Hi [Name],\n\n"
            "I'm [Your Name], founder of an early-stage fintech. I'm doing market "
            "research (not selling anything) and your work on [Topic] at [Company] "
            "stood out.\n\n"
            "Would you be open to a quick 20-minute call in the next couple of weeks? "
            "I'd love to learn from your experience.\n\n"
            "Thanks,\n[Your Name]"
        ),
    },
    {
        "name": "Warm & specific",
        "subject": "Learning from your experience in [Topic]",
        "body": (
            "Hi [Name],\n\n"
            "I've been researching [Topic] and kept coming across your work at "
            "[Company] — your perspective is exactly the kind I'm hoping to learn "
            "from. I'm an early-stage fintech founder doing market research, not "
            "selling anything.\n\n"
            "Could I ask you a few questions over a short 20-30 minute call? Happy "
            "to work around your schedule.\n\n"
            "Warm regards,\n[Your Name]"
        ),
    },
]

# ---------------------------------------------------------------------------
# 5. ADVANCED (you can usually leave these alone)
# ---------------------------------------------------------------------------
# Claude models. Haiku is cheap/fast for bulk work; Opus is higher-quality for
# the email drafts you only generate occasionally.
DISCOVERY_MODEL = "claude-haiku-4-5"   # used in discovery + enrichment
DRAFTING_MODEL = "claude-sonnet-4-6"   # used for outreach email drafts (good quality, cheaper than Opus)

# Tavily search depth: "basic" (cheaper/faster) or "advanced" (richer results).
TAVILY_SEARCH_DEPTH = "advanced"
# How many search results to pull per query.
TAVILY_RESULTS_PER_QUERY = 8

DB_PATH = "networking.db"
DAILY_LOG_PATH = "daily_log.txt"

# The pipeline stages a person can move through.
STATUSES = [
    "Found",
    "Reviewed",
    "Contacted",
    "Replied",
    "Meeting scheduled",
    "No response",
    "Declined",
]

# How / where you're conducting the conversation (for the CRM field).
OUTREACH_CHANNELS = ["", "Email", "Call", "Google Meet", "External link"]

# ---------------------------------------------------------------------------
# MESSAGE CHANNELS — how you send the FIRST outreach message (distinct from the
# meeting medium above). Each has its own editable best-practice guidance that
# the AI follows when drafting, and each lead tracks which one you're using.
# ---------------------------------------------------------------------------
MESSAGE_CHANNELS = ["Email", "LinkedIn DM", "X DM"]

# Starting best-practice "skill" per channel — editable in the app's Settings tab
# (saved to settings.json under "channel_guides"). These steer how the AI drafts
# for each medium.
DEFAULT_CHANNEL_GUIDES = {
    "Email": (
        "Use a clear, specific subject line. Keep the body under ~150 words. Open "
        "with a concrete reason you're reaching out (their specific work), make one "
        "low-pressure ask for a short 20-30 min call, and close politely with a "
        "signature placeholder. Professional but warm."
    ),
    "LinkedIn DM": (
        "No subject line. Keep it to ~40-75 words — LinkedIn DMs are short. Lead with "
        "a specific, genuine reason you're connecting (reference their role or a post/"
        "project). One simple ask. Conversational and human, not salesy. No signature "
        "block; sign off with just your first name."
    ),
    "X DM": (
        "No subject line. Very short — ~30-50 words, punchy and casual, lowercase-"
        "friendly tone is fine. Reference something specific about them. One quick, "
        "low-friction ask (e.g. open to a quick chat?). No formal sign-off."
    ),
}

# Automation defaults (editable in the app's Settings tab).
DEFAULT_AUTO_ENABLED = True    # daily auto-run on/off
DEFAULT_ARCHIVE_HOURS = 24     # archive untouched leads older than this many hours
