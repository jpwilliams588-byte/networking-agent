"""
app.py  —  the web app you actually use.

Run it with:  streamlit run app.py   (or double-click run.bat)

Tabs:
  ⚡ Quick review   — fast triage: skim each person, flag the ones you want (a
                      personalized email auto-drafts when you flag).
  📊 Dashboard      — pipeline funnel + geography / company-size breakdown.
  👥 Browse & manage — full filterable table with details and status control.
  ✉️ Templates      — your email templates (the AI picks the best one when drafting).
  ⚙️ Settings       — research questions, topics, and your "About me".
"""

import pandas as pd
import streamlit as st

import config
import database
import discover
import draft_email
import enrich
import store

st.set_page_config(page_title="Networking Agent", page_icon="🤝", layout="wide")
database.init_db()


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #
def show_photo(person, width=72):
    """Show the person's photo, or an initials avatar if none/broken."""
    url = person.get("photo_url")
    if url:
        try:
            st.image(url, width=width)
            return
        except Exception:
            pass
    initials = "".join(p[0] for p in (person.get("name") or "?").split()[:2]).upper()
    st.markdown(
        f"<div style='width:{width}px;height:{width}px;border-radius:50%;"
        f"background:#e6e6e6;display:flex;align-items:center;justify-content:center;"
        f"font-size:{width // 3}px;color:#666;font-weight:600;'>{initials or '?'}</div>",
        unsafe_allow_html=True,
    )


def edu_badge(person):
    """Return a 🎓 badge string for MIT alumni, or ''."""
    e = (person.get("education_flag") or "").strip()
    return f"🎓 {e}" if e else ""


def connection_badge(person):
    """Return a 🔗 badge string for warm-intro connections, or ''."""
    c = (person.get("connection_flag") or "").strip()
    return f"🔗 {c}" if c else ""


def badges(person):
    """Combine the education + connection badges into one ' · '-joined string."""
    return "  ·  ".join(b for b in (edu_badge(person), connection_badge(person)) if b)


def flag_and_draft(eid, channel=None):
    """Flag a person AND auto-generate a personalized draft for the chosen channel."""
    label = channel or "Email"
    with st.spinner(f"Flagging and drafting a personalized {label} message…"):
        database.set_flag(eid, True)
        try:
            draft_email.draft_outreach(eid, channel=channel)
        except Exception as e:
            st.warning(f"Flagged, but draft failed: {e}")


def channel_emoji(channel):
    """A small icon for a message channel."""
    return {"Email": "✉️", "LinkedIn DM": "in", "X DM": "𝕏"}.get(channel, "✉️")


def parse_channels(value):
    """Split a stored message_channel string into an ordered, de-duped list."""
    out = []
    for part in (value or "").split(","):
        ch = part.strip()
        if ch in config.MESSAGE_CHANNELS and ch not in out:
            out.append(ch)
    return out


def primary_channel(value):
    """The first selected channel (the one we auto-draft for), or 'Email'."""
    chans = parse_channels(value)
    return chans[0] if chans else "Email"


def split_draft(text):
    """Split a draft into (subject, body). Handles DMs that have no subject line."""
    lines = (text or "").splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return subject, body
    return "", (text or "").strip()


def set_status(eid, status):
    """Update status; if it's a 'they responded' stage, credit the logged email."""
    database.update_status(eid, status)
    if status in ("Replied", "Meeting scheduled"):
        database.mark_email_replied(eid)


def parse_subject(draft):
    """Pull the 'Subject:' line out of a draft, if present."""
    for line in (draft or "").splitlines():
        if line.lower().startswith("subject:"):
            return line.split(":", 1)[1].strip()
    return "(no subject)"


# --------------------------------------------------------------------------- #
# Sidebar: run the pipeline on demand
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Run now")
    st.caption("The daily job does this automatically. Use these to run by hand.")

    max_new = st.number_input(
        "Max new leads this run", min_value=1, max_value=config.DAILY_LEAD_CAP,
        value=min(10, config.DAILY_LEAD_CAP),
        help="Start small (e.g. 5) to test, then raise it.",
    )

    if st.button("🔍 Find new leads", use_container_width=True):
        log = st.empty()
        lines = []
        def show(msg):
            lines.append(msg)
            log.code("\n".join(lines[-15:]))
        with st.spinner("Searching the web…"):
            n = discover.discover(max_new=int(max_new), progress=show)
        st.success(f"Added {n} new lead(s).")

    if st.button("📝 Enrich new leads", use_container_width=True):
        log = st.empty()
        lines = []
        def show(msg):
            lines.append(msg)
            log.code("\n".join(lines[-15:]))
        with st.spinner("Researching and writing briefs…"):
            n = enrich.enrich_all(progress=show)
        st.success(f"Enriched {n} lead(s). See them in 👥 Browse & manage (newest first).")

    today = database.count_added_on()
    st.metric("Found today", f"{today} / {config.DAILY_LEAD_CAP}")


