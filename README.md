# Networking Agent

A simple, local tool that finds industry experts for your fintech market research,
gathers their public contact info, drafts outreach emails, and tracks everyone in a
small database — all from a point-and-click web app on your own computer.

It runs **once a day automatically**, finding up to **50 new people per day** spread
across your prioritized research questions, different geographies, and company sizes.

> **About LinkedIn:** This tool does **not** scrape LinkedIn or auto-connect/auto-message
> (that gets accounts banned). It finds people via web search, captures their public
> LinkedIn URL, and lets *you* reach out manually. Email is best-effort — when no public
> email is found, you'll have the LinkedIn link instead.

---

## What's in this folder

| File | What it's for |
|---|---|
| **`config.py`** | **The one file you edit** — your topics, prioritized research questions, daily cap, regions, and a short "about me" for emails. |
| `.env` | Your two secret API keys (you create this — see setup). |
| `run.bat` | Double-click to open the app. |
| `daily_run.bat` | What the daily scheduled task runs. |
| (everything else) | The program itself — you don't need to touch it. |

---

## One-time setup (about 15 minutes)

### 1. Install Python
- Open **Microsoft Store** → search **Python 3.12** → Install.
  *(Or download from [python.org](https://www.python.org/downloads/) and tick
  "Add Python to PATH" during install.)*

### 2. Get your two free API keys
- **Tavily** (web search): sign up at [tavily.com](https://tavily.com) → copy your API key (starts with `tvly-`).
- **Claude** (the AI): sign up at [console.anthropic.com](https://console.anthropic.com) →
  create an API key (starts with `sk-ant-`). You'll add a small amount of billing credit;
  daily usage is typically pennies to a couple of dollars.

### 3. Create your `.env` file
- In this folder, make a copy of **`.env.example`** and rename the copy to **`.env`**.
- Open `.env` in Notepad and paste your two keys in. Save.

### 4. Install the program's building blocks
- Open **Command Prompt**, then run (adjust the path if needed):
  ```
  cd "C:\Users\John_\OneDrive\Networking Agent 2"
  pip install -r requirements.txt
  ```

### 5. Personalize and prioritize
- **Research questions & topics** are edited **inside the app** — open it (step below),
  go to the **⚙️ Research questions** tab, and add/edit/delete your questions and their
  priorities (higher priority = more leads + more search effort). It also shows you how
  the daily 50-lead budget splits across them. Your edits save automatically to
  `settings.json` and take effect on the next run.
- A few things still live in **`config.py`** (open in Notepad if you want to change them):
  - `SENDER_PROFILE` — a few honest lines about you and your startup (used to
    personalize email drafts).
  - Optionally `TARGET_REGIONS`, `DAILY_LEAD_CAP`, etc.

That's it. You're ready.

---

## Everyday use

1. **Open the app:** double-click **`run.bat`**. It opens in your browser.
2. **Find leads:** in the left sidebar, set "Max new leads this run" (try **5** the first
   time), click **🔍 Find new leads**, then **📝 Enrich new leads**.
3. **Quick review (the fast way):** the **⚡ Quick review** tab shows each reviewed person as a
   card — photo, name, title, what they can help answer, and the 10 questions. **🚩 Flag** the
   ones you want (a personalized email **auto-drafts** instantly using your best-fit template),
   or **👎 Skip** to remove them from the queue. Tick **🎓 MIT alumni only** to focus on MIT /
   MIT Sloan grads.
4. **Browse (the deep way):** the **👥 Browse & manage** tab is a full filterable table
   (US market, size, status, topic, MIT-only, etc.) with each person's full detail, draft, and
   status control.
5. **Reach out:** flagged people already have a draft — open them, edit it, and send it yourself.
6. **Track:** update each person's **Status** (Found → Reviewed → Contacted → Replied →
   Meeting scheduled, etc.). The **📊 Dashboard** tab shows your pipeline plus a US-market and
   company-size breakdown.

**The tabs:** ⚡ Quick review · 📊 Dashboard · 👥 Browse & manage · ✉️ Templates (your email
styles) · ⚙️ Settings (research questions, topics, and your "About me").

> **Templates & About me:** In **✉️ Templates**, save email styles you like — when you flag
> someone, the AI picks the most relevant one and adapts it. In **⚙️ Settings → About me**, add
> your background and paste a few past emails so drafts match *your* voice.

> **Geography:** Leads are spread across **US markets** — Northeast, Mid-Atlantic, Southeast,
> Midwest, Southwest, West. (Edit `TARGET_REGIONS` in `config.py` to change these.)

> **Photos:** Profile photos are best-effort from web search — many people won't have one (you'll
> see an initials avatar), and occasionally one may be off. Treat them as a hint.

---

## Runs automatically every day at 5 AM ET

A Windows scheduled task named **"Networking Agent Daily"** is already set up to run at
**5:00 AM Eastern** every day. Each morning it:

1. **Archives untouched leads** from earlier days — anyone you didn't flag or act on (still in
   Found/Reviewed) rolls off into the archive after the window (default **24 hours**). This keeps your
   review queue fresh, and archived people are **remembered so they're never found again**.
