"""
A demo "college server" for the prototype: two databases laid out the way colleges really store data.

  college_erp.db  - the college ERP (as in typical Indian college ERPs): departments, staff, students,
                    academic terms, subjects, exam marks, PERIOD-WISE attendance (one row per student per
                    class hour, marked P / A / OD), placement training, skills, activities, feedback,
                    survey, mentor actions and last year's placement results.
  moodle.db       - the Moodle LMS, using Moodle's own table names (mdl_user, mdl_logstore_standard_log,
                    mdl_assign, mdl_assign_submission).

Both are SQLite files so the demo runs anywhere. A real college would run MySQL, PostgreSQL, SQL Server or
Oracle; EarlySignal connects to those the same way, with the same SQL.

Built from the sample college:  python -m src.demo_server
"""
import gc
import os
import sqlite3
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import config as C

DIR = C.ROOT / "data" / "demo_server"
ERP_DB = DIR / "college_erp.db"
LMS_DB = DIR / "moodle.db"
SIM_FILE = DIR / "simulation.json"  # the "prove it's live" change, so it survives a browser refresh

# the sample college's three semesters, each starting on a Monday
TERMS = [("2025-ODD", date(2025, 7, 21)), ("2026-EVEN", date(2026, 1, 5)), ("2026-ODD", date(2026, 8, 10))]


def exists():
    return ERP_DB.exists() and LMS_DB.exists()


def _day(term, week, offset):
    start = dict(TERMS)[term]
    return start + timedelta(days=7 * (int(week) - 1) + int(offset))


def build(verbose=False):
    with C.sample_mode():  # always the sample college, whatever data the app shows now
        return _build(verbose)


