"""
draft_email.py  —  write a personalized outreach email draft.

Uses your "About me" (bio + writing-voice samples) and your saved templates.
By default the AI picks the single most relevant template and adapts it, and we
RECORD which template it chose (so the A/B testing view can compare them). You
can also force a specific template by passing template_name.

Returns (draft_text, chosen_template_name). Draft only — never auto-sent.
"""

import config
import database
import store
from clients import ask_json, ask_text


def _base_system(about, with_voice, channel="Email"):
    is_dm = channel in ("LinkedIn DM", "X DM")
    if is_dm:
        system = (
            f"You write concise, warm cold-outreach direct messages on {channel} for "
            "market research. No marketing fluff, no hard sell. Reference who the person "
            "is and why their specific expertise is valuable, and make a small, "
            "low-pressure ask for a short 20-30 minute conversation. This is a DM: "
            "do NOT include a subject line. Output ONLY the message text."
        )
    else:
        system = (
            "You write concise, warm, professional cold-outreach emails for market "
            "research. Keep it under 150 words. No marketing fluff, no hard sell. "
            "Reference who the person is and why their specific expertise is valuable, "
            "and make a small, low-pressure ask for a short 20-30 minute conversation. "
            "Output the email as a subject line then the body."
        )
    guide = store.get_channel_guide(channel)
    if guide:
        system += f"\n\nBEST PRACTICES FOR {channel.upper()} (follow these):\n{guide}"
    if with_voice and about.get("voice_samples"):
        system += (
            " Match the sender's personal writing voice shown in the WRITING "
            "SAMPLES — mirror their tone, rhythm, and level of formality."
        )
    return system


def _context_blocks(expert, about, templates_text=None):
    parts = [f"ABOUT ME (the sender):\n{about.get('bio', '')}"]
    if about.get("voice_samples"):
        parts.append(f"WRITING SAMPLES (match this voice):\n{about['voice_samples']}")
    if templates_text:
        parts.append(templates_text)
    parts.append(
        "PERSON I'M EMAILING:\n"
        f"Name: {expert.get('name')}\n"
        f"Title: {expert.get('title')}\n"
        f"Company: {expert.get('company')}\n"
        f"Summary: {expert.get('summary')}\n"
        f"Topics they can help with: {expert.get('topics')}\n"
        f"Research questions they can help answer: {expert.get('answers_questions')}\n"
    )
    return parts


def draft_outreach(expert_id, template_name=None, channel=None, save=True):
    """
    Draft an outreach message. Returns (draft, chosen_template_name).
    If template_name is given, that template is used; otherwise the AI picks.
    `channel` is one of config.MESSAGE_CHANNELS (Email / LinkedIn DM / X DM); it
    reshapes the draft (DMs are shorter and have no subject line) and pulls in that
    channel's best-practice guidance. Defaults to the lead's saved channel, else Email.
    """
    expert = database.get_expert(expert_id)
    if not expert:
        raise ValueError(f"No expert with id {expert_id}")

    channel = channel or expert.get("message_channel") or "Email"
    if channel not in config.MESSAGE_CHANNELS:
        channel = "Email"
    is_dm = channel in ("LinkedIn DM", "X DM")
    word = "message" if is_dm else "email"

    about = store.get_about()
    templates = store.get_templates()
    names = list(dict.fromkeys(t.get("name", "") for t in templates if t.get("name")))
    forced = next((t for t in templates if t.get("name") == template_name), None)

    if forced:
        # Use the chosen template specifically.
        tail = (
            f" Adapt the TEMPLATE below to this person and to {channel}, keeping its "
            "voice. Fill any [placeholders]; leave a signature placeholder like "
            f"[Your Name] as-is. Output ONLY the {word}."
        )
        if is_dm:
            tail += " Since this is a DM, drop the template's subject line entirely."
        system = _base_system(about, with_voice=True, channel=channel) + tail
        tmpl_text = (f"TEMPLATE — {forced.get('name')}:\n"
                     f"Subject: {forced.get('subject', '')}\n{forced.get('body', '')}")
        user = "\n\n".join(_context_blocks(expert, about, tmpl_text) + [f"Write the outreach {word}."])
        draft = ask_text(config.DRAFTING_MODEL, system, user)
        chosen = forced.get("name", "")

    elif templates:
        # Let the AI pick the best template AND tell us which one.
        tail = (
            " You are given outreach TEMPLATES. Choose the SINGLE most relevant one "
            f"for this person and adapt it to {channel} (keep its voice; fill "
            "[placeholders], leaving [Your Name] as-is). Return the chosen "
            f"template's name and the finished {word}."
        )
        if is_dm:
            tail += " Since this is a DM, drop the template's subject line entirely."
        system = _base_system(about, with_voice=True, channel=channel) + tail
        tmpl_text = "MY OUTREACH TEMPLATES (pick the most relevant and adapt it):\n" + "\n\n".join(
            f"TEMPLATE — {t.get('name', 'Untitled')}:\nSubject: {t.get('subject', '')}\n{t.get('body', '')}"
            for t in templates
        )
        user = "\n\n".join(_context_blocks(expert, about, tmpl_text) + [f"Write the outreach {word}."])
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "template_name": {"type": "string", "enum": names + [""]},
                "email": {"type": "string"},
            },
            "required": ["template_name", "email"],
        }
        data = ask_json(config.DRAFTING_MODEL, system, user, schema)
        draft = data.get("email", "")
        chosen = data.get("template_name", "")

    else:
        # No templates saved — just write a fresh message.
        system = _base_system(about, with_voice=True, channel=channel) + f" Output ONLY the {word}."
        user = "\n\n".join(_context_blocks(expert, about) + [f"Write the outreach {word}."])
        draft = ask_text(config.DRAFTING_MODEL, system, user)
        chosen = ""

    if save:
        database.update_fields(expert_id, email_draft=draft, draft_template=chosen,
                               message_channel=channel)
    return draft, chosen


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python draft_email.py <expert_id>")
    else:
        text, tmpl = draft_outreach(int(sys.argv[1]))
        print(f"[template: {tmpl or '(none)'}]\n\n{text}")
