"""
"Ask your campus data": turn a plain-English question into a safe, structured filter.
The AI (if connected) only *translates* the question into a filter spec; the numbers are always
computed by our own code, so answers can't be hallucinated. Without AI, a rule-based parser
handles the common phrasings.
"""
import json
import re

import pandas as pd

FIELDS = {
    "dept": "department: CSE, IT, ECE, MECH", "year": "year of study: 1 to 4", "section": "A/B/C",
    "residence": "Hostel or Day Scholar", "gender": "F or M", "first_graduate": "Yes/No", "mentor": "mentor name",
    "success_score": "0-100", "academic": "Academic Health 0-100", "engagement": "Engagement 0-100",
    "placement": "Placement Readiness 0-100", "band": "At Risk / Needs Attention / On Track / Thriving",
    "att_pct": "attendance % so far", "projected_attendance": "projected end-of-semester attendance %",
    "cgpa": "CGPA", "backlogs": "standing arrears", "cia1_pct": "CIA-1 average %", "lms_avg": "LMS logins per week",
    "lms_change": "change in LMS activity, -1 to 1 (negative = falling)", "asg_rate": "assignment completion 0-1",
    "best_aptitude": "aptitude 0-100", "best_coding": "coding 0-100", "mock_interviews": "count",
    "certifications": "count", "activities": "events/clubs count", "acad_risk": "High/Medium/Low",
    "placement_risk": "High/Medium/Low/Pre-placement", "segment": "segment name", "acad_prob": "risk 0-1",
    "newly_flagged": "true/false", "attendance_shortage": "true/false",
}
OPS = {"==", "!=", "<", "<=", ">", ">=", "in", "contains"}


def ai_prompt(question, segments):
    return f"""Translate the question into a JSON filter over a table of college students.
Fields: {json.dumps(FIELDS)}
Segment names: {segments}
Return ONLY JSON like:
{{"filters":[{{"field":"dept","op":"in","value":["CSE"]}},{{"field":"att_pct","op":"<","value":75}}],
 "sort":{{"field":"acad_prob","desc":true}},"limit":50,"explanation":"short restatement of what is shown"}}
Allowed ops: {sorted(OPS)}. Use only listed fields. Percent fields are 0-100 except asg_rate (0-1) and acad_prob (0-1).
"Falling/declining activity" means lms_change <= -0.25. "At risk" means acad_risk in [High, Medium].
Question: {question}"""


NUM_FIELDS = [
    (r"projected attendance", "projected_attendance"), (r"attendance", "att_pct"), (r"cgpa|gpa", "cgpa"),
    (r"success score|score", "success_score"), (r"academic health", "academic"), (r"engagement", "engagement"),
    (r"placement readiness", "placement"), (r"arrears?|backlogs?", "backlogs"), (r"cia|internal marks?|marks", "cia1_pct"),
    (r"lms logins?|logins?", "lms_avg"), (r"coding", "best_coding"), (r"aptitude", "best_aptitude"),
    (r"mock interviews?|mocks?", "mock_interviews"), (r"certifications?", "certifications"),
]
CMP = [(r"below|under|less than|lower than|<", "<"), (r"at most|<=|no more than", "<="),
       (r"above|over|more than|greater than|higher than|>", ">"), (r"at least|>=|min(?:imum)?", ">=")]


