"""
Run everything: raw files -> integrated data -> scores, risks, segments, insights.
Usage:  python -m src.pipeline
Writes everything the dashboard needs into data/processed/.
"""
import json
import pickle
import time

import numpy as np
import pandas as pd

from . import config as C
from .analytics import fairness, intervention_effects, insights, dept_summary
from .features import academic_history, subject_attendance, weekly_panel
from .generate_data import generate
from .integrate import integrate
from .models import (FEAT_LABELS, PL_FEATS, PL_LABELS, backtest, contributions, frame, live_risk,
                     placement_model)
from .scoring import INDICATORS, compute_scores, placement_weights
from .segments import assign



def acad_reason(feat, v):
    return {
        "att_pct": f"Attendance {v:.0f}% so far",
        "att_trend": f"Attendance fell {abs(v):.0f} pts in the last 4 weeks",
        "lms_avg": f"Only {v:.1f} LMS logins a week",
        "lms_change": f"LMS activity down {abs(v) * 100:.0f}% in the last 3 weeks",
        "asg_rate": f"Only {v * 100:.0f}% of assignments submitted",
        "asg_change": f"Assignment submissions down {abs(v) * 100:.0f} pts recently",
        "prior_cgpa": f"CGPA {v:.2f} before this semester",
        "backlogs": f"{v:.0f} standing arrear(s)",
        "cia1_pct": f"CIA-1 average {v:.0f}%",
        "cia1_absent": f"Missed {v:.0f} CIA-1 paper(s)",
    }[feat]


def place_reason(feat, v, avg, row):
    if feat == "eligible":
        return f"Not eligible for most recruiters (CGPA {row['cgpa']:.2f}, {row['backlogs']:.0f} arrear(s))"
    fmt = {"mock_interviews": "{:.0f}", "avg_mock_rating": "{:.1f}", "certifications": "{:.0f}"}.get(feat, "{:.0f}")
    return f"{PL_LABELS[feat]} {fmt.format(v)} (placed seniors averaged {fmt.format(avg)})"


