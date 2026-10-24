"""
Optional AI layer (Google Gemini). Everything here has a non-AI fallback, so the dashboard
works fully offline and nothing breaks if the network or API is down during a demo.

Privacy: only anonymised facts (department, year, computed numbers, reasons) are sent.
Names, roll numbers and emails never leave the server.

Set the key in either place:
  * environment variable GEMINI_API_KEY (and optionally GEMINI_MODEL), or
  * the "AI assistant" box in the dashboard sidebar (kept only for that browser session).
"""
import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(Exception):
    pass


def call_gemini(prompt, api_key, model=DEFAULT_MODEL, want_json=False, timeout=25):
    if not api_key:
        raise AIError("No API key")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}}
    if want_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(ENDPOINT.format(model=model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise AIError(f"Gemini returned HTTP {e.code}: {detail}")
    except Exception as e:  # network down, timeout, proxy
        raise AIError(f"Could not reach Gemini: {e}")
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise AIError(f"Unexpected response: {str(data)[:300]}")
    if want_json:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise AIError("AI did not return JSON")
        return json.loads(m.group(0))
    return text.strip()


# ---------------------------------------------------------------- mentor brief
def mentor_brief_prompt(facts):
    return f"""You are helping a college faculty mentor prepare for a one-to-one conversation with a student.
Write a short, kind, practical brief in plain English (max 120 words) with exactly these four parts:
1. What's happening (one sentence, factual, using the numbers below)
2. Likely reasons to explore (two short bullets; phrase as questions to ask, never as conclusions or diagnoses)
3. How to open the conversation (one warm sentence the mentor could actually say)
4. Agreed next step (one concrete action with a date in the next 7 days)
Do not invent facts beyond what is given. Do not mention any model, score formula or probability jargon.

Student facts (anonymised):
{json.dumps(facts, indent=1)}"""


def template_mentor_brief(f):
    reasons = f.get("risk_reasons") or ["no single strong warning sign"]
    plan = f.get("path_to_green") or []
    opener = ("I noticed things have been a bit harder these last few weeks. How are you doing, honestly?"
              if f.get("declining") else "I wanted to check in on how the semester is going for you.")
    lines = [
        f"**What's happening:** Success Score {f['success_score']:.0f}/100 ({f['band']}); academic risk {f['academic_risk']}. "
        f"Main signals: {'; '.join(reasons[:3])}.",
        "**Reasons to explore:**",
        "- Has anything changed recently (health, family, travel, money, workload)?",
        "- Which subject or task feels hardest right now, and what would help?",
        f"**How to open:** \"{opener}\"",
        f"**Agreed next step:** {plan[0] if plan else 'Agree one small, specific goal for this week'}; follow up in 7 days.",
    ]
    return "\n\n".join(lines)


# ---------------------------------------------------------------- weekly briefing
def weekly_brief_prompt(stats):
    return f"""You are writing the Monday briefing for a college Head of Department.
Using ONLY the numbers below, write 4 short bullet points (max 90 words total):
what changed this week, who needs attention first, the most useful action, and one positive.
Plain English, no jargon, no invented numbers.

Data:
{json.dumps(stats, indent=1)}"""


def template_weekly_brief(s):
    return "\n".join([
        f"- **{s['high_risk']} students are at high academic risk** ({s['newly_flagged']} moved into high risk this week).",
        f"- **Start with the {s['critical']} students in 'Critical: Act This Week'**, then the {s['silent']} Silent Strugglers "
        f"whose marks still look fine.",
        f"- **{s['shortage']} students are heading below 75% attendance**; {s['recoverable']} can still recover if they attend "
        f"almost every remaining class, so this week matters.",
        f"- **Positive:** {s['thriving']} students are Thriving and {s['stars']} are Placement-Ready Stars who could peer-mentor.",
    ])