2. **Finds and enriches** up to 50 new leads.
3. Appends a summary line to **`daily_log.txt`**.

**Your flagged leads — and anyone you've moved to Contacted/Replied/Meeting — are never archived.**

**Control it from the app (⚙️ Settings → Automation):**
- **Pause/resume** the daily run with a toggle (no need to touch Windows).
- **Change the archive window** (how many hours before untouched leads roll off).

Notes:
- Your PC must be **on** at 5 AM; if it's off/asleep, Windows runs it at the next opportunity.
- View what rolled off via **Browse & manage → 🗄 Show archived**.
- Re-create the schedule (if ever needed):
  ```
  schtasks /create /tn "Networking Agent Daily" /tr "\"C:\Users\John_\OneDrive\Networking Agent 2\daily_run.bat\"" /sc daily /st 05:00 /f
  ```
- Remove it entirely: `schtasks /delete /tn "Networking Agent Daily" /f`

---

## Tracking outreach & A/B testing your emails

Outreach is **manual** (you send from your own inbox), but the tool keeps a tidy log so you can learn
what works:

1. **Draft:** flag a lead (auto-draft) or open them in **Browse & manage**. The AI picks the best-fit
   template, but you can **override** the template from a dropdown and regenerate.
2. **Send it yourself,** then click **✅ Mark as sent** — this logs the subject + template + date and
   moves the lead to **Contacted** in one click.
3. **Log replies:** when someone replies or books time, set their status to **Replied** or **Meeting
   scheduled** (dropdown or quick buttons). That records the email as "got a reply".
4. **Sent outside the app?** Use **📈 A/B testing → Log an email I sent outside the app** to add it.
5. **See what wins:** the **📈 A/B testing** tab shows reply rates **by template** and **by subject
   line**, so you can double down on the phrasing that gets responses.

## Deploying to the web (GitHub + Streamlit Community Cloud)

You can run this on the free [Streamlit Community Cloud](https://share.streamlit.io) so it's
reachable from any browser instead of only your PC.

### 1. Put the code on GitHub
This repo is already git-ready: **your `.env` (secret keys) and `networking.db` are gitignored
and never uploaded.** Push it to a **private** repo (recommended).

### 2. Deploy on Streamlit Community Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → pick this repository and branch (`main`) → set **Main file path** to `app.py`.
3. Open **Advanced settings → Secrets** and paste your two keys in TOML form:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   TAVILY_API_KEY = "tvly-..."
   ```
   Streamlit exposes these as environment variables, which is exactly what the app reads — no
   code change needed.
4. Click **Deploy**.

### Important deployment caveats
- **Storage is ephemeral.** Streamlit Cloud resets the filesystem on every reboot/redeploy, so
  `networking.db` and any in-app changes to `settings.json` **will not persist** there. It's great
  for trying the app online; for durable data, keep running locally (the local DB persists) or
  later move storage to a hosted database (e.g. Postgres/Supabase).
- **The 5 AM daily auto-run does not run on Streamlit Cloud** — that schedule is a local Windows
  task (see above). On the cloud you'd trigger runs manually from the sidebar, or add a separate
  scheduler.

## What it costs / what to expect

- **Tavily:** the free tier is fine for testing. At a steady 50 leads/day you may eventually
  need a low-cost paid tier.
- **Claude:** roughly pennies to a couple of dollars per day at 50 leads. Email drafts cost
  almost nothing (only generated for people you flag).
- **Emails:** only a minority of people have a findable public email — that's normal. For
  everyone else you'll have their LinkedIn URL to reach out manually.

---

## Troubleshooting

- **"Missing TAVILY_API_KEY / ANTHROPIC_API_KEY"** — your `.env` file is missing or still has
  the placeholder text. Re-check step 3.
- **"python is not recognized"** — Python isn't on your PATH. Reinstall and tick
  "Add Python to PATH", or install from the Microsoft Store.
- **Few or no leads found** — try raising the per-run number, or broaden/reword your
  `RESEARCH_QUESTIONS`. Search results vary day to day.
- **Want to start over** — close the app and delete `networking.db`; it rebuilds empty.
