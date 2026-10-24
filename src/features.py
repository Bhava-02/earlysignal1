"""Turn the integrated records into weekly behaviour panels and per-student features."""
import numpy as np
import pandas as pd

from . import config as C

GP = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "RA": 0}


def weekly_panel(att, lms):
    """One row per student x semester x week with attendance, LMS and assignment activity."""
    a = att.groupby(["roll_no", "semester", "week"], as_index=False)[["classes_held", "classes_attended"]].sum()
    p = a.merge(lms, on=["roll_no", "semester", "week"], how="outer")
    return p.sort_values(["roll_no", "semester", "week"]).reset_index(drop=True)


def subject_attendance(att, semester):
    s = att[att["semester"] == semester].groupby(["roll_no", "subject_code"], as_index=False)[
        ["classes_held", "classes_attended"]].sum()
    s["attendance_pct"] = 100 * s["classes_attended"] / s["classes_held"]
    return s


def snapshot(panel, semester, week):
    """Behaviour features using only what was known by the end of `week`."""
    p = panel[(panel["semester"] == semester) & (panel["week"] <= week)]
    g = p.groupby("roll_no")
    out = pd.DataFrame(index=g.size().index)
    held, attd = g["classes_held"].sum(), g["classes_attended"].sum()
    out["att_pct"] = 100 * attd / held.replace(0, np.nan)
    recent = p[p["week"] > week - 4]
    early = p[p["week"] <= week - 4]
    r = recent.groupby("roll_no")[["classes_held", "classes_attended"]].sum()
    e = early.groupby("roll_no")[["classes_held", "classes_attended"]].sum()
    out["att_recent"] = 100 * r["classes_attended"] / r["classes_held"].replace(0, np.nan)
    out["att_trend"] = (out["att_recent"] - 100 * e["classes_attended"] / e["classes_held"].replace(0, np.nan)).fillna(0)
    out["lms_avg"] = g["logins"].mean()
    base_weeks = max(1, week - 3)
    base = p[p["week"] <= base_weeks].groupby("roll_no")["logins"].mean()
    rec = p[p["week"] > week - 3].groupby("roll_no")["logins"].mean() if week > 3 else base
    out["lms_recent"] = rec
    out["lms_change"] = ((rec - base) / (base + 1.0)).clip(-1, 1).fillna(0)
    due, sub = g["assignments_due"].sum(), g["assignments_submitted"].sum()
    out["asg_rate"] = (sub / due.replace(0, np.nan)).fillna(1.0)
    bd = p[p["week"] <= base_weeks].groupby("roll_no")[["assignments_due", "assignments_submitted"]].sum()
    rd = p[p["week"] > week - 3].groupby("roll_no")[["assignments_due", "assignments_submitted"]].sum()
    base_rate = (bd["assignments_submitted"] / bd["assignments_due"].replace(0, np.nan))
    rec_rate = (rd["assignments_submitted"] / rd["assignments_due"].replace(0, np.nan))
    out["asg_change"] = (rec_rate - base_rate).fillna(0) if week > 3 else 0.0
    out["weeks_observed"] = g["week"].nunique()
    return out


def academic_history(exams, sis):
    """Prior CGPA, standing arrears, CIA-1 and semester outcomes for each tracked semester.

    Assumption: an arrear is re-attempted in the next semester's arrear exam, so a subject
    failed last semester is still 'standing' when a new semester starts.
    """
    ex = exams.copy()
    ex["gp"] = ex["grade"].map(GP)
    s_ = sis.set_index("roll_no")
    cur_no = 2 * s_["year"] - 1  # odd semester running (sample college)
    if "current_sem_no" in s_:  # the college told us each student's current semester
        cur_no = s_["current_sem_no"].fillna(cur_no)
    ex["rel"] = ex["semester_no"] - ex["roll_no"].map(cur_no)  # 0 = current, -1 = last semester, ...
    first = ex[(ex["attempt"] == 1) & ex["grade"].notna()]
    cleared = set(map(tuple, ex.loc[ex["attempt"] > 1, ["roll_no", "subject_code"]].values))
    hsc = sis.set_index("roll_no")["hsc_percent"]
    rows = []
    for k, sem in enumerate(C.SEMESTERS):
        target = k - (len(C.SEMESTERS) - 1)  # -2, -1, 0
        before = first[first["rel"] < target]
        cgpa = before[before["gp"] > 0].groupby("roll_no")["gp"].mean()
        failed = before[before["gp"] == 0]
        mask = [((r, c) not in cleared) or (rel == target - 1) for r, c, rel in
                failed[["roll_no", "subject_code", "rel"]].values]
        backlogs = failed[mask].groupby("roll_no").size() if len(failed) else pd.Series(dtype=int)
        cur = ex[ex["rel"] == target]
        cia = cur.groupby("roll_no").agg(cia1_pct=("cia1", lambda x: 100 * x.fillna(0).mean() / 50),
                                         cia1_absent=("cia1_absent", "sum"))
        graded = cur[cur["grade"].notna() & (cur["attempt"] == 1)]
        res = graded.groupby("roll_no").agg(
            fails=("gp", lambda x: int((x == 0).sum())),
            sgpa=("gp", lambda x: x[x > 0].mean() if (x > 0).any() else 0.0))
        d = pd.DataFrame(index=pd.Index(sis["roll_no"], name="roll_no"))
        d["semester"] = sem
        d["prior_cgpa"] = cgpa.reindex(d.index)
        d["has_prior_cgpa"] = d["prior_cgpa"].notna()
        d["prior_cgpa"] = d["prior_cgpa"].fillna(hsc / 10 - 1.0).clip(4, 10)  # first semester: proxy from HSC %
        d["backlogs"] = backlogs.reindex(d.index).fillna(0).astype(int)
        d = d.join(cia).join(res)
        if sem != C.CURRENT_SEM:
            d["acad_fail"] = ((d["fails"] > 0) | (d["sgpa"] < 6.0)).astype(int)
        rows.append(d.reset_index())
    hist = pd.concat(rows, ignore_index=True)
    sgpa_hist = (first[first["rel"] < 0].groupby(["roll_no", "semester_no"])["gp"]
                 .apply(lambda x: round(x[x > 0].mean(), 2) if (x > 0).any() else 0.0).reset_index(name="sgpa"))
    fails_hist = first[first["rel"] < 0].groupby(["roll_no", "semester_no"])["gp"].apply(
        lambda x: int((x == 0).sum())).reset_index(name="arrears")
    sgpa_hist = sgpa_hist.merge(fails_hist, on=["roll_no", "semester_no"])
    return hist, sgpa_hist