# --------------------------------------------------------------------------- #
# Main tabs
# --------------------------------------------------------------------------- #
tab_quick, tab_dash, tab_browse, tab_templates, tab_ab, tab_settings = st.tabs(
    ["⚡ Quick review", "📊 Dashboard", "👥 Browse & manage",
     "✉️ Templates", "📈 A/B testing", "⚙️ Settings"]
)

# ---- Quick review (fast triage) ------------------------------------------- #
with tab_quick:
    st.subheader("Quick review")
    st.caption(
        "Reviewed people you haven't flagged yet. Skim each one and **Flag** the "
        "ones you want to reach out to — a personalized email drafts automatically. "
        "**Skip** removes someone from this queue."
    )

    qf1, qf2 = st.columns([1, 2])
    with qf1:
        mit_only = st.checkbox("🎓 MIT alumni only", key="quick_mit")
    with qf2:
        conn_callouts = sorted({c["callout"] for c in store.get_connections()})
        quick_conn = st.selectbox("🔗 Connection", ["(any)"] + conn_callouts,
                                  key="quick_conn")
    queue = database.get_experts(
        status="Reviewed", flagged=False,
        education_like="MIT" if mit_only else None,
        connection_like=None if quick_conn == "(any)" else quick_conn,
        order_by="created_at ASC",
    )
    st.caption(f"{len(queue)} to review")

    if not queue:
        st.info("Nothing to review right now. Use the sidebar to find & enrich leads.")
    for person in queue[:20]:  # cap for speed
        eid = person["id"]
        with st.container(border=True):
            c_photo, c_info = st.columns([1, 6])
            with c_photo:
                show_photo(person, width=72)
            with c_info:
                badge = badges(person)
                header = f"### {person['name']}"
                if badge:
                    header += f"  ·  {badge}"
                st.markdown(header)
                st.write(f"**{person.get('title','')}** at **{person.get('company','')}** "
                         f"· {person.get('region','')} {person.get('country','')}")
                if person.get("connection_note"):
                    st.markdown(f"🔗 *{person['connection_note']}*")
                if person.get("answers_questions"):
                    st.markdown(f"**Can help answer:** {person['answers_questions']}")
                if person.get("outreach_channel") or person.get("meeting_location"):
                    conv = " · ".join(b for b in (person.get("outreach_channel"),
                                                  person.get("meeting_location")) if b)
                    st.markdown(f"**Conversation:** {conv}")
                if person.get("summary"):
                    st.caption(person["summary"])
                if person.get("draft_questions"):
                    with st.expander("10 questions to ask"):
                        st.text(person["draft_questions"])

                qchannels = st.multiselect(
                    "Respond via", config.MESSAGE_CHANNELS,
                    default=parse_channels(person.get("message_channel")) or ["Email"],
                    key=f"qchan_{eid}",
                    help="Pick one or more. The auto-draft uses the first one; you can "
                         "draft the others later in Browse & manage.")
                b1, b2, _ = st.columns([1, 1, 4])
                with b1:
                    if st.button("🚩 Flag", key=f"flag_{eid}", use_container_width=True):
                        chans = qchannels or ["Email"]
                        database.update_fields(eid, message_channel=", ".join(chans))
                        flag_and_draft(eid, channel=chans[0])
                        st.toast(f"Flagged {person['name']} — {chans[0]} draft ready.")
                        st.rerun()
                with b2:
                    if st.button("👎 Skip", key=f"skip_{eid}", use_container_width=True):
                        database.update_status(eid, "Declined")
                        st.rerun()
    if len(queue) > 20:
        st.caption(f"Showing first 20 of {len(queue)}. Flag or skip some to see more.")