def build_students(d, hist, panel, lr, pm):
    W = C.CURRENT_WEEK
    sis = d["sis"].set_index("roll_no")
    S = sis[["name", "gender", "dept", "batch", "year", "section", "residence", "first_graduate", "mentor",
             "hsc_percent", "email"]].copy()
    cur = lr["current"]
    for c in ["att_pct", "att_recent", "att_trend", "lms_avg", "lms_recent", "lms_change", "asg_rate", "asg_change",
              "cia1_pct", "cia1_absent", "backlogs"]:
        S[c] = cur[c]
    S["cgpa"] = cur["prior_cgpa"]
    hcur = hist[hist["semester"] == C.CURRENT_SEM].set_index("roll_no")
    S["cgpa_missing"] = ~hcur["has_prior_cgpa"]

    fb = d["feedback"].groupby("roll_no")
    S["faculty_rating"] = fb["participation_rating"].mean()
    S["low_rating_subjects"] = fb["participation_rating"].apply(lambda x: int((x <= 2).sum()))
    S["faculty_remark"] = d["feedback"].sort_values("participation_rating").groupby("roll_no")["remark"].first()

    ev = d["events"]
    S["activities"] = ev[ev["event_type"] != "Certification"].groupby("roll_no").size()
    S["hackathons"] = ev[ev["event_type"] == "Hackathon"].groupby("roll_no").size()
    S["certifications"] = ev[ev["event_type"] == "Certification"].groupby("roll_no").size()
    for c in ["activities", "hackathons", "certifications"]:
        S[c] = S[c].fillna(0).astype(int)

    sv = d["survey"].set_index("roll_no")
    S["satisfaction"] = (sv["course_satisfaction"] + sv["feels_supported"]) / 2
    S["stress"] = sv["workload_stress"]

    pl = d["placement"]
    g = pl.groupby(["roll_no", "test_type"])["score_num"]
    best = g.max().unstack()
    first = pl.sort_values("attempt_month").groupby(["roll_no", "test_type"])["score_num"].first().unstack()
    nan = pd.Series(np.nan, index=S.index)
    S["best_aptitude"] = best["Aptitude"] if "Aptitude" in best else nan
    S["aptitude_gain"] = (best["Aptitude"] - first["Aptitude"]) if "Aptitude" in best else nan
    S["best_coding"] = best["Coding"] if "Coding" in best else nan
    S["mock_interviews"] = pl[pl["test_type"] == "Mock Interview"].groupby("roll_no").size()
    means = g.mean().unstack()
    S["avg_mock_rating"] = means["Mock Interview"] if "Mock Interview" in means else nan
    has_pl = S.index.isin(pl["roll_no"].unique())
    S["placement_records"] = has_pl
    sk = d["skills"].set_index("roll_no")
    S["technical_score"] = sk["technical_score"]
    S["soft_skill_score"] = sk["soft_skill_score"]
    S["eligible"] = ((S["cgpa"] >= C.PLACEMENT_CGPA_MIN) & (S["backlogs"] <= C.PLACEMENT_MAX_BACKLOGS)).astype(float)
    S.loc[S["cgpa"].isna(), "eligible"] = np.nan  # no CGPA yet (first semester): unknown, not "ineligible"
    S["momentum"] = (0.4 * S["lms_change"] + 0.8 * S["asg_change"] + 0.02 * S["att_trend"]).clip(-1, 1)

    # sources the college did not provide count as unknown (not as zero)
    prov = d["report"].get("provided", {})
    if not prov.get("lms", True):
        S[["lms_avg", "asg_rate", "momentum"]] = np.nan
    if not prov.get("events", True):
        S[["activities", "certifications"]] = np.nan
    if not prov.get("feedback", True):
        S["faculty_remark"] = "No faculty feedback provided"

    # missing flags, then fill so the score stays a clean weighted sum
    S["mock_interviews"] = np.where(has_pl, S["mock_interviews"].fillna(0), np.nan)
    for k, *_ in INDICATORS:
        miss = S[k].isna()
        if k in ("best_coding", "mock_interviews", "avg_mock_rating"):
            miss &= S["year"] >= 3
        S[f"{k}_missing"] = miss if k != "cgpa" else S["cgpa_missing"]
    S["avg_mock_rating"] = np.where(S["mock_interviews"].fillna(0) > 0, S["avg_mock_rating"], 1.0)
    S.loc[S["year"] <= 2, ["best_coding", "mock_interviews"]] = S.loc[S["year"] <= 2, ["best_coding", "mock_interviews"]].fillna(0)
    for k, _, _, lo, hi, inv, *_ in INDICATORS:
        S[k] = S[k].astype(float).fillna(S.groupby("year")[k].transform("median")).fillna((lo + hi) / 2)
    S["faculty_remark"] = S["faculty_remark"].fillna("No remark")
    S["satisfaction_missing"] = S["satisfaction_missing"].astype(bool)

    # Success Score
    plw = placement_weights(pm["coef"])
    sc, contrib, norm, wt = compute_scores(S, plw)
    S = S.join(sc)

    # Academic risk (early-warning model) + attendance projection
    P, F, thr = lr["probs"], lr["flags"], lr["threshold"]
    S["acad_prob"] = P[W]
    pc = panel[panel["semester"] == C.CURRENT_SEM]
    held = pc.groupby("roll_no")["classes_held"].sum()
    attd = pc.groupby("roll_no")["classes_attended"].sum()
    remaining = held / W * (C.WEEKS_PER_SEM - W)
    S["classes_held"], S["classes_attended"], S["classes_remaining"] = held, attd, remaining.round()
    S["projected_attendance"] = 100 * (attd + S["att_recent"] / 100 * remaining) / (held + remaining)
    S["required_rate_for_75"] = 100 * (0.75 * (held + remaining) - attd) / remaining
    lvl = np.select([S["acad_prob"] >= C.RISK_HIGH, S["acad_prob"] >= C.RISK_MEDIUM], ["High", "Medium"], "Low")
    lvl = np.where((S["projected_attendance"] < C.ATTENDANCE_MIN) & (lvl == "Low"), "Medium", lvl)
    lvl = np.where(S["att_pct"] < 70, "High", lvl)
    S["acad_risk"] = lvl
    S["attendance_shortage"] = S["projected_attendance"] < C.ATTENDANCE_MIN
    S["first_flag_week"] = F.apply(lambda r: int(r.idxmax()) if r.any() else np.nan, axis=1)
    S["newly_flagged"] = (P[W] >= C.RISK_HIGH) & (P[W - 1] < C.RISK_HIGH)  # moved into High risk this week
    S["risk_change_3w"] = P[W] - P[W - 3]
    ac = lr["contrib"]
    reasons = []
    for r in S.index:
        row = ac.loc[r].sort_values(ascending=False)
        rs = [acad_reason(f, cur.at[r, f]) for f, v in row.items() if v > 0.25][:3]
        if S.at[r, "attendance_shortage"] and not any("Attendance" in x for x in rs):
            rs.append(f"Projected to finish at {S.at[r, 'projected_attendance']:.0f}% attendance (below 75%)")
        reasons.append(rs)
    S["acad_reasons"] = reasons

    # Placement risk (3rd / 4th years)
    X = S[PL_FEATS].copy()
    X["avg_mock_rating"] = np.where(S["mock_interviews"] > 0, S["avg_mock_rating"], 2.5)
    S["placement_prob"] = pm["model"].predict_proba(X)[:, 1]
    S.loc[S["year"] <= 2, "placement_prob"] = np.nan
    S["placement_risk"] = np.select(
        [S["year"] <= 2, (S["placement_prob"] < 0.35) | (S["eligible"] == 0), S["placement_prob"] < 0.6],
        ["Pre-placement", "High", "Medium"], "Low")
    pcon = contributions(pm["model"], X, PL_FEATS)
    preasons = []
    for r in S.index:
        if S.at[r, "year"] <= 2:
            preasons.append([])
            continue
        row = pcon.loc[r].sort_values()
        preasons.append([place_reason(f, S.at[r, f], pm["placed_avg"][f], S.loc[r]) for f, v in row.items() if v < -0.25][:3])
    S["placement_reasons"] = preasons

    S["segment"] = assign(S)
    return S, contrib, norm, wt, plw, pcon