def rule_parse(q, segments, mentors):
    text = q.lower()
    F, expl = [], []
    pats = [("CSE", r"\bcse\b|computer science"), ("ECE", r"\bece\b|electronics"),
            ("MECH", r"\bmech\b|mechanical"), ("IT", r"\bIT\b|information tech")]
    from . import config as C
    pats += [(d, r"\b" + re.escape(d.lower()) + r"\b") for d in C.DEPTS if d not in dict(pats)]
    depts = [d for d, pat in pats if re.search(pat, q if d == "IT" else text)]
    if depts:
        F.append(dict(field="dept", op="in", value=depts))
        expl.append("dept " + "/".join(depts))
    years = []
    for y, pat in [(1, r"\b(1st|first)\b|year 1"), (2, r"\b(2nd|second|ii)\b|year 2"), (3, r"\b(3rd|third|iii)\b|year 3"),
                   (4, r"\b(4th|fourth|final|iv)\b|year 4")]:
        if re.search(pat, text):
            years.append(y)
    if years:
        F.append(dict(field="year", op="in", value=years))
        expl.append("year " + "/".join(map(str, years)))
    for pat, field in NUM_FIELDS:
        for cpat, op in CMP:
            m = re.search(rf"(?:{pat})\s*(?:is\s*|of\s*)?(?:{cpat})\s*(\d+(?:\.\d+)?)", text)
            if m:
                F.append(dict(field=field, op=op, value=float(m.group(1))))
                expl.append(f"{field} {op} {m.group(1)}")
                text = text.replace(m.group(0), " ")
                break
    if re.search(r"high[- ]risk|high academic risk", text):
        F.append(dict(field="acad_risk", op="in", value=["High"])); expl.append("high academic risk")
    elif re.search(r"at[- ]risk|medium risk|risky", text):
        F.append(dict(field="acad_risk", op="in", value=["High", "Medium"])); expl.append("academic risk High/Medium")
    if "placement risk" in text:
        F.append(dict(field="placement_risk", op="in", value=["High", "Medium"])); expl.append("placement risk High/Medium")
    if re.search(r"declin|falling|dropp|disengag", text):
        F.append(dict(field="lms_change", op="<=", value=-0.25)); expl.append("LMS activity falling")
    if re.search(r"shortage|detain|below 75", text) and not any(f["field"] == "att_pct" for f in F):
        F.append(dict(field="attendance_shortage", op="==", value=True)); expl.append("heading for attendance shortage")
    if re.search(r"new(ly)?|this week", text):
        F.append(dict(field="newly_flagged", op="==", value=True)); expl.append("newly high-risk this week")
    if re.search(r"no mock|zero mock|without mock", text):
        F.append(dict(field="mock_interviews", op="==", value=0)); expl.append("no mock interviews")
    if "hostel" in text:
        F.append(dict(field="residence", op="==", value="Hostel")); expl.append("hostellers")
    if re.search(r"day scholar", text):
        F.append(dict(field="residence", op="==", value="Day Scholar")); expl.append("day scholars")
    if re.search(r"\b(girls|female|women)\b", text):
        F.append(dict(field="gender", op="==", value="F")); expl.append("female")
    if re.search(r"\b(boys|male|men)\b", text):
        F.append(dict(field="gender", op="==", value="M")); expl.append("male")
    if "first graduate" in text or "first-graduate" in text:
        F.append(dict(field="first_graduate", op="==", value="Yes")); expl.append("first-graduate")
    for s in segments:
        key = s.lower().split(":")[0].split(",")[0]
        if key in text:
            F.append(dict(field="segment", op="==", value=s)); expl.append(f"segment '{s}'")
    for m_ in mentors:
        surname = m_.split()[-1].lower()
        if surname in text and len(surname) > 3:
            F.append(dict(field="mentor", op="==", value=m_)); expl.append(f"mentor {m_}")
    sort = dict(field="acad_prob", desc=True)
    if re.search(r"lowest|worst|bottom", text):
        sort = dict(field="success_score", desc=False)
    elif re.search(r"best|top performers|highest score", text):
        sort = dict(field="success_score", desc=True)
    lim = re.search(r"\b(?:top|first|show)\s+(\d+)", text)
    return dict(filters=F, sort=sort, limit=int(lim.group(1)) if lim else 200,
                explanation=", ".join(expl) if expl else "all students (no filter recognised)")


def apply(df, spec):
    out = df.copy()
    applied = []
    for f in spec.get("filters", []):
        field, op, val = f.get("field"), f.get("op"), f.get("value")
        if field not in out.columns or op not in OPS:
            continue
        col = out[field]
        try:
            if op == "in":
                vals = val if isinstance(val, list) else [val]
                mask = col.astype(str).str.lower().isin([str(v).lower() for v in vals])
            elif op == "contains":
                mask = col.astype(str).str.contains(str(val), case=False, regex=False)
            elif op in ("==", "!="):
                if isinstance(val, bool) or str(val).lower() in ("true", "false"):
                    v = val if isinstance(val, bool) else str(val).lower() == "true"
                    mask = col.astype(bool) == v
                elif pd.api.types.is_numeric_dtype(col):
                    mask = col == float(val)
                else:
                    mask = col.astype(str).str.lower() == str(val).lower()
                mask = mask if op == "==" else ~mask
            else:
                v = float(val)
                mask = {"<": col < v, "<=": col <= v, ">": col > v, ">=": col >= v}[op]
            out = out[mask]
            applied.append(f)
        except (ValueError, TypeError):
            continue
    s = spec.get("sort") or {}
    if s.get("field") in out.columns:
        out = out.sort_values(s["field"], ascending=not s.get("desc", True))
    return out.head(int(spec.get("limit") or 200)), applied
