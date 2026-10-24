"""Decision intelligence on top of the scores: what works, is it fair, and what should leadership know."""
import numpy as np
import pandas as pd

from . import config as C
from .models import feats_for, fit, best_threshold, frame


ALERT_RULE = "LMS logins over the last 2 weeks at 40% (or less) of the student's own first-3-week level, or 5 of the last 8 assignments missed"


def alert_weeks(panel, semester):
    """First week (from week 5) in which the college's existing simple alert fired, per student."""
    p = panel[panel["semester"] == semester]
    if p["logins"].isna().all():  # no LMS data provided
        return pd.Series(dtype=float)
    weeks = range(1, C.WEEKS_PER_SEM + 1)
    L = p.pivot_table(index="roll_no", columns="week", values="logins").reindex(columns=weeks)
    D = p.pivot_table(index="roll_no", columns="week", values="assignments_due").reindex(columns=weeks, index=L.index)
    S = p.pivot_table(index="roll_no", columns="week", values="assignments_submitted").reindex(columns=weeks, index=L.index)
    base = L[[1, 2, 3]].mean(axis=1)
    first = pd.Series(np.nan, index=L.index)
    for w in range(5, C.WEEKS_PER_SEM + 1):
        recent = L[[w - 2, w - 1]].mean(axis=1)
        missed = D[[x for x in range(w - 4, w)]].sum(axis=1) - S[[x for x in range(w - 4, w)]].sum(axis=1)
        fired = ((base >= 1.5) & (recent <= 0.4 * base)) | (missed >= 5)
        first = first.where(first.notna(), np.where(fired, w, np.nan))
    return first


def intervention_effects(panel, hist, log):
    """
    Did past actions work? The college's old alert fired for some students each semester and mentors
    followed up on roughly 60% of them, depending on who they had time for, not on how bad things looked.
    So within the alerted group, students who got no action are a fair comparison for each action.
    Comparisons are weighted by prior-CGPA band so weaker students are compared with weaker students.
    """
    rows = []
    for s in (C.TRAIN_SEM, C.TEST_SEM):
        first = alert_weeks(panel, s).dropna()
        h = hist[hist["semester"] == s].set_index("roll_no")
        df = h.loc[first.index, ["prior_cgpa", "acad_fail"]].copy()
        acts = log[log["semester"] == s].drop_duplicates("roll_no").set_index("roll_no")["action"]
        df["action"] = acts.reindex(df.index).fillna("No action taken")
        rows.append(df)
    df = pd.concat(rows)
    empty = pd.DataFrame([dict(action="No action taken", students=len(df), fail_rate=df["acad_fail"].mean() if len(df) else 0.0,
                               expected_without_action=df["acad_fail"].mean() if len(df) else 0.0,
                               failures_prevented_per_100=0.0, fail_rate_reduction=0.0)])
    if not len(df) or (df["action"] == "No action taken").all():
        return empty
    df["band"] = pd.cut(df["prior_cgpa"], [0, 6.5, 7.5, 11], labels=["<6.5", "6.5-7.5", ">7.5"])
    none = df[df["action"] == "No action taken"]
    none_rate = none.groupby("band", observed=False)["acad_fail"].mean()
    out = []
    for a, g in df.groupby("action"):
        mix = g["band"].value_counts(normalize=True)
        expected = float((mix * none_rate.reindex(mix.index)).sum())
        out.append(dict(action=a, students=len(g), fail_rate=g["acad_fail"].mean(), expected_without_action=expected))
    g = pd.DataFrame(out)
    g["failures_prevented_per_100"] = 100 * (g["expected_without_action"] - g["fail_rate"])
    g["fail_rate_reduction"] = (g["expected_without_action"] - g["fail_rate"]) / g["expected_without_action"]
    g = g[g["action"] != "No action taken"].sort_values("fail_rate_reduction", ascending=False)
    base = none["acad_fail"].mean()
    g = pd.concat([g, pd.DataFrame([dict(action="No action taken", students=len(none), fail_rate=base,
                                         expected_without_action=base, failures_prevented_per_100=0.0,
                                         fail_rate_reduction=0.0)])])
    return g.reset_index(drop=True)