ACTION_COLUMNS = ["logged_at", "week", "roll_no", "name", "dept", "action", "owner", "note", "follow_up_week",
                  "status", "logged_by"]


def seed_actions(S, path):
    """A few actions mentors already logged this semester, so the tracker isn't empty on first run."""
    if path.exists():
        return
    rng = np.random.default_rng(7)
    crit = S[S["segment"] == "Critical: Act This Week"].sample(10, random_state=1)
    rows = []
    for r, row in crit.iterrows():
        a = rng.choice(["Mentor meeting", "Remedial classes", "Counselling referral", "Peer tutoring"])
        wk = int(rng.integers(6, 9))
        rows.append(dict(logged_at=f"Week {wk}", week=wk, roll_no=r, name=row["name"], dept=row["dept"], action=a,
                         owner=row["mentor"] if a == "Mentor meeting" else ("Counsellor" if "Counsel" in a else "Subject faculty"),
                         note="Seeded example", follow_up_week=wk + 2,
                         status=rng.choice(["Done", "In progress", "Planned"]), logged_by="Mentor"))
    pd.DataFrame(rows, columns=ACTION_COLUMNS).to_csv(path, index=False)


def score_trend(S, panel, hist, plw):
    """Average Success Score week by week this semester (behaviour indicators change, history stays fixed)."""
    from .models import frame
    rows = []
    for w in range(3, C.CURRENT_WEEK + 1):
        X = frame(panel, hist, C.CURRENT_SEM, w).reindex(S.index)
        T = S.copy()
        T["att_pct"] = X["att_pct"].fillna(S["att_pct"])
        T["lms_avg"] = X["lms_avg"].fillna(S["lms_avg"])
        T["asg_rate"] = X["asg_rate"].fillna(S["asg_rate"])
        T["momentum"] = (0.4 * X["lms_change"] + 0.8 * X["asg_change"] + 0.02 * X["att_trend"]).clip(-1, 1).fillna(S["momentum"])
        if w < C.CIA1_RESULTS_WEEK:  # internal marks not out yet: neutral
            T["cia1_pct"] = S.groupby("year")["cia1_pct"].transform("median")
        sc, *_ = compute_scores(T, plw)
        sc["dept"] = S["dept"]
        for dept, g in [("All", sc)] + list(sc.groupby("dept")):
            rows.append(dict(week=w, dept=dept, success=g["success_score"].mean(), academic=g["academic"].mean(),
                             engagement=g["engagement"].mean(), placement=g["placement"].mean()))
    return pd.DataFrame(rows)


