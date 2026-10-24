"""
Data integration: turn 9 messy campus exports into one clean, linked student view.

Every student is identified by the SIS roll number. Each other source is linked
to it with the strongest method available, in this order:
  1. exact ID after normalising (case, spaces, padding, alternate formats)
  2. ID translated from another scheme (12-digit register no -> roll no)
  3. official email -> roll no
  4. identity learned from another source (personal Gmail seen in the LMS)
  5. fuzzy name match restricted to the same department + year
Anything that cannot be linked with confidence goes to a manual-review queue
instead of being guessed.
"""
import re
from difflib import SequenceMatcher

import numpy as np
import pandas as pd

from . import config as C
from .sources import SOURCES, read_source

SOURCES_SIS_COLS = SOURCES["01_sis_student_master.csv"]["cols"]

DEPT_ALIASES = {
    "cse": "CSE", "computerscience": "CSE", "computerscienceengineering": "CSE", "cs": "CSE",
    "it": "IT", "informationtech": "IT", "informationtechnology": "IT",
    "ece": "ECE", "electronicscomm": "ECE", "electronics": "ECE", "ec": "ECE",
    "mech": "MECH", "mechanical": "MECH", "me": "MECH",
}
YEAR_ALIASES = {"i": 1, "1": 1, "1styear": 1, "first": 1,
                "ii": 2, "2": 2, "2ndyear": 2, "second": 2, "iii": 3, "3": 3, "3rdyear": 3, "third": 3,
                "iv": 4, "4": 4, "finalyear": 4, "4thyear": 4, "final": 4}
def univ_code_to_dept():
    return {v[1]: k for k, v in C.DEPTS.items()}


def rollcode_to_dept():
    return {v[2]: k for k, v in C.DEPTS.items()}


# ---------------------------------------------------------------- helpers
def norm_roll(x):
    """'23cs045', ' 23CS045 ', '23CS45', '23-CS-045' -> '23CS045'.
    Any other roll number style (a different college's format) is kept, in capitals, without spaces."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    m = re.match(r"^\s*(\d{2})\s*-?\s*([A-Za-z]{2})\s*-?\s*0*(\d{1,3})\s*$", str(x))
    if m:
        return f"{m.group(1)}{m.group(2).upper()}{int(m.group(3)):03d}"
    s = re.sub(r"\s+", "", str(x)).upper()
    s = re.sub(r"\.0$", "", s)  # numeric roll numbers read from Excel as 1234.0
    return s or None


def register_to_roll(reg):
    """'412723104045' -> '23CS045'. Returns None if the number is damaged."""
    reg = str(reg).strip()
    if not re.fullmatch(r"\d{12}", reg):
        return None
    yy, ucode, serial = reg[4:6], reg[6:9], reg[9:12]
    dept = univ_code_to_dept().get(ucode)
    return f"{yy}{C.DEPTS[dept][2]}{serial}" if dept else None


def norm_dept(label):
    if label is None or (isinstance(label, float) and np.isnan(label)) or not str(label).strip():
        return None
    key = re.sub(r"[^a-z&]", "", str(label).lower()).replace("&", "")
    if key in DEPT_ALIASES:
        return DEPT_ALIASES[key]
    for short, v in C.DEPTS.items():  # the college's own departments
        if key in (re.sub(r"[^a-z]", "", short.lower()), re.sub(r"[^a-z]", "", str(v[0]).lower())):
            return short
    return re.sub(r"\s+", " ", str(label).strip()).upper()


def norm_year(label):
    return YEAR_ALIASES.get(re.sub(r"[^a-z0-9]", "", str(label).lower()), None)


def norm_name(n):
    return " ".join(sorted(re.sub(r"[^a-z ]", " ", str(n).lower()).split()))


def name_keys(first, last):
    """All reasonable spellings of a student's name, normalised."""
    first, last = str(first or ""), str(last or "")
    return {norm_name(f"{first} {last}"), norm_name(f"{first} {last[:1]}")}