# ---- Dashboard ------------------------------------------------------------ #
with tab_dash:
    st.subheader("Pipeline")
    counts = database.stats()
    cols = st.columns(len(config.STATUSES))
    for col, status in zip(cols, config.STATUSES):
        col.metric(status, counts.get(status, 0))
    st.caption(f"🗄 Archived (rolled off, hidden from active views): "
               f"**{database.archived_count()}**")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("By US market")
        regions = database.region_distribution()
        if regions:
            st.bar_chart(pd.DataFrame({"leads": regions}))
        else:
            st.caption("No leads yet.")
    with c2:
        st.subheader("By company size")
        sizes = database.size_distribution()
        if sizes:
            st.bar_chart(pd.DataFrame({"leads": sizes}))
        else:
            st.caption("No leads yet.")

# ---- Browse & manage ------------------------------------------------------ #
with tab_browse:
    with st.expander("➕ Add a person manually"):
        with st.form("add_person", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            with a1:
                add_name = st.text_input("Name *")
                add_title = st.text_input("Title")
                add_company = st.text_input("Company")
                add_size = st.selectbox("Company size", [""] + config.COMPANY_SIZES)
            with a2:
                add_region = st.selectbox("US market", [""] + config.TARGET_REGIONS)
                add_state = st.text_input("State")
                add_email = st.text_input("Email")
                add_linkedin = st.text_input("LinkedIn URL")
            with a3:
                add_status = st.selectbox("Status", config.STATUSES)
                add_channel = st.selectbox("How/where reaching out", config.OUTREACH_CHANNELS)
                add_location = st.text_input("Meeting link / location")
                add_notes = st.text_area("Notes", height=80)
            if st.form_submit_button("Add person", type="primary"):
                if not add_name.strip():
                    st.error("Name is required.")
                else:
                    ok = database.add_expert({
                        "name": add_name, "title": add_title, "company": add_company,
                        "company_size": add_size, "region": add_region, "country": add_state,
                        "email": add_email or None,
                        "email_source": "manual" if add_email else "none",
                        "linkedin_url": add_linkedin, "status": add_status,
                        "outreach_channel": add_channel, "meeting_location": add_location,
                        "notes": add_notes,
                    })
                    if ok:
                        st.success(f"Added {add_name}.")
                    else:
                        st.warning(f"{add_name} looks like a duplicate — not added.")

    st.subheader("Filters")
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        status = st.selectbox("Status", ["(any)"] + config.STATUSES)
    with f2:
        region = st.selectbox("US market", ["(any)"] + config.TARGET_REGIONS)
    with f3:
        size = st.selectbox("Company size", ["(any)"] + config.COMPANY_SIZES)
    with f4:
        contact = st.selectbox("Contact", ["(any)", "has email", "LinkedIn only"])
    with f5:
        msg_channel = st.selectbox("✉️ Channel", ["(any)"] + config.MESSAGE_CHANNELS)

    g1, g2, g3, g4, g5 = st.columns(5)
    with g1:
        topic = st.selectbox("Topic", ["(any)"] + store.get_topics())
    with g2:
        browse_callouts = sorted({c["callout"] for c in store.get_connections()})
        connection = st.selectbox("🔗 Connection", ["(any)"] + browse_callouts,
                                  key="browse_conn")
    with g3:
        only_flagged = st.checkbox("Flagged only")
    with g4:
        mit_browse = st.checkbox("🎓 MIT alumni only", key="browse_mit")
    with g5:
        show_archived = st.checkbox("🗄 Show archived", key="browse_archived",
                                    help="View leads that rolled off into the archive.")

    experts = database.get_experts(
        status=None if status == "(any)" else status,
        region=None if region == "(any)" else region,
        company_size=None if size == "(any)" else size,
        has_email=True if contact == "has email" else (False if contact == "LinkedIn only" else None),
        topic=None if topic == "(any)" else topic,
        education_like="MIT" if mit_browse else None,
        connection_like=None if connection == "(any)" else connection,
        message_channel=None if msg_channel == "(any)" else msg_channel,
        flagged=True if only_flagged else None,
        archived_only=show_archived,
    )

    st.caption(f"{len(experts)} matching lead(s)")

    if experts:
        table = pd.DataFrame(experts)[
            ["id", "name", "title", "company", "company_size", "region",
             "topics", "answers_questions", "education_flag", "connection_flag",
             "message_channel", "email_source", "status", "outreach_channel", "flagged"]
        ]
        st.dataframe(
            table, use_container_width=True, hide_index=True,
            column_config={
                "topics": st.column_config.TextColumn("Topics", width="medium"),
                "answers_questions": st.column_config.TextColumn("Can help answer", width="large"),
            },
        )

        # ---- Detail / actions for one person ---- #
        st.divider()
        st.subheader("Open a lead")
        options = {f"{e['id']} — {e['name']} ({e.get('company','')})": e["id"]
                   for e in experts}
        chosen = st.selectbox("Select someone", list(options.keys()))
        eid = options[chosen]
        person = database.get_expert(eid)

        left, right = st.columns([2, 1])
        with left:
            pc, hc = st.columns([1, 5])
            with pc:
                show_photo(person, width=84)
            with hc:
                badge = badges(person)
                st.markdown(f"### {person['name']}" + (f"  ·  {badge}" if badge else ""))
                st.write(f"**{person.get('title','')}** at **{person.get('company','')}** "
                         f"({person.get('company_size','?')})")
                st.write(f"📍 {person.get('region','')} {person.get('country','')}  "
                         f"·  ✉️ **{person.get('message_channel') or 'Email'}**")
                if person.get("connection_note"):
                    st.markdown(f"🔗 *{person['connection_note']}*")
            if not person.get("summary"):
                st.info("This lead isn't enriched yet — no summary, topics, or interview "
                        "questions. Enrich it to fill in that detail.")
                if st.button("✨ Enrich this lead", key=f"enrich_{eid}"):
                    with st.spinner("Researching and writing a brief…"):
                        enrich.enrich_one(person)
                    st.success("Enriched.")
                    st.rerun()
            if person.get("summary"):
                st.markdown("**Why talk to them**")
                st.write(person["summary"])
            if person.get("topics"):
                st.markdown(f"**Topics:** {person['topics']}")
            if person.get("answers_questions"):
                st.markdown(f"**Can help answer:** {person['answers_questions']}")
            if person.get("outreach_channel") or person.get("meeting_location") or person.get("meeting_time"):
                bits = [b for b in (person.get("outreach_channel"),
                                    person.get("meeting_location"),
                                    person.get("meeting_time")) if b]
                st.markdown("**Conversation:** " + " · ".join(bits))
            if person.get("notes"):
                st.markdown(f"**Notes:** {person['notes']}")
            if person.get("draft_questions"):
                with st.expander("🔟 10 questions to ask"):
                    st.text(person["draft_questions"])

        with right:
            st.markdown("**Contact**")
            if person.get("email"):
                tag = {"found": "✅ found", "guessed": "⚠️ guessed"}.get(
                    person.get("email_source"), "")
                st.write(f"✉️ {person['email']} {tag}")
            if person.get("linkedin_url"):
                st.markdown(f"[🔗 LinkedIn profile]({person['linkedin_url']})")
            if not person.get("email") and not person.get("linkedin_url"):
                st.caption("No public contact found.")

            st.markdown("**Message channel(s)**")
            sel_channels = st.multiselect(
                "Channels", config.MESSAGE_CHANNELS,
                default=parse_channels(person.get("message_channel")),
                key=f"mc_{eid}", label_visibility="collapsed",
                help="Track every channel you'll use for this lead. The first one is "
                     "the primary (used by the auto-draft).")
            if st.button("💾 Save channels", key=f"mcsave_{eid}", use_container_width=True):
                database.update_fields(eid, message_channel=", ".join(sel_channels))
                st.toast("Channels saved.")
                st.rerun()

            st.markdown("**Actions**")
            flagged = bool(person.get("flagged"))
            if flagged:
                if st.button("🚩 Unflag", use_container_width=True):
                    database.set_flag(eid, False)
                    st.rerun()
            else:
                if st.button("🚩 Flag for outreach", use_container_width=True):
                    # auto-draft for the lead's primary (first) channel
                    flag_and_draft(eid, channel=primary_channel(person.get("message_channel")))
                    st.rerun()

            new_status = st.selectbox(
                "Status", config.STATUSES,
                index=config.STATUSES.index(person.get("status", "Found"))
                if person.get("status") in config.STATUSES else 0,
            )
            if new_status != person.get("status"):
                set_status(eid, new_status)
                st.rerun()

            st.caption("Quick update:")
            q1, q2, q3 = st.columns(3)
            if q1.button("✅ Replied", key=f"qr_{eid}", use_container_width=True):
                set_status(eid, "Replied"); st.rerun()
            if q2.button("📅 Meeting", key=f"qm_{eid}", use_container_width=True):
                set_status(eid, "Meeting scheduled"); st.rerun()
            if q3.button("🔇 No resp.", key=f"qn_{eid}", use_container_width=True):
                set_status(eid, "No response"); st.rerun()

        # ---- Manual edit ---- #
        with st.expander("✏️ Edit this lead"):
            with st.form(f"edit_{eid}"):
                e1, e2, e3 = st.columns(3)
                with e1:
                    ed_title = st.text_input("Title", value=person.get("title") or "")
                    ed_company = st.text_input("Company", value=person.get("company") or "")
                    ed_size = st.selectbox(
                        "Company size", [""] + config.COMPANY_SIZES,
                        index=([""] + config.COMPANY_SIZES).index(person.get("company_size"))
                        if person.get("company_size") in config.COMPANY_SIZES else 0)
                    ed_region = st.selectbox(
                        "US market", [""] + config.TARGET_REGIONS,
                        index=([""] + config.TARGET_REGIONS).index(person.get("region"))
                        if person.get("region") in config.TARGET_REGIONS else 0)
                with e2:
                    ed_state = st.text_input("State", value=person.get("country") or "")
                    ed_email = st.text_input("Email", value=person.get("email") or "")
                    ed_linkedin = st.text_input("LinkedIn URL", value=person.get("linkedin_url") or "")
                    ed_status = st.selectbox(
                        "Status", config.STATUSES,
                        index=config.STATUSES.index(person.get("status"))
                        if person.get("status") in config.STATUSES else 0)
                with e3:
                    ed_channel = st.selectbox(
                        "How/where reaching out", config.OUTREACH_CHANNELS,
                        index=config.OUTREACH_CHANNELS.index(person.get("outreach_channel"))
                        if person.get("outreach_channel") in config.OUTREACH_CHANNELS else 0)
                    ed_location = st.text_input("Meeting link / location",
                                                value=person.get("meeting_location") or "")
                    ed_time = st.text_input("Meeting time",
                                            value=person.get("meeting_time") or "")
                    ed_notes = st.text_area("Notes", value=person.get("notes") or "", height=80)

                st.markdown("**Enriched details** (from the AI — edit freely)")
                ed_summary = st.text_area("Summary", value=person.get("summary") or "", height=80)
                ed_topics = st.text_input("Topics", value=person.get("topics") or "")
                ed_answers = st.text_input("Can help answer",
                                           value=person.get("answers_questions") or "")
                ed_connnote = st.text_input("🔗 Connection note (how they link to a target)",
                                            value=person.get("connection_note") or "")
                ed_questions = st.text_area("Questions to ask them",
                                            value=person.get("draft_questions") or "", height=160)
                if st.form_submit_button("💾 Save changes", type="primary"):
                    database.update_fields(
                        eid, title=ed_title, company=ed_company, company_size=ed_size,
                        region=ed_region, country=ed_state, email=ed_email or None,
                        linkedin_url=ed_linkedin, status=ed_status, outreach_channel=ed_channel,
                        meeting_location=ed_location, meeting_time=ed_time, notes=ed_notes,
                        summary=ed_summary, topics=ed_topics, answers_questions=ed_answers,
                        connection_note=ed_connnote, draft_questions=ed_questions,
                    )
                    if ed_status in ("Replied", "Meeting scheduled"):
                        database.mark_email_replied(eid)
                    st.success("Saved.")
                    st.rerun()

        # ---- Outreach draft ---- #
        st.divider()
        st.subheader("Outreach message draft")
        st.caption("Drafts only — send from your own account, then click ✅ Mark as sent to log it. "
                   "The draft adapts to the chosen channel and its best-practice guidance.")

        tmpl_names = [t["name"] for t in store.get_templates() if t.get("name")]
        dc1, dc2, dc3 = st.columns([2, 2, 1])
        with dc1:
            draft_channel = st.selectbox(
                "Channel", config.MESSAGE_CHANNELS,
                index=config.MESSAGE_CHANNELS.index(primary_channel(person.get("message_channel"))),
                help="Which channel to write this draft for. Email = subject + body; "
                     "DMs are shorter with no subject line.")
        with dc2:
            pick = st.selectbox("Template", ["(auto — AI picks)"] + tmpl_names,
                                help="Auto lets the AI choose the best fit; or force a specific one.")
        with dc3:
            st.write("")
            gen = st.button("✨ Generate draft", use_container_width=True)
        if gen:
            override = None if pick.startswith("(auto") else pick
            with st.spinner(f"Writing a personalized {draft_channel} message…"):
                draft_email.draft_outreach(eid, template_name=override, channel=draft_channel)
            st.rerun()

        person = database.get_expert(eid)
        if person.get("draft_template"):
            st.caption(f"Template used: **{person['draft_template']}**")
        current = person.get("email_draft") or ""
        edited = st.text_area("Draft (edit freely)", value=current, height=240)

        s1, s2 = st.columns(2)
        with s1:
            if st.button("💾 Save edits", use_container_width=True):
                database.save_draft(eid, edited)
                st.success("Saved.")
        with s2:
            if st.button("✅ Mark as sent", use_container_width=True,
                         help="Logs this email (subject + template) and sets status to Contacted."):
                database.save_draft(eid, edited)
                subject = parse_subject(edited)
                database.log_sent_email(eid, person.get("draft_template", ""), subject, edited)
                database.advance_status(eid, "Contacted")
                if not person.get("outreach_channel"):
                    database.update_fields(eid, outreach_channel="Email")
                st.success(f"Logged & marked Contacted — subject: “{subject}”")
                st.rerun()

        # ---- Save this edited draft as a reusable template ---- #
        st.caption("Like how this turned out? Save it as a reusable template.")
        t1, t2 = st.columns([3, 1])
        with t1:
            tmpl_name = st.text_input(
                "Template name", value=f"Draft from {person.get('name', 'lead')}",
                key=f"tmplname_{eid}", label_visibility="collapsed")
        with t2:
            if st.button("💾 Save as template", use_container_width=True):
                subj, body = split_draft(edited)
                templates = store.get_templates()
                templates.append({"name": (tmpl_name or "Untitled").strip(),
                                  "subject": subj, "body": body})
                store.set_templates(templates)
                st.success(f"Saved template “{tmpl_name}”. Find it in the ✉️ Templates tab.")
    else:
        st.info("No leads match these filters yet. Use the sidebar to find some.")

# ---- Templates ------------------------------------------------------------ #
with tab_templates:
    st.subheader("Email templates")
    st.caption(
        "Each template has its own **Subject** and **Body** box — just write naturally, "
        "no formatting needed. When you flag someone, the AI picks the most relevant "
        "template and adapts it. Use placeholders like [Name], [Company], [Topic], "
        "[Your Name] and the AI fills them in. Click **Save templates** when done."
    )

    # Working copy with stable ids so editing/adding/deleting never scrambles fields.
    if "tmpl_work" not in st.session_state:
        st.session_state.tmpl_seq = 0
        st.session_state.tmpl_work = []
        for t in store.get_templates():
            st.session_state.tmpl_work.append({**t, "_id": st.session_state.tmpl_seq})
            st.session_state.tmpl_seq += 1

    work = st.session_state.tmpl_work
    if not work:
        st.info("No templates yet — click ➕ Add template below.")

    delete_id = None
    for t in work:
        tid = t["_id"]
        with st.container(border=True):
            h1, h2 = st.columns([5, 1])
            with h1:
                t["name"] = st.text_input("Template name", value=t.get("name", ""), key=f"tn_{tid}")
            with h2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("🗑 Delete", key=f"tdel_{tid}", use_container_width=True):
                    delete_id = tid
            t["subject"] = st.text_input("Subject", value=t.get("subject", ""), key=f"ts_{tid}")
            t["body"] = st.text_area("Body", value=t.get("body", ""), height=180, key=f"tb_{tid}")

    if delete_id is not None:
        st.session_state.tmpl_work = [t for t in work if t["_id"] != delete_id]
        st.rerun()

    b1, b2 = st.columns(2)
    with b1:
        if st.button("➕ Add template", use_container_width=True):
            st.session_state.tmpl_work.append(
                {"name": "New template", "subject": "", "body": "",
                 "_id": st.session_state.tmpl_seq})
            st.session_state.tmpl_seq += 1
            st.rerun()
    with b2:
        if st.button("💾 Save templates", type="primary", use_container_width=True):
            saved = store.set_templates(
                [{"name": t["name"], "subject": t["subject"], "body": t["body"]} for t in work])
            st.success(f"Saved {len(saved)} template(s).")

# ---- A/B testing ---------------------------------------------------------- #
with tab_ab:
    st.subheader("A/B testing — what gets replies")
    st.caption(
        "Reply rates for the emails you've logged (via ✅ Mark as sent, or the form "
        "below). An email counts as a reply once you move that lead to Replied or "
        "Meeting scheduled."
    )

    by_template, by_subject = database.ab_stats()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**By template**")
        if by_template:
            st.dataframe(
                pd.DataFrame(by_template).rename(columns={"key": "template"}),
                use_container_width=True, hide_index=True)
        else:
            st.caption("No emails logged yet.")
    with c2:
        st.markdown("**By subject line**")
        if by_subject:
            st.dataframe(
                pd.DataFrame(by_subject).rename(columns={"key": "subject"}),
                use_container_width=True, hide_index=True)
        else:
            st.caption("No emails logged yet.")

    st.divider()
    st.markdown("**Sent-email log**")
    sent = database.get_sent_emails()
    if sent:
        log_df = pd.DataFrame(sent)[
            ["sent_at", "lead_name", "template_name", "subject", "replied"]
        ]
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Nothing logged yet.")

    st.divider()
    with st.expander("➕ Log an email I sent outside the app"):
        people = database.get_experts(order_by="name ASC")
        if not people:
            st.caption("Add some leads first.")
        else:
            opts = {f"{p['name']} ({p.get('company','')})": p["id"] for p in people}
            with st.form("manual_log", clear_on_submit=True):
                who = st.selectbox("Lead", list(opts.keys()))
                tmpl_names = [t["name"] for t in store.get_templates() if t.get("name")]
                ml_tmpl = st.selectbox("Template used", ["(none)"] + tmpl_names)
                ml_subject = st.text_input("Subject line")
                ml_body = st.text_area("Email body (optional)", height=120)
                ml_date = st.date_input("Date sent")
                if st.form_submit_button("Log it", type="primary"):
                    eid2 = opts[who]
                    database.log_sent_email(
                        eid2, "" if ml_tmpl == "(none)" else ml_tmpl,
                        ml_subject, ml_body, sent_at=str(ml_date))
                    database.advance_status(eid2, "Contacted")
                    st.success("Logged.")
                    st.rerun()

# ---- Settings: automation + research questions + topics + about me -------- #
with tab_settings:
    st.subheader("Automation")
    st.caption(
        "The tool runs itself every day at **5:00 AM Eastern**. Each run archives "
        "untouched leads from earlier days (so the same people aren't surfaced "
        "twice), then finds & enriches new ones. **Flagged leads and anyone you've "
        "moved forward are never archived.**"
    )
    auto_on = st.toggle("Run automatically every day (5 AM ET)",
                        value=store.get_auto_enabled(),
                        help="Turn off to pause the daily run without removing the schedule.")
    if auto_on != store.get_auto_enabled():
        store.set_auto_enabled(auto_on)
        st.toast("Auto-run " + ("enabled." if auto_on else "paused."))
    arch_hours = st.number_input(
        "Archive untouched leads after (hours)", min_value=1, max_value=720,
        value=store.get_archive_hours(), step=1,
        help="Leads you haven't flagged or acted on roll off into the archive after this long.")
    if int(arch_hours) != store.get_archive_hours():
        store.set_archive_hours(int(arch_hours))
        st.toast(f"Archive window set to {int(arch_hours)} hours.")

    st.divider()
    st.subheader("⭐ Biggest questions")
    st.caption(
        f"Your **top {config.MAX_BIGGEST_QUESTIONS} questions** — these get the "
        "heaviest discovery weight. For each, write the question, then use the notes "
        "box to think out loud about **who** you want to talk to, **what level** "
        "(seniority/role), and the **approaches/considerations** you want to explore. "
        "The agent uses those notes to shape exactly who it looks for."
    )
    existing_bq = store.get_biggest_questions()
    bq_inputs = []
    for i in range(config.MAX_BIGGEST_QUESTIONS):
        cur = existing_bq[i] if i < len(existing_bq) else {"question": "", "notes": ""}
        with st.container(border=True):
            q_text = st.text_input(
                f"Biggest question #{i + 1}", value=cur.get("question", ""),
                key=f"bq_q_{i}", placeholder="e.g. What would unlock retail access to private markets?")
            q_notes = st.text_area(
                "Who / level / approaches / considerations",
                value=cur.get("notes", ""), key=f"bq_n_{i}", height=120,
                placeholder="Free-flowing thoughts: the kind of person, their seniority, "
                            "multiple angles you want to explore, what a great conversation covers…")
            bq_inputs.append({"question": q_text, "notes": q_notes})
    if st.button("💾 Save biggest questions", type="primary"):
        saved = store.set_biggest_questions(bq_inputs)
        st.success(f"Saved {len(saved)} biggest question(s).")
        st.rerun()

    st.divider()
    st.subheader("Research questions")
    st.caption(
        "These drive discovery. Higher **priority** = more of the daily lead "
        "budget and more searches. Add rows, edit text, change priorities, or "
        "delete rows — then click Save. Changes apply on your next run."
    )

    questions = store.get_research_questions()
    q_df = pd.DataFrame(questions or [{"question": "", "priority": 1}])
    edited_q = st.data_editor(
        q_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "question": st.column_config.TextColumn("Research question", width="large"),
            "priority": st.column_config.NumberColumn("Priority", min_value=1, step=1, width="small"),
        },
        key="q_editor",
    )

    if st.button("💾 Save research questions", type="primary"):
        saved = store.set_research_questions(edited_q.to_dict("records"))
        st.success(f"Saved {len(saved)} question(s).")
        st.rerun()

    alloc = discover.allocate_budget(config.DAILY_LEAD_CAP)
    if alloc:
        st.markdown(f"**How today's {config.DAILY_LEAD_CAP}-lead budget splits right now:**")
        preview = pd.DataFrame(
            [{"Research question": q["question"], "Priority": q.get("priority", 1),
              "Leads/day": c} for q, c in alloc]
        )
        st.dataframe(preview, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Topics")
    st.caption("Broad areas used to tag people. One per line.")
    topics_text = st.text_area(
        "Topics", value="\n".join(store.get_topics()), height=200, label_visibility="collapsed"
    )
    if st.button("💾 Save topics"):
        saved = store.set_topics(topics_text.splitlines())
        st.success(f"Saved {len(saved)} topic(s).")
        st.rerun()

    st.divider()
    st.subheader("🔗 Connections")
    st.caption(
        "Your warm-intro **bridge list** — a first filter on top of the research "
        "questions. The agent prefers people who match an active connection AND can "
        "still help answer your questions.\n\n"
        "• **Direct** = the person *shares an attribute* (e.g. attended MIT, ex-Stripe).\n"
        "• **Indirect** = the person is *connected to a company/person* (e.g. Sequoia). "
        "For these the agent goes **down** the hierarchy — it looks for junior, "
        "accessible people (analysts, associates, recent hires, portfolio founders), "
        "**not** partners or C-suite (they're the goal, not the bridge).\n\n"
        "Toggle **active** to use a connection; the **callout** is the label shown on "
        "matching leads. Edit rows, then Save. Changes apply on your next run."
    )

    conns = store.get_connections()
    c_df = pd.DataFrame(
        conns or [{"name": "", "kind": "direct", "active": True, "callout": ""}]
    )[["name", "kind", "active", "callout"]]
    edited_c = st.data_editor(
        c_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn(
                "Anchor (school / company / person)", width="medium"),
            "kind": st.column_config.SelectboxColumn(
                "Kind", options=config.CONNECTION_KINDS, width="small"),
            "active": st.column_config.CheckboxColumn("Active", width="small"),
            "callout": st.column_config.TextColumn(
                "Call-out (label on leads)", width="medium"),
        },
        key="conn_editor",
    )
    if st.button("💾 Save connections", type="primary"):
        saved = store.set_connections(edited_c.to_dict("records"))
        st.success(f"Saved {len(saved)} connection(s).")
        st.rerun()

    st.divider()
    st.subheader("✍️ Message best practices")
    st.caption(
        "A short **best-practice guide per channel** — your reusable \"skill\" for each "
        "medium. The AI follows the matching guide when drafting, so a LinkedIn DM reads "
        "differently from an email or an X DM. Edit and Save; applies to the next draft."
    )
    guides = store.get_channel_guides()
    new_guides = {}
    for ch in config.MESSAGE_CHANNELS:
        new_guides[ch] = st.text_area(
            f"{channel_emoji(ch)} {ch}", value=guides.get(ch, ""), height=140,
            key=f"guide_{ch}")
    if st.button("💾 Save message best practices", type="primary"):
        store.set_channel_guides(new_guides)
        st.success("Saved best-practice guides.")
        st.rerun()

    st.divider()
    st.subheader("About me")
    st.caption(
        "Used to personalize your outreach emails. **Background** tells the AI what "
        "to say about you; **writing samples** teach it to match your voice."
    )
    about = store.get_about()
    bio = st.text_area("Background / bio", value=about.get("bio", ""), height=160)
    voice = st.text_area(
        "Writing samples (paste a few past emails you've written)",
        value=about.get("voice_samples", ""), height=200,
    )
    if st.button("💾 Save About me"):
        store.set_about({"bio": bio, "voice_samples": voice})
        st.success("Saved.")