def fairness(S, bt, sis):
    out = {}
    bt = bt.join(sis[["gender", "residence", "first_graduate"]])
    for col, label in [("gender", "Gender"), ("residence", "Residence"), ("first_graduate", "First-graduate")]:
        rows = []
        for val, grp in S.groupby(col):
            b = bt[bt[col] == val]
            failed = b[b["failed"] == 1]
            ok = b[b["failed"] == 0]
            y34 = grp[grp["year"] >= 3]
            rows.append(dict(group=str(val), students=int(len(grp)),
                             high_academic_risk=float((grp["acad_risk"] == "High").mean()),
                             attendance_shortage=float(grp["attendance_shortage"].mean()),
                             high_placement_risk=float((y34["placement_risk"] == "High").mean()) if len(y34) else np.nan,
                             backtest_recall=float(failed["model_flag_w9"].mean()) if len(failed) else np.nan,
                             backtest_false_alarm=float(ok["model_flag_w9"].mean()) if len(ok) else np.nan,
                             avg_success_score=float(grp["success_score"].mean())))
        if not rows:  # the college did not record this attribute
            continue
        r = pd.DataFrame(rows)
        hr = r["high_academic_risk"]
        out[label] = dict(rows=rows, risk_ratio=float(hr.min() / hr.max()) if hr.max() > 0 else 1.0,
                          shortage_ratio=float(r["attendance_shortage"].min() / max(r["attendance_shortage"].max(), 1e-9)),
                          recall_gap=float(r["backtest_recall"].max() - r["backtest_recall"].min()))
    return out


def dept_summary(S, flags):
    W = C.CURRENT_WEEK
    rows = []
    for dept, g in S.groupby("dept"):
        rows.append(dict(dept=dept, students=len(g), avg_score=g["success_score"].mean(),
                         high_risk=int((g["acad_risk"] == "High").sum()),
                         high_risk_pct=(g["acad_risk"] == "High").mean(),
                         newly_flagged=int(g["newly_flagged"].sum()),
                         attendance_shortage=int(g["attendance_shortage"].sum()),
                         placement_high=int((g["placement_risk"] == "High").sum()),
                         silent_strugglers=int((g["segment"] == "Silent Strugglers").sum()),
                         flagged_week6=float(flags.loc[g.index, 6].mean()), flagged_now=float(flags.loc[g.index, W].mean())))
    return pd.DataFrame(rows)


def top_driver(S, mask):
    """How often each kind of reason appears among the given students (any of their top reasons)."""
    from collections import Counter
    c = Counter()
    for rs in S.loc[mask, "acad_reasons"]:
        for fam in {_driver_family(r) for r in rs}:
            c[fam] += 1
    return c.most_common(4)


def _driver_family(reason):
    r = reason.lower()
    for k, v in [("lms", "Falling LMS activity"), ("assignment", "Missed assignments"), ("attendance", "Attendance"),
                 ("cia-1", "Low CIA-1 marks"), ("cgpa", "Weak academic history (CGPA)"), ("arrear", "Standing arrears")]:
        if k in r:
            return v
    return "Other"