class NameIndex:
    """Fuzzy name lookup within a (dept, year) or (dept, batch) group."""

    def __init__(self, sis, group_cols):
        self.groups = {}
        for r in sis.itertuples():
            key = tuple(getattr(r, c) for c in group_cols)
            self.groups.setdefault(key, []).append((r.roll_no, name_keys(r.first, r.last)))

    def match(self, name, group, threshold=0.86):
        cands = self.groups.get(group, [])
        q = norm_name(name)
        scored = []
        for roll, keys in cands:
            best = max(SequenceMatcher(None, q, k).ratio() for k in keys)
            scored.append((best, roll))
        if not scored:
            return None, "no candidates"
        scored.sort(reverse=True)
        best, roll = scored[0]
        if best < threshold:
            return None, "no confident match"
        if len(scored) > 1 and scored[1][0] >= best - 0.02:
            return None, "ambiguous (same name in class)"
        return roll, "fuzzy name"


def to_num(series):
    return pd.to_numeric(series.astype(str).str.replace("%", "", regex=False).str.split("/").str[0].str.strip(),
                         errors="coerce")


# ---------------------------------------------------------------- integration
def integrate():
    raw = C.RAW_DIR
    report = {"sources": [], "review_queue": []}

    def log(source, system, key, rows_in, rows_clean, linked, methods, issues):
        report["sources"].append(dict(source=source, system=system, identifier=key, rows_in=int(rows_in),
                                      rows_after_cleaning=int(rows_clean), linked_rows=int(linked),
                                      link_rate=round(100 * linked / max(rows_clean, 1), 1),
                                      methods={k: int(v) for k, v in methods.items()},
                                      issues={k: int(v) for k, v in issues.items() if v}))

    # 1. SIS master -------------------------------------------------------
    sis, _ = read_source(raw, "01_sis_student_master.csv")
    n_in = len(sis)
    cur_sem_no = sis.pop("Current Semester") if "Current Semester" in sis else None  # simple-template uploads
    sis = sis[SOURCES_SIS_COLS]
    sis.columns = ["roll_no", "name", "gender", "dept", "batch", "year", "section", "residence", "first_graduate",
                   "mentor", "hsc_percent", "email"]
    sis["current_sem_no"] = pd.to_numeric(cur_sem_no, errors="coerce") if cur_sem_no is not None else np.nan
    sis["roll_no"] = sis["roll_no"].map(norm_roll)
    sis["email"] = sis["email"].fillna("").astype(str)
    raw_names = sis["name"].copy()
    sis["name"] = sis["name"].str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    recased = (raw_names != sis["name"]).sum()
    dept_fixed = (sis["dept"] != sis["dept"].map(norm_dept)).sum()
    sis["dept"] = sis["dept"].map(norm_dept)
    dups = sis.duplicated("roll_no").sum()
    sis = sis.drop_duplicates("roll_no").sort_values("roll_no").reset_index(drop=True)
    parts = sis["name"].str.split(" ", n=1)
    sis["first"], sis["last"] = parts.str[0], parts.str[1].fillna("")
    log("Student master", "SIS / ERP", "Roll No", n_in, len(sis), len(sis), {"master record": len(sis)},
        {"duplicate rows removed": dups, "department labels standardised": dept_fixed,
         "names re-cased / trimmed": recased})
    roll_set = set(sis["roll_no"])
    has_email = sis["email"].str.contains("@", na=False)
    email_to_roll = dict(zip(sis.loc[has_email, "email"].str.lower().str.strip(), sis.loc[has_email, "roll_no"]))

    def direct(ids):
        """IDs that already are a known roll number (simple-template uploads use the roll number everywhere)."""
        r = ids.map(norm_roll)
        return r.where(r.isin(roll_set))
    by_dept_year = NameIndex(sis, ["dept", "year"])
    by_dept_batch = NameIndex(sis, ["dept", "batch"])

    # 2. Exam cell ----------------------------------------------------------
    ex, _ = read_source(raw, "02_exam_cell_results.csv", dtype={"register_no": str})
    n_in = len(ex)
    ex["roll_no"] = ex["register_no"].map(register_to_roll)
    method = np.where(ex["roll_no"].notna(), "register no -> roll no", "")
    d_ = direct(ex["register_no"])
    use = ex["roll_no"].isna() & d_.notna()
    ex.loc[use, "roll_no"] = d_[use]
    method = np.where(use, "roll no", method)
    damaged = ex["roll_no"].isna()
    rec_map = {}
    for (reg, name), grp in ex[damaged].groupby(["register_no", "student_name"]):
        digits = re.sub(r"\D", "", reg.split("E")[0])  # mantissa keeps college code + batch
        batch = 2000 + int(digits[4:6]) if len(digits) >= 6 else None
        dept = rollcode_to_dept().get(str(grp["subject_code"].iloc[0])[:2])
        roll, how = by_dept_batch.match(name, (dept, batch))
        rec_map[(reg, name)] = roll
        if roll is None:
            report["review_queue"].append(dict(source="Exam cell", record=f"{name} / {reg}", reason=how))
    rec = ex[damaged].apply(lambda r: rec_map.get((r["register_no"], r["student_name"])), axis=1)
    ex.loc[damaged, "roll_no"] = rec
    method = np.where(damaged & ex["roll_no"].notna(), "damaged ID -> name + dept + batch", method)
    ex["cia1_absent"] = ex["cia1"].astype(str).str.upper().eq("AB")
    ex["cia1"] = pd.to_numeric(ex["cia1"], errors="coerce")
    for c in ("cia2", "end_sem"):
        ex[c] = pd.to_numeric(ex[c], errors="coerce")
    linked = ex["roll_no"].isin(roll_set)
    log("Exam results", "Exam cell", "12-digit Register No", n_in, len(ex), linked.sum(),
        pd.Series(method[linked.values]).value_counts().to_dict(),
        {"register numbers damaged by Excel (scientific notation)": damaged.sum(),
         "'AB' (absent) marks converted": ex["cia1_absent"].sum()})
    ex = ex[linked].copy()

    # 3. Attendance -----------------------------------------------------------
    att, _ = read_source(raw, "03_attendance_weekly.csv")
    n_in = len(att)
    att["roll_no"] = att["RollNo"].map(norm_roll)
    reformatted = (att["RollNo"] != att["roll_no"]).sum()
    impossible = (att["classes_attended"] > att["classes_held"]).sum()
    att["classes_attended"] = att[["classes_attended", "classes_held"]].min(axis=1)
    key = ["roll_no", "semester", "week", "subject_code"]
    dup = att.duplicated(key).sum()
    att = att.drop_duplicates(key)
    sample = C.RAW_DIR.resolve() == C.SAMPLE_RAW_DIR.resolve()
    expected = sum(len(sis) * (C.CURRENT_WEEK if s == C.CURRENT_SEM else C.WEEKS_PER_SEM) * C.SUBJECTS_PER_SEM
                   for s in C.SEMESTERS) if sample else len(att)
    linked = att["roll_no"].isin(roll_set)
    log("Attendance", "Attendance system", "Roll No (inconsistent format)", n_in, len(att), linked.sum(),
        {"normalised roll no": linked.sum()},
        {"roll numbers re-formatted (case / spaces / padding)": reformatted,
         "impossible values fixed (attended > held)": impossible, "duplicate uploads removed": dup,
         "missing subject-weeks (not uploaded)": max(expected - len(att), 0)})
    att = att[linked].drop(columns="RollNo")

    # 4. LMS -------------------------------------------------------------------
    users, has_users = read_source(raw, "04a_lms_users.csv")
    users["roll_no"] = users["login_email"].astype(str).str.lower().str.strip().map(email_to_roll)
    users["method"] = np.where(users["roll_no"].notna(), "official email", "")
    d_ = direct(users["lms_user_id"])
    use = users["roll_no"].isna() & d_.notna()
    users.loc[use, "roll_no"] = d_[use]
    users.loc[use, "method"] = "roll no"
    for i, r in users[users["roll_no"].isna()].iterrows():
        code = str(r["enrolled_courses"]).split(";")[0]
        try:
            dept, year = rollcode_to_dept().get(code[:2]), (int(code[2]) + 1) // 2
        except (ValueError, IndexError):
            dept, year = None, None
        roll, how = by_dept_year.match(r["display_name"], (dept, year))
        users.at[i, "roll_no"] = roll
        users.at[i, "method"] = "personal email -> name + enrolled courses" if roll else ""
        if roll is None:
            report["review_queue"].append(dict(source="LMS", record=f"{r['display_name']} <{r['login_email']}>",
                                               reason=how))
    ok_ = users["roll_no"].notna() & users["login_email"].astype(str).str.contains("@")
    personal_to_roll = dict(zip(users.loc[ok_, "login_email"].astype(str).str.lower().str.strip(),
                                users.loc[ok_, "roll_no"]))
    lms, has_lms = read_source(raw, "04b_lms_weekly_activity.csv")
    n_in = len(lms)
    neg = (lms["minutes"] < 0).sum()
    lms.loc[lms["minutes"] < 0, "minutes"] = np.nan
    dup = lms.duplicated(["lms_user_id", "semester", "week"]).sum()
    lms = lms.drop_duplicates(["lms_user_id", "semester", "week"])
    lms = lms.merge(users[["lms_user_id", "roll_no", "method"]], on="lms_user_id", how="left")
    linked = lms["roll_no"].notna()
    log("LMS activity", "Moodle LMS", "LMS user id + login email", n_in, len(lms), linked.sum(),
        lms.loc[linked, "method"].value_counts().to_dict(),
        {"duplicate log rows removed": dup, "negative time-on-platform values blanked": neg,
         "users who signed up with a personal email": (users["method"] != "official email").sum()})
    lms = lms[linked].drop(columns=["lms_user_id", "method"])

    # 5. Student affairs (events, clubs, hackathons, certifications) -----------
    ev, has_ev = read_source(raw, "05_student_affairs_events.csv")
    n_in = len(ev)
    ev["dept_n"] = ev["department"].map(norm_dept)
    ev["year_n"] = ev["year_of_study"].map(norm_year)
    known = direct(ev["roll_no"]) if "roll_no" in ev else pd.Series(np.nan, index=ev.index, dtype=object)
    cache, rolls, reasons = {}, [], []
    for r, kn in zip(ev.itertuples(), known):
        if isinstance(kn, str):  # the file already gives the roll number
            rolls.append(kn)
            reasons.append("roll no")
            continue
        k = (r.participant_name, r.dept_n, r.year_n)
        if k not in cache:
            cache[k] = by_dept_year.match(r.participant_name, (r.dept_n, r.year_n))
        rolls.append(cache[k][0])
        reasons.append(cache[k][1])
    ev["roll_no"], ev["reason"] = rolls, reasons
    for (name, dept, year), (roll, why) in cache.items():
        if roll is None:
            report["review_queue"].append(dict(source="Student affairs", record=f"{name} ({dept}, year {year})",
                                               reason=why))
    linked = ev["roll_no"].notna()
    log("Events & certifications", "Student affairs office", "Name + dept + year only (no ID)", n_in, len(ev),
        linked.sum(), ev.loc[linked, "reason"].replace({"fuzzy name": "fuzzy name within dept + year"}).value_counts().to_dict(),
        {"department labels standardised": (ev["department"] != ev["dept_n"]).sum(),
         "year labels standardised": (ev["year_of_study"].astype(str) != ev["year_n"].astype(str)).sum(),
         "rows sent to manual review": (~linked).sum()})
    ev = ev[linked][["roll_no", "event_month", "event_type", "event_name"]]

    # 6. Placement training vendor ---------------------------------------------
    pl, has_pl = read_source(raw, "06_placement_training_scores.csv", dtype={"candidate_id": str})
    n_in = len(pl)
    dup = pl.duplicated().sum()
    pl = pl.drop_duplicates()
    cid = pl["candidate_id"].astype(str).str.strip().str.lower()
    r1 = cid.map(register_to_roll)
    r2 = cid.map(email_to_roll)
    r3 = cid.map(personal_to_roll)
    r4 = direct(pl["candidate_id"])
    pl["roll_no"] = r1.fillna(r2).fillna(r3).fillna(r4)
    meth = np.select([r1.notna(), r2.notna(), r3.notna(), r4.notna()],
                     ["register no -> roll no", "official email", "personal email learned from LMS", "roll no"], "")
    pl["score_num"] = to_num(pl["score"])
    linked = pl["roll_no"].notna()
    for c in pl.loc[~linked, "candidate_id"].unique():
        report["review_queue"].append(dict(source="Placement vendor", record=c, reason="unknown identifier"))
    log("Placement training", "Placement cell (training vendor)", "Register No / email / personal email",
        n_in, len(pl), linked.sum(), pd.Series(meth[linked.values]).value_counts().to_dict(),
        {"duplicate rows removed": dup, "scores with '%' or '/5' cleaned": pl["score"].astype(str).str.contains("%|/").sum()})
    pl = pl[linked]

    # 7. Skills assessment -----------------------------------------------------
    sk, has_sk = read_source(raw, "07_skills_assessment.csv")
    n_in = len(sk)
    sk["roll_no"] = sk["student_ref"].map(norm_roll)
    linked = sk["roll_no"].isin(roll_set)
    log("Skills assessment", "Skills platform", "'23-CS-045' style ID", n_in, len(sk), linked.sum(),
        {"ID format translated": linked.sum()},
        {"students with no assessment (left blank, lowers confidence)": len(sis) - linked.sum()})
    sk = sk[linked][["roll_no", "technical_score", "soft_skill_score"]]

    # 8. Feedback --------------------------------------------------------------
    fb, has_fb = read_source(raw, "08a_faculty_feedback.csv")
    n_in = len(fb)
    fb["roll_no"] = fb["student"].map(norm_roll)
    linked = fb["roll_no"].isin(roll_set)
    log("Faculty feedback", "Faculty feedback portal", "Roll No (lower case)", n_in, len(fb), linked.sum(),
        {"normalised roll no": linked.sum()}, {})
    fb = fb[linked]
    sv, has_sv = read_source(raw, "08b_student_survey.csv")
    n_in = len(sv)
    e = sv["respondent_email"].astype(str).str.lower().str.strip()
    r4 = direct(sv["respondent_email"])
    sv["roll_no"] = e.map(email_to_roll).fillna(e.map(personal_to_roll)).fillna(r4)
    meth = np.where(e.map(email_to_roll).notna(), "official email",
                    np.where(e.map(personal_to_roll).notna(), "personal email learned from LMS",
                             np.where(sv["roll_no"].notna(), "roll no", "")))
    linked = sv["roll_no"].notna()
    log("Student survey", "Feedback survey (Google Form)", "Respondent email", n_in, len(sv), linked.sum(),
        pd.Series(meth[linked.values]).value_counts().to_dict(),
        {"students who did not respond (lowers confidence)": len(sis) - linked.sum()})
    sv = sv[linked].drop_duplicates("roll_no")

    # 9. Past interventions + alumni --------------------------------------------
    iv, has_iv = read_source(raw, "09_intervention_log_past.csv")
    iv["roll_no"] = iv["roll_no"].map(norm_roll)
    alumni, has_alumni = read_source(raw, "10_alumni_placement_outcomes.csv")
    if not has_alumni:  # fall back to the built-in sample history
        alumni = pd.read_csv(C.ROOT / "assets" / "sample_alumni.csv")

    report["review_queue_size"] = len(report["review_queue"])
    tot_in = sum(s["rows_in"] for s in report["sources"])
    tot_link = sum(s["linked_rows"] for s in report["sources"])
    provided = dict(lms=bool(has_users and has_lms), events=has_ev, placement=has_pl, skills=has_sk, feedback=has_fb,
                    survey=has_sv, interventions=has_iv, alumni=has_alumni)
    report["provided"] = provided
    n_files = 3 + sum([has_users, has_lms, has_ev, has_pl, has_sk, has_fb, has_sv, has_iv, has_alumni])
    report["summary"] = dict(students=len(sis), source_files=n_files, rows_in=tot_in, rows_linked=tot_link,
                             overall_link_rate=round(100 * tot_link / max(tot_in, 1), 1))
    return dict(sis=sis, exams=ex, attendance=att, lms=lms, events=ev, placement=pl, skills=sk, feedback=fb,
                survey=sv, interventions=iv, alumni=alumni, report=report)


if __name__ == "__main__":
    out = integrate()
    for s in out["report"]["sources"]:
        print(f"{s['source']:25s} in={s['rows_in']:>7} clean={s['rows_after_cleaning']:>7} linked={s['link_rate']:>5}%  {s['methods']}")
        for k, v in s["issues"].items():
            print(f"{'':27s}- {k}: {v}")
    print("review queue:", out["report"]["review_queue_size"])
    print(out["report"]["summary"])