def _build(verbose):
    from .integrate import integrate

    say = print if verbose else (lambda *a: None)
    d = integrate()
    rng = np.random.default_rng(11)
    DIR.mkdir(parents=True, exist_ok=True)
    erp_tmp, lms_tmp = ERP_DB.with_suffix(".part"), LMS_DB.with_suffix(".part")  # renamed only when complete
    for p in (ERP_DB, LMS_DB, erp_tmp, lms_tmp, SIM_FILE):
        p.unlink(missing_ok=True)

    sis = d["sis"].copy()
    sis["student_id"] = np.arange(1001, 1001 + len(sis))
    sid = dict(zip(sis["roll_no"], sis["student_id"]))

    # departments, staff (mentors)
    depts = pd.DataFrame([(i + 1, k, v[0]) for i, (k, v) in enumerate(C.DEPTS.items())],
                         columns=["department_id", "dept_code", "dept_name"])
    did = dict(zip(depts["dept_code"], depts["department_id"]))
    mentors = sis.groupby("mentor")["dept"].agg(lambda x: x.mode().iloc[0]).reset_index()
    staff = pd.DataFrame({"staff_id": np.arange(501, 501 + len(mentors)), "staff_name": mentors["mentor"],
                          "department_id": mentors["dept"].map(did), "designation": "Assistant Professor"})
    stid = dict(zip(staff["staff_name"], staff["staff_id"]))
    students = pd.DataFrame({
        "student_id": sis["student_id"], "roll_no": sis["roll_no"],
        "register_no": [f"{C.COLLEGE_CODE}{r[:2]}{C.DEPTS[dp][1]}{r[4:]}" for r, dp in zip(sis["roll_no"], sis["dept"])],
        "full_name": sis["name"], "gender": sis["gender"], "department_id": sis["dept"].map(did),
        "batch_year": sis["batch"], "current_semester": 2 * sis["year"] - 1, "section": sis["section"],
        "hostel_flag": np.where(sis["residence"] == "Hostel", "Y", "N"),
        "first_graduate": np.where(sis["first_graduate"] == "Yes", "Y", "N"),
        "mentor_staff_id": sis["mentor"].map(stid), "email": sis["email"], "hsc_percentage": sis["hsc_percent"],
        "status": "ACTIVE"})
    terms = pd.DataFrame([(i + 1, n, s.isoformat(), (s + timedelta(weeks=C.WEEKS_PER_SEM) - timedelta(days=1)).isoformat(),
                           int(n == TERMS[-1][0])) for i, (n, s) in enumerate(TERMS)],
                         columns=["term_id", "term_name", "start_date", "end_date", "is_current"])

    # subjects and marks
    ex = d["exams"].copy()
    att = d["attendance"]
    subj = ex.groupby("subject_code").agg(subject_name=("subject_name", "first"), semester=("semester_no", "min"))
    for code in set(att["subject_code"]) - set(subj.index):
        subj.loc[code] = [code, np.nan]
    subj = subj.reset_index()
    subj["department_id"] = subj["subject_code"].str[:2].map({v[2]: did[k] for k, v in C.DEPTS.items()})
    subj["subject_id"] = np.arange(1, len(subj) + 1)
    subj["credits"] = 3
    subj = subj[["subject_id", "subject_code", "subject_name", "department_id", "semester", "credits"]]
    sub_id = dict(zip(subj["subject_code"], subj["subject_id"]))
    marks = pd.DataFrame({
        "mark_id": np.arange(1, len(ex) + 1), "student_id": ex["roll_no"].map(sid).values,
        "subject_id": ex["subject_code"].map(sub_id).values, "cia1": ex["cia1"].values,
        "cia1_status": np.where(ex["cia1_absent"], "AB", "P"), "cia2": ex["cia2"].values,
        "end_sem": ex["end_sem"].values, "grade": ex["grade"].values, "attempt_no": ex["attempt"].values})
    say("subjects", len(subj), "marks", len(marks))

    # period-wise attendance: each class hour of the week is one row (P = present, A = absent, OD = on duty).
    # Kept as plain number arrays and written in batches, so building it needs little memory.
    att = att[att["classes_held"] > 0].reset_index(drop=True)
    a_sid = att["roll_no"].map(sid).to_numpy(np.int64)
    a_sub = att["subject_code"].map(sub_id).to_numpy(np.int64)
    a_start = pd.to_datetime(att["semester"].map(dict(TERMS))).to_numpy().astype("datetime64[D]")
    a_week = att["week"].to_numpy(np.int64)
    a_held = att["classes_held"].to_numpy(np.int64)
    a_attd = att["classes_attended"].to_numpy(np.int64)
    del att, d["attendance"]
    gc.collect()
    # placement training, skills, activities, feedback, survey, mentor actions, alumni
    pl = d["placement"]
    placement = pd.DataFrame({"id": np.arange(1, len(pl) + 1), "student_id": pl["roll_no"].map(sid).values,
                              "test_type": pl["test_type"].values, "score": pl["score_num"].values,
                              "test_date": (pl["attempt_month"].astype(str) + "-15").values})
    sk = d["skills"]
    skills = pd.DataFrame({"id": np.arange(1, len(sk) + 1), "student_id": sk["roll_no"].map(sid).values,
                           "technical_score": sk["technical_score"].values, "soft_skill_score": sk["soft_skill_score"].values,
                           "assessed_on": "2026-07-20"})
    ev = d["events"]
    activities = pd.DataFrame({"id": np.arange(1, len(ev) + 1), "student_id": ev["roll_no"].map(sid).values,
                               "activity_type": ev["event_type"].values, "title": ev["event_name"].values,
                               "activity_date": (ev["event_month"].astype(str) + "-10").values})
    fb = d["feedback"]
    feedback = pd.DataFrame({"id": np.arange(1, len(fb) + 1), "student_id": fb["roll_no"].map(sid).values,
                             "subject_id": fb["subject_code"].map(sub_id).values,
                             "participation_rating": fb["participation_rating"].values, "remark": fb["remark"].values,
                             "given_on": [_day("2026-ODD", w, 3).isoformat() for w in fb["given_in_week"]]})
    sv = d["survey"]
    survey = pd.DataFrame({"id": np.arange(1, len(sv) + 1), "student_id": sv["roll_no"].map(sid).values,
                           "course_satisfaction": sv["course_satisfaction"].values,
                           "feels_supported": sv["feels_supported"].values, "workload_stress": sv["workload_stress"].values,
                           "submitted_on": [_day("2026-ODD", w, 2).isoformat() for w in sv["submitted_week"]]})
    iv = d["interventions"]
    iv = iv[iv["roll_no"].isin(sid)]
    actions = pd.DataFrame({"id": np.arange(1, len(iv) + 1), "student_id": iv["roll_no"].map(sid).values,
                            "action_date": [_day(t, w, 2).isoformat() for t, w in zip(iv["semester"], iv["week"])],
                            "action": iv["action"].values, "done_by": iv["owner"].values})
    al = d["alumni"]
    alumni = pd.DataFrame({
        "id": np.arange(1, len(al) + 1), "roll_no": al["alumni_id"], "department_id": al["dept"].map(did),
        "final_cgpa": al["final_cgpa"], "standing_arrears": al["standing_backlogs"], "aptitude_score": al["best_aptitude"],
        "coding_score": al["best_coding"], "technical_score": al["technical_score"],
        "soft_skill_score": al["soft_skill_score"], "mock_interviews": al["mock_interviews"],
        "mock_rating": al["avg_mock_rating"], "certifications": al["certifications"],
        "internship": np.where(al["internship"].astype(int) == 1, "Y", "N"),
        "placed": np.where(al["placed"] == "Yes", "Y", "N"), "offer_tier": al["offer_tier"]})

    with sqlite3.connect(erp_tmp) as con:
        con.execute("CREATE TABLE attendance (attendance_id INTEGER, student_id INTEGER, subject_id INTEGER, "
                    "class_date TEXT, period_no INTEGER, status TEXT)")
        n_att = 0
        for lo in range(0, len(a_held), 30000):
            hi = min(lo + 30000, len(a_held))
            h = a_held[lo:hi]
            rep = np.repeat(np.arange(lo, hi), h)
            k = np.arange(len(rep)) - np.repeat(np.cumsum(h) - h, h)  # which class hour of that week
            rank = np.empty(len(rep), np.int64)
            rank[np.lexsort((rng.random(len(rep)), rep))] = k  # random order of the week's hours
            present = rank < a_attd[rep]
            status = np.where(present, np.where(rng.random(len(rep)) < 0.03, "OD", "P"), "A")
            dates = a_start[rep] + (7 * (a_week[rep] - 1) + k % 5).astype("timedelta64[D]")
            con.executemany("INSERT INTO attendance VALUES (?,?,?,?,?,?)", zip(
                range(n_att + 1, n_att + len(rep) + 1), a_sid[rep].tolist(), a_sub[rep].tolist(),
                np.datetime_as_string(dates, unit="D").tolist(), (k // 5 + 1 + a_sub[rep] % 4).tolist(),
                status.tolist()))
            n_att += len(rep)
        say("attendance rows", n_att)
        for name, df in [("departments", depts), ("staff", staff), ("students", students), ("academic_terms", terms),
                         ("subjects", subj), ("exam_marks", marks),
                         ("placement_training", placement), ("skill_assessments", skills),
                         ("student_activities", activities), ("faculty_feedback", feedback), ("student_survey", survey),
                         ("mentor_actions", actions), ("alumni_placements", alumni)]:
            df.to_sql(name, con, index=False)
        for t, c in [("attendance", "student_id"), ("exam_marks", "student_id"), ("students", "roll_no")]:
            con.execute(f"CREATE INDEX ix_{t}_{c} ON {t}({c})")

    # ---- Moodle
    lms = d["lms"].copy()
    users = sis[sis["roll_no"].isin(set(lms["roll_no"]))].reset_index(drop=True)
    users["id"] = np.arange(2, 2 + len(users))  # Moodle user 1 is the guest account
    uid = dict(zip(users["roll_no"], users["id"]))
    parts = users["name"].str.split(" ", n=1)
    mdl_user = pd.DataFrame({"id": users["id"], "username": users["roll_no"].str.lower(), "idnumber": users["roll_no"],
                             "email": users["email"], "firstname": parts.str[0], "lastname": parts.str[1].fillna(""),
                             "deleted": 0})
    lg = lms[lms["logins"] > 0]
    n = lg["logins"].astype(int).values
    L = lg.iloc[np.repeat(np.arange(len(lg)), n)].reset_index(drop=True)
    base = pd.to_datetime(L["semester"].map({t: s for t, s in TERMS})) + pd.to_timedelta(7 * (L["week"].astype(int) - 1),
                                                                                           unit="D")
    secs = rng.integers(7 * 3600, 7 * 86400 - 3600, len(L))
    ts = ((base - datetime(1970, 1, 1)).dt.total_seconds().astype("int64") + secs - 19800)  # IST -> UTC
    logs = pd.DataFrame({"id": np.arange(1, len(L) + 1), "eventname": "\\core\\event\\user_loggedin",
                         "component": "core", "action": "loggedin", "target": "user",
                         "userid": L["roll_no"].map(uid).values, "courseid": 0, "timecreated": ts.values})
    # assignments: one Moodle assignment per due slot per week, a submission row per student it was due for
    due = lms[lms["assignments_due"] > 0].copy()
    due["n"] = due["assignments_due"].astype(int)
    slots = due.groupby(["semester", "week"])["n"].max().reset_index()
    arows, aid = [], {}
    for t, w, m in slots.itertuples(index=False):
        for j in range(m):
            aid[(t, w, j)] = len(arows) + 1
            dd = datetime.combine(_day(t, w, 4), datetime.min.time()) + timedelta(hours=23, minutes=59)
            arows.append((len(arows) + 1, 0, f"Weekly assignment {j + 1} ({t}, week {w})",
                          int((dd - datetime(1970, 1, 1)).total_seconds()) - 19800))
    mdl_assign = pd.DataFrame(arows, columns=["id", "course", "name", "duedate"])
    srows = []
    for r_, t, w, nd, ns in due[["roll_no", "semester", "week", "n", "assignments_submitted"]].itertuples(index=False):
        for j in range(nd):
            srows.append((aid[(t, w, j)], uid[r_], "submitted" if j < ns else "new"))
    sub = pd.DataFrame(srows, columns=["assignment", "userid", "status"])
    sub.insert(0, "id", np.arange(1, len(sub) + 1))
    sub["timemodified"] = sub["assignment"].map(dict(zip(mdl_assign["id"], mdl_assign["duedate"]))) - 3600
    sub["latest"] = 1
    with sqlite3.connect(lms_tmp) as con:
        for name, df in [("mdl_user", mdl_user), ("mdl_logstore_standard_log", logs), ("mdl_assign", mdl_assign),
                         ("mdl_assign_submission", sub)]:
            df.to_sql(name, con, index=False)
        con.execute("CREATE INDEX ix_log_user ON mdl_logstore_standard_log(userid)")
    os.replace(erp_tmp, ERP_DB)
    os.replace(lms_tmp, LMS_DB)
    say("moodle users", len(mdl_user), "login events", len(logs), "assignments", len(mdl_assign), "submissions", len(sub))
    return dict(students=len(students), attendance_rows=n_att, marks=len(marks), login_events=len(logs))


def tables():
    """Table name -> row count for both demo databases (for the page)."""
    out = {}
    for label, p in (("ERP", ERP_DB), ("Moodle", LMS_DB)):
        with sqlite3.connect(f"file:{p}?mode=ro", uri=True) as con:
            for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                out[(label, t)] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


if __name__ == "__main__":
    import time
    t0 = time.time()
    print(build(verbose=True), f"{time.time() - t0:.1f}s")


# ---------------------------------------------------------------- "prove it's live" (plays the college's own systems)
def rolls():
    with sqlite3.connect(f"file:{ERP_DB}?mode=ro", uri=True) as con:
        return {r for (r,) in con.execute("SELECT roll_no FROM students")}


def simulate_dropout(roll, from_week=7):
    """Act as the college's attendance system and Moodle: from `from_week` of this semester the student is marked
    absent in every class, stops logging in, and stops submitting assignments. (EarlySignal itself never writes;
    this only changes the demo server, so the next sync can show the dashboard reacting.)"""
    start = TERMS[-1][1]
    d0 = start + timedelta(weeks=from_week - 1)
    with sqlite3.connect(ERP_DB) as con:
        row = con.execute("SELECT student_id FROM students WHERE roll_no = ?", (roll,)).fetchone()
        if not row:
            raise ValueError(f"{roll} is not on the demo server")
        n_att = con.execute("UPDATE attendance SET status = 'A' WHERE student_id = ? AND class_date >= ? "
                            "AND status <> 'A'", (row[0], d0.isoformat())).rowcount
    ts0 = int((datetime.combine(d0, datetime.min.time()) - datetime(1970, 1, 1)).total_seconds()) - 19800
    n_log = n_sub = 0
    with sqlite3.connect(LMS_DB) as con:
        u = con.execute("SELECT id FROM mdl_user WHERE idnumber = ?", (roll,)).fetchone()
        if u:
            n_log = con.execute("DELETE FROM mdl_logstore_standard_log WHERE userid = ? AND timecreated >= ?",
                                (u[0], ts0)).rowcount
            n_sub = con.execute("UPDATE mdl_assign_submission SET status = 'new' WHERE userid = ? AND status = "
                                "'submitted' AND assignment IN (SELECT id FROM mdl_assign WHERE duedate >= ?)",
                                (u[0], ts0)).rowcount
    return dict(attendance=n_att, logins=n_log, submissions=n_sub, from_date=d0)


def load_sim():
    import json
    try:
        return json.loads(SIM_FILE.read_text()) if SIM_FILE.exists() else None
    except Exception:
        return None


def save_sim(sim):
    import json
    if sim is None:
        SIM_FILE.unlink(missing_ok=True)
    else:
        SIM_FILE.write_text(json.dumps(sim, default=str))