def insights(S, bt, pm, effects, fair, report):
    W = C.CURRENT_WEEK
    ins = []
    hi = S["acad_risk"] == "High"
    silent = S["segment"] == "Silent Strugglers"
    ins.append(dict(kind="risk", title=f"{hi.sum()} students at high academic risk in week {W}",
                    body=(f"{int(S['newly_flagged'].sum())} were newly flagged this week. "
                          f"{silent.sum()} are Silent Strugglers: their marks and attendance still look fine, "
                          f"but LMS and assignment activity is falling.")))
    bt_text = (f"Back-tested on {bt['test_semester']}, a semester the model never saw: by week 6 it had flagged "
               f"{bt['recall_by_week6']:.0%} of the students who went on to fail, versus {bt['rule_recall_by_week6']:.0%} "
               f"for the usual attendance-shortage and low-marks lists, on average {bt['avg_weeks_earlier_than_rule']:.1f} weeks earlier.")
    ins.append(dict(kind="model", title="Warnings arrive weeks before marks fall", body=bt_text))
    sh = S["attendance_shortage"]
    recoverable = sh & (S["required_rate_for_75"] <= 95)
    ins.append(dict(kind="attendance", title=f"{sh.sum()} students heading for attendance shortage",
                    body=(f"At their current pace they will finish below 75% and lose exam eligibility. "
                          f"{recoverable.sum()} can still make it if they attend at least 95% of remaining classes; "
                          f"act now while it's still possible.")))
    fam = top_driver(S, hi)
    if fam:
        behav = sum(v for k, v in fam if k in ("Falling LMS activity", "Missed assignments", "Attendance"))
        ins.append(dict(kind="driver", title=f"Most common reason for high risk: {fam[0][0]}",
                        body="Reasons appearing among high-risk students: " +
                             ", ".join(f"{k} ({v})" for k, v in fam) +
                             ". Behaviour signals (LMS, assignments, attendance) are fixable this semester; "
                             "history (CGPA, arrears) needs longer-term academic support."))
    bsjs = S["segment"] == "Book-smart, Job-shy"
    if bsjs.any():
        g = S[bsjs]
        ins.append(dict(kind="placement", title=f"{bsjs.sum()} 'Book-smart, Job-shy' students",
                        body=(f"Average CGPA {g['cgpa'].mean():.2f}, but placement readiness only {g['placement'].mean():.0f}/100. "
                              f"They average {g['mock_interviews'].mean():.1f} mock interviews vs "
                              f"{pm['placed_avg']['mock_interviews']:.1f} for seniors who got placed.")))
    o = pm["odds_per_unit"]
    ins.append(dict(kind="placement", title="Mock interviews beat certifications for placement",
                    body=(f"From last year's {pm['n_alumni']} graduates: each extra mock interview raised placement odds by "
                          f"{(o['mock_interviews'] - 1):.0%}; each extra certification by {(o['certifications'] - 1):.0%}. "
                          f"Placement cell effort should shift toward mock-interview drives.")))
    acted = effects[effects["action"] != "No action taken"]
    best, worst = (acted.iloc[0], acted.iloc[-1]) if len(acted) else (None, None)
    if best is not None:
        ins.append(dict(kind="intervention", title=f"What works: {best['action']}",
                        body=(f"Among students flagged by the old LMS alert in the last two semesters, {best['fail_rate']:.0%} of "
                          f"those given {best['action'].lower()} failed, against {best['expected_without_action']:.0%} of "
                          f"comparable alerted students nobody followed up with: "
                          f"about {best['failures_prevented_per_100']:.0f} failures prevented per 100 students. "
                          f"{worst['action']} showed the least effect.")))
    r = fair.get("Residence", {"rows": []})
    rows = {x["group"]: x for x in r["rows"]}
    if "Day Scholar" in rows and "Hostel" in rows:
        ds, hs = rows["Day Scholar"]["attendance_shortage"], rows["Hostel"]["attendance_shortage"]
        if hs > 0:
            ins.append(dict(kind="fairness", title="Day scholars face more attendance shortage",
                            body=(f"{ds:.0%} of day scholars vs {hs:.0%} of hostellers are heading for shortage "
                                  f"({ds / hs:.1f}x). Likely a commute issue, not motivation: consider bus timings "
                                  f"or first-hour scheduling before penalising.")))
    s = report["summary"]
    ins.append(dict(kind="data", title=f"{s['overall_link_rate']}% of {s['rows_in']:,} records linked",
                    body=((f"12 files from 9 campus systems, each using a different student identifier, joined into one "
                           if C.RAW_DIR.resolve() == C.SAMPLE_RAW_DIR.resolve() else
                           f"{s['source_files']} kinds of records joined into one ")
                          + f"view of {s['students']:,} students. {report['review_queue_size']} records go to manual review "
                          f"rather than being guessed.")))
    return ins