def run(verbose=True, web=None):
    """web=True also writes the React dashboard's data file (python -m src.pipeline --web)."""
    import os
    if web is None:
        web = os.environ.get("EARLYSIGNAL_WEB", "") == "1"
    W = C.CURRENT_WEEK
    t0 = time.time()
    say = print if verbose else (lambda *a, **k: None)
    if not (C.RAW_DIR / "01_sis_student_master.csv").exists():
        say("Generating source data ...")
        generate()
    say("Integrating 12 source files ...")
    d = integrate()
    say("Building features and models ...")
    hist, sgpa_hist = academic_history(d["exams"], d["sis"])
    panel = weekly_panel(d["attendance"], d["lms"])
    curve, bt_summary, bt_detail = backtest(panel, hist)
    lr = live_risk(panel, hist)
    pm = placement_model(d["alumni"])
    say("Scoring students ...")
    S, contrib, norm, wt, plw, pcon = build_students(d, hist, panel, lr, pm)

    say("Analysing interventions, fairness and insights ...")
    trend = score_trend(S, panel, hist, plw)
    effects = intervention_effects(panel, hist, d["interventions"])
    fair = fairness(S, bt_detail, d["sis"].set_index("roll_no"))
    ins = insights(S, bt_summary, pm, effects, fair, d["report"])
    depts = dept_summary(S, lr["flags"])

    out = C.PROC_DIR
    out.mkdir(parents=True, exist_ok=True)
    S2 = S.copy()
    S2["acad_reasons"] = S2["acad_reasons"].map(json.dumps)
    S2["placement_reasons"] = S2["placement_reasons"].map(json.dumps)
    S2.reset_index().to_parquet(out / "students.parquet", index=False)
    contrib.reset_index().to_parquet(out / "score_contributions.parquet", index=False)
    lr["contrib"].reset_index().to_parquet(out / "risk_contributions.parquet", index=False)
    lr["probs"].rename(columns=str).reset_index().to_parquet(out / "risk_by_week.parquet", index=False)
    panel.to_parquet(out / "weekly_panel.parquet", index=False)
    subject_attendance(d["attendance"], C.CURRENT_SEM).to_parquet(out / "subject_attendance.parquet", index=False)
    marks = d["exams"]
    marks.to_parquet(out / "exam_results.parquet", index=False)
    sgpa_hist.to_parquet(out / "sgpa_history.parquet", index=False)
    d["events"].to_parquet(out / "events.parquet", index=False)
    curve.to_csv(out / "backtest_curve.csv", index=False)
    trend.to_csv(out / "score_trend.csv", index=False)
    effects.to_csv(out / "intervention_effects.csv", index=False)
    depts.to_csv(out / "dept_summary.csv", index=False)
    meta = dict(
        current_semester=C.CURRENT_SEM, current_week=W, risk_threshold=lr["threshold"],
        risk_coefficients=lr["coefs"].round(4).to_dict(), risk_feature_labels=FEAT_LABELS,
        backtest=bt_summary, placement=dict(coef=pm["coef"].round(4).to_dict(),
                                            odds_per_unit=pm["odds_per_unit"].round(3).to_dict(),
                                            placed_avg=pm["placed_avg"].round(2).to_dict(), auc=pm["auc"],
                                            placement_rate=pm["placement_rate"], eligible_rate=pm["eligible_rate"],
                                            placed_rate_eligible=pm["placed_rate_eligible"],
                                            placed_rate_ineligible=pm["placed_rate_ineligible"]),
        placement_weights=plw, weight_table={str(k): v for k, v in wt.items()},
        provided=d["report"].get("provided", {}), college_name=C.COLLEGE_NAME,
        using_sample=C.RAW_DIR.resolve() == C.SAMPLE_RAW_DIR.resolve(),
        quality=d["report"], fairness=fair, insights=ins, built_at=time.strftime("%Y-%m-%d %H:%M"),
    )
    with open(out / "models.pkl", "wb") as f:
        pickle.dump(dict(risk_model=lr["model"], risk_features=lr["features"], risk_threshold=lr["threshold"],
                         placement_model=pm["model"], placement_weights=plw), f)
    if C.RAW_DIR.resolve() == C.SAMPLE_RAW_DIR.resolve():
        seed_actions(S, out / "actions_log.csv")  # example entries only for the sample college
    (out / "meta.json").write_text(json.dumps(meta, indent=1, default=float))  # last: marks the data complete
    if web:  # the React dashboard's data file (Round 1 features only)
        try:
            from .web_export_r1 import build as build_web
            say(f"React data file: {build_web()}")
        except Exception as e:  # the Streamlit app keeps working even if this step fails
            say(f"React data file skipped: {type(e).__name__}: {e}")
    say(f"Done in {time.time() - t0:.1f}s -> {out}")
    return S


if __name__ == "__main__":
    import sys
    run(web=True if "--web" in sys.argv else None)  # without the flag, EARLYSIGNAL_WEB=1 still switches it on
