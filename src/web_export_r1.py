"""
Data file for the React dashboard, Round 1 features only (Success Score, weekly early warning, placement
model, segments, what works, data quality). Reads what `python -m src.pipeline` already saved in
data/processed and writes data/processed/web/bundle_r1.json.

    python -m src.pipeline && python -m src.web_export_r1
"""
import json
import math
import pickle

import numpy as np
import pandas as pd

from . import config as C
from .analytics import ALERT_RULE, _driver_family
from .scoring import INDICATORS
from .segments import ORDER, SEG

P = C.PROC_DIR
OUT = P / "web" / "bundle_r1.json"

NUM = ["cgpa", "cia1_pct", "att_pct", "backlogs", "faculty_rating", "lms_avg", "asg_rate", "momentum", "activities",
       "satisfaction", "best_aptitude", "best_coding", "mock_interviews", "avg_mock_rating", "technical_score",
       "soft_skill_score", "certifications", "eligible", "att_recent", "att_trend", "lms_change", "asg_change",
       "cia1_absent", "hackathons", "stress", "low_rating_subjects", "classes_held", "classes_attended",
       "classes_remaining", "projected_attendance", "required_rate_for_75", "success_score", "academic", "engagement",
       "placement", "acad_prob", "placement_prob", "confidence"]
MISSING = ["satisfaction_missing", "technical_score_missing", "soft_skill_score_missing", "best_aptitude_missing",
           "best_coding_missing"]


def r(x, d=3):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, d)


def lst(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return []
    if isinstance(x, str):
        try:
            x = json.loads(x)
        except ValueError:
            return [x]
    return [str(v) for v in list(x)]


def pipe_params(p, features):
    imp, sc, lr = p.named_steps["simpleimputer"], p.named_steps["standardscaler"], p.named_steps["logisticregression"]
    return dict(features=list(features), median=[r(v, 6) for v in imp.statistics_], mean=[r(v, 6) for v in sc.mean_],
                scale=[r(v, 6) for v in sc.scale_], coef=[r(v, 6) for v in lr.coef_[0]], intercept=r(lr.intercept_[0], 6))


def identity_example(S):
    """One real student as they appear in each raw system (sample data only), as on the Round 1 Data quality page."""
    from .integrate import norm_dept, norm_year
    raw = C.RAW_DIR
    try:
        ex = pd.read_csv(raw / "02_exam_cell_results.csv", dtype={"register_no": str})
        users = pd.read_csv(raw / "04a_lms_users.csv")
        ev = pd.read_csv(raw / "05_student_affairs_events.csv")
        att = pd.read_csv(raw / "03_attendance_weekly.csv")
        pl = pd.read_csv(raw / "06_placement_training_scores.csv", dtype={"candidate_id": str})
    except FileNotFoundError:
        return None
    damaged = ex[ex["register_no"].str.contains("E", na=False)]
    E = pd.read_parquet(P / "exam_results.parquet")
    att_norm = att["RollNo"].astype(str).str.strip().str.upper().str.replace(r"^(\d\d[A-Z]{2})0*", r"\1", regex=True)
    ev_norm = ev["participant_name"].str.lower().str.replace(r"[^a-z ]", " ", regex=True).str.split().map(sorted).map(" ".join)
    ev_dept, ev_year = ev["department"].map(norm_dept), ev["year_of_study"].map(norm_year)
    for name in damaged["student_name"].unique()[:200]:
        rolls = E[(E["student_name"] == name) & E["register_no"].astype(str).str.contains("E", na=False)]["roll_no"].unique()
        if len(rolls) != 1 or rolls[0] not in S.index:
            continue
        r_ = rolls[0]
        s = S.loc[r_]
        u = users[users["login_email"].str.lower() == s["email"]]
        e_rows = ev[(ev_norm == " ".join(sorted(s["name"].lower().split()))) & (ev_dept == s["dept"]) & (ev_year == s["year"])]
        a_rows = att[(att_norm == r_[:4] + str(int(r_[4:]))) & (att["RollNo"] != r_)]
        if not len(e_rows) or not len(a_rows) or not len(u):
            continue
        reg = f"{C.COLLEGE_CODE}{r_[:2]}{C.DEPTS[s['dept']][1]}{r_[4:]}"
        p_rows = pl[pl["candidate_id"].isin([reg, s["email"]])]
        rows = [["Student records (SIS)", r_, "Master record"],
                ["Exam cell", damaged[damaged["student_name"] == name]["register_no"].iloc[0],
                 "Number damaged by Excel; matched on name, department and batch"],
                ["Attendance system", a_rows["RollNo"].iloc[0], "Capitals, spaces and zeros fixed"],
                ["Online learning portal", u["login_email"].iloc[0], "Email turned into roll number"],
                ["Events and clubs office", f"{e_rows['participant_name'].iloc[0]} ({e_rows['department'].iloc[0]}, "
                                            f"{e_rows['year_of_study'].iloc[0]})", "Name matched within the same class"],
                ["Placement training", p_rows["candidate_id"].iloc[0] if len(p_rows) else "-", "Register number or email"],
                ["Skills tests", f"{r_[:2]}-{r_[2:4]}-{r_[4:]}", "ID format converted"]]
        return dict(roll=r_, name=s["name"], rows=[[str(a), str(b), str(c)] for a, b, c in rows])
    return None


def build():
    S = pd.read_parquet(P / "students.parquet")
    if "roll_no" in S.columns:
        S = S.set_index("roll_no")
    meta = json.loads((P / "meta.json").read_text())
    models = pickle.load(open(P / "models.pkl", "rb"))
    panel = pd.read_parquet(P / "weekly_panel.parquet")
    risk = pd.read_parquet(P / "risk_by_week.parquet").set_index("roll_no")
    sgpa = pd.read_parquet(P / "sgpa_history.parquet")
    exams = pd.read_parquet(P / "exam_results.parquet")
    satt = pd.read_parquet(P / "subject_attendance.parquet")
    events = pd.read_parquet(P / "events.parquet")
    curve = pd.read_csv(P / "backtest_curve.csv")
    effects = pd.read_csv(P / "intervention_effects.csv")
    trend = pd.read_csv(P / "score_trend.csv")

    W, N = int(meta["current_week"]), C.WEEKS_PER_SEM
    sems = {C.CURRENT_SEM: "now", C.TEST_SEM: "last"}
    panel = panel[panel["semester"].isin(sems)]
    weeks = {}
    for (roll, sem), g in panel.groupby(["roll_no", "semester"]):
        g = g.set_index("week").reindex(range(1, N + 1))
        att = (100 * g["classes_attended"] / g["classes_held"].replace(0, np.nan)).round(0)
        weeks.setdefault(roll, {})[sems[sem]] = dict(
            att=[r(v, 0) for v in att], logins=[r(v, 1) for v in g["logins"]],
            asg=[r(v, 0) for v in g["assignments_submitted"]], due=[r(v, 0) for v in g["assignments_due"]])
    sg = {roll: [[int(a), r(b, 2), int(c)] for a, b, c in g[["semester_no", "sgpa", "arrears"]].values]
          for roll, g in sgpa.sort_values("semester_no").groupby("roll_no")}
    cur = exams[exams["grade"].isna()][["roll_no", "subject_code", "subject_name", "cia1", "cia1_absent"]]
    cur = cur.merge(satt[["roll_no", "subject_code", "attendance_pct"]], on=["roll_no", "subject_code"], how="left")
    subj = {roll: [[c, n, r(a, 0), bool(ab), r(p, 0)] for c, n, a, ab, p in
                   g[["subject_code", "subject_name", "cia1", "cia1_absent", "attendance_pct"]].values]
            for roll, g in cur.groupby("roll_no")}
    ev = {roll: [[m, t, n] for m, t, n in g.sort_values("event_month", ascending=False)[["event_month", "event_type", "event_name"]].values]
          for roll, g in events.groupby("roll_no")}
    wcols = [c for c in risk.columns]

    students = []
    for roll, x in S.iterrows():
        reasons = lst(x.get("acad_reasons"))
        students.append(dict(
            id=roll, name=x["name"], dept=x["dept"], year=int(x["year"]),
            sec=None if pd.isna(x.get("section")) else str(x.get("section")),
            gender=x.get("gender"), res=x.get("residence"), fg=x.get("first_graduate"), mentor=x["mentor"],
            band=x["band"], conf=x["confidence_label"], seg=x["segment"], ar=x["acad_risk"], pr=x["placement_risk"],
            reasons=reasons, fam=[_driver_family(t) for t in reasons], preasons=lst(x.get("placement_reasons")),
            new=bool(x["newly_flagged"]), short=bool(x["attendance_shortage"]),
            remark=None if pd.isna(x.get("faculty_remark")) else str(x.get("faculty_remark")),
            v={k: r(x.get(k)) for k in NUM}, miss={k: bool(x.get(k)) for k in MISSING if k in x},
            risk=[r(risk.at[roll, c], 3) if roll in risk.index else None for c in wcols],
            wk=weeks.get(roll, {}), sgpa=sg.get(roll, []), subj=subj.get(roll, []), ev=ev.get(roll, []),
        ))

    mentors = (S.groupby(["mentor", "dept"]).size().reset_index(name="students").sort_values(["dept", "mentor"]))
    pm = meta["placement"]
    bt = meta["backtest"]
    out = dict(
        meta=dict(college=meta.get("college_name", C.COLLEGE_NAME), semester=meta["current_semester"],
                  last_semester=bt["test_semester"], train_semester=bt["train_semester"], week=W, weeks=N,
                  built_at=meta.get("built_at", ""), using_sample=bool(meta.get("using_sample", True)),
                  cia1_week=C.CIA1_RESULTS_WEEK, risk_high=C.RISK_HIGH, risk_medium=C.RISK_MEDIUM,
                  attendance_min=C.ATTENDANCE_MIN, cgpa_min=C.PLACEMENT_CGPA_MIN, max_backlogs=C.PLACEMENT_MAX_BACKLOGS,
                  risk_weeks=[int(c) for c in wcols], alert_rule=ALERT_RULE,
                  depts=[dict(code=k, name=v[0]) for k, v in C.DEPTS.items() if k in set(S["dept"])],
                  mentors=[dict(name=m, dept=d, students=int(n)) for m, d, n in mentors.values]),
        students=students,
        backtest={k: r(v) for k, v in bt.items()},
        curve=[dict(week=int(w), recall=r(a), rule=r(b)) for w, a, b in curve[["week", "recall", "rule_recall"]].values],
        trend=[dict(week=int(t.week), dept=t.dept, success=r(t.success, 2), academic=r(t.academic, 2),
                    engagement=r(t.engagement, 2)) for t in trend.itertuples()],
        effects=[{k: r(v) for k, v in e.items()} for e in effects.to_dict("records")],
        placement=dict(odds=pm["odds_per_unit"], placed_avg={k: r(v, 2) for k, v in pm["placed_avg"].items()},
                       rate=r(pm["placement_rate"]), eligible_rate=r(pm["placed_rate_eligible"]),
                       ineligible_rate=r(pm["placed_rate_ineligible"])),
        weights={y: {k: r(v, 5) for k, v in w.items()} for y, w in meta["weight_table"].items()},
        indicators=[dict(key=k, part=sub, label=lab, lo=lo, hi=hi, invert=bool(inv)) for k, sub, lab, lo, hi, inv, *_ in INDICATORS],
        segments=[dict(name=n, rule=SEG[n]["rule"], why=SEG[n]["why"], actions=SEG[n]["actions"], owner=SEG[n]["owner"],
                       kpi=SEG[n]["kpi"]) for n in ORDER],
        quality=dict(summary=meta["quality"]["summary"], review_size=meta["quality"].get("review_queue_size", 0),
                     review=meta["quality"].get("review_queue", [])[:400],
                     sources=[{k: s.get(k) for k in ("source", "system", "identifier", "rows_in", "link_rate", "issues")}
                              for s in meta["quality"]["sources"]]),
        identity=identity_example(S) if meta.get("using_sample", True) else None,
        models=dict(risk=pipe_params(models["risk_model"], models["risk_features"]),
                    placement=pipe_params(models["placement_model"], models["placement_model"].feature_names_in_)),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
