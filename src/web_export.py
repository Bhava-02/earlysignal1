"""
Export everything the React dashboard needs into ONE JSON file: data/processed/web/bundle.json.

The React app is a static site (no server needed, never sleeps). It reads this bundle, so every number it
shows comes from the same pipeline, models and rules. Model parameters are included so the what-if
simulator and Path to Green can re-run the exact models in the browser.
"""
import json
import math
import time

import numpy as np
import pandas as pd

from . import config as C
from . import round2 as R
from .features import GP
from .models import PL_FEATS, PL_LABELS
from .recommend import ACTION_NAMES, dept_priorities, evidence_lines, recommend_student, segment_playbooks
from .scoring import INDICATORS, SUB_LABEL
from .segments import SEGMENTS

FAMILY = {"att_pct": "Attendance", "att_trend": "Attendance", "att_last2": "Attendance", "lms_avg": "LMS activity",
          "lms_change": "LMS activity", "lms_last2": "LMS activity", "asg_rate": "Assignments",
          "asg_change": "Assignments", "asg_last2": "Assignments", "prior_cgpa": "CGPA", "backlogs": "Arrears",
          "arrears_due": "Arrears", "cia1_pct": "CIA-1 marks", "cia1_absent": "CIA-1 marks", "week": "Timing",
          "best_aptitude": "Aptitude", "best_coding": "Coding", "mock_interviews": "Mock interviews",
          "avg_mock_rating": "Mock interviews", "technical_score": "Technical skills", "soft_skill_score": "Soft skills",
          "certifications": "Certifications", "eligible": "Eligibility"}


def clean(o):
    """JSON-safe: NaN/inf -> None, numpy -> python, floats rounded to keep the file small."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4 if abs(f) < 1 else 3)
    return o


def rnd(d):
    """Round display values: 2 decimals below 10 (CGPA, rates), 1 decimal above (percentages, scores)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (float, np.floating)) and not (isinstance(v, float) and math.isnan(v)):
            out[k] = round(float(v), 2 if abs(v) < 10 else 1)
        else:
            out[k] = v
    return out


def reasons_list(con_row, raw_row, sign=1, k=3, cut=0.2):
    out = []
    for x in R.top_reasons(con_row, raw_row, sign=sign, k=k, cut=cut):
        out.append(x)
    return out


def place_reasons(con_row, row, bench, placed_avg):
    out = []
    for f, v in con_row.sort_values().items():
        if v >= -0.25 or len(out) >= 3:
            break
        val = row[f]
        if f == "eligible":
            txt = f"Not eligible for most recruiters (CGPA {row['cgpa']:.2f}, {row['backlogs']:.0f} arrear(s))"
        elif f == "mock_interviews":
            txt = f"{val:.0f} mock interview(s) done (placed seniors averaged {placed_avg[f]:.1f})"
        elif f == "avg_mock_rating":
            txt = f"Mock interview rating {val:.1f}/5 (placed seniors averaged {placed_avg[f]:.1f})" if row["mock_interviews"] > 0 \
                else "No mock interview rating yet"
        elif f == "certifications":
            txt = f"{val:.0f} certification(s) (placed seniors averaged {placed_avg[f]:.1f})"
        else:
            txt = f"{PL_LABELS[f]} {val:.0f} (benchmark {bench.get(f, placed_avg[f]):.0f})"
        out.append(dict(feature=f, text=txt, impact=round(float(-v), 2)))
    return out


def weak_subjects(exams, sis):
    s_ = sis.set_index("roll_no")
    cur_no = 2 * s_["year"] - 1
    if "current_sem_no" in s_:
        cur_no = s_["current_sem_no"].fillna(cur_no)
    ex = exams[(exams["attempt"] == 1)].copy()
    ex = ex[ex["semester_no"] == ex["roll_no"].map(cur_no)]
    ex = ex[ex["cia1"].notna()]
    ex["cia1p"] = 100 * ex["cia1"] / 50
    out = {}
    for r, g in ex.sort_values("cia1p").groupby("roll_no"):
        out[r] = [dict(subject=n, cia1=float(c)) for n, c in zip(g["subject_name"], g["cia1p"])][:3]
    return out


def series(panel, sem, roll_order, weeks):
    p = panel[panel["semester"] == sem].copy()
    p["att"] = 100 * p["classes_attended"] / p["classes_held"].replace(0, np.nan)
    p["asg"] = p["assignments_submitted"] / p["assignments_due"].replace(0, np.nan)
    out = {}
    for col in ("att", "logins", "asg"):
        pv = p.pivot_table(index="roll_no", columns="week", values=col).reindex(index=roll_order, columns=weeks)
        out[col] = pv
    return out


def build(d, hist, panel, S, plw, wt, lr, pm, effects, fair, ins, meta_extra, r2=None):
    t0 = time.time()
    W, WEEKS = C.CURRENT_WEEK, C.WEEKS_PER_SEM
    r2 = r2 or R.run(d, hist, panel, S, plw, lr, pm)
    sp, bk, en, pr = r2["semester"], r2["backlog"], r2["engagement"], r2["placement"]
    targ = r2["targets"]
    cur_t = targ[targ["semester"] == C.CURRENT_SEM].set_index("roll_no")
    bench = pr["benchmarks"]
    placed_avg = pm["placed_avg"]
    ev = evidence_lines(effects, pm["odds_per_unit"])
    weak = weak_subjects(d["exams"], d["sis"])
    rolls = list(S.index)
    cur_series = series(panel, C.CURRENT_SEM, rolls, list(range(1, W + 1)))
    last_series = series(panel, C.TEST_SEM, rolls, list(range(1, WEEKS + 1)))
    acad_weeks = lr["probs"].reindex(rolls)
    back_weeks = bk["weekly"].reindex(rolls)
    eng_weeks = en["weekly"].reindex(rolls)
    sg_hist = None
    try:
        from .features import academic_history
        _, sg_hist = academic_history(d["exams"], d["sis"])
    except Exception:
        pass
    sgh = {r: g.sort_values("semester_no")[["semester_no", "sgpa"]].values.tolist()
           for r, g in sg_hist.groupby("roll_no")} if sg_hist is not None else {}

    pc = panel[panel["semester"] == C.CURRENT_SEM].groupby("roll_no")
    missing_asg = (pc["assignments_due"].sum() - pc["assignments_submitted"].sum()).clip(lower=0)
    eng_flag, eng_high = en["threshold"], en["high"]
    eng_level = lambda p: "High" if p >= eng_high else ("Medium" if p >= eng_flag else "Low")
    ctx = dict(evidence=ev, bench=bench, flag=R.FLAG, high=R.HIGH, eng_high=eng_high, eng_base=en["event_rate"],
               horizon=en["horizon"], week=W, weeks=WEEKS, asg_avg=float(S["asg_rate"].mean()),
               placed_avg=placed_avg)

    students, catalog = [], {}
    for roll in rolls:
        s = S.loc[roll]
        cap = lambda p: float(min(0.99, max(0.001, p)))  # never show "100%" or "0%" for a forecast
        acad_p = cap(s["acad_prob"])
        bp = cap(bk["prob"].get(roll, 0.0))
        ep = cap(en["prob"].get(roll, 0.0))
        pp = cap(pr["prob"].get(roll)) if s["year"] >= 3 else None
        elig = bool(s["eligible"] == 1)
        plevel = R.placement_level(pp if pp is not None else 0, elig, int(s["year"]))
        sg = float(sp["sgpa"]["pred"].get(roll, np.nan))
        cur_row = sp["current"].loc[roll] if roll in sp["current"].index else pd.Series(dtype=float)
        bk_row = bk["current"].loc[roll] if roll in bk["current"].index else pd.Series(dtype=float)
        en_row = en["current"].loc[roll] if roll in en["current"].index else pd.Series(dtype=float)
        reasons = dict(
            semester=reasons_list(sp["contrib"].loc[roll], cur_row) if roll in sp["contrib"].index else [],
            backlog=reasons_list(bk["contrib"].loc[roll], bk_row) if roll in bk["contrib"].index else [],
            engagement=reasons_list(en["contrib"].loc[roll], en_row) if roll in en["contrib"].index else [],
            placement=place_reasons(pr["contrib"].loc[roll], s, bench, placed_avg) if s["year"] >= 3 else [],
            sgpa=reasons_list(sp["sgpa"]["contrib"].loc[roll], cur_row, sign=-1) if roll in sp["sgpa"]["contrib"].index else [],
        )
        asg_missing = float(missing_asg.get(roll, 0.0))
        row = dict(
            s.to_dict(), roll=roll, acad_prob=acad_p, backlog_prob=bp, backlog_level=R.level(bp), eng_prob=ep,
            eng_level=eng_level(ep), place_prob=pp if pp is not None else np.nan, place_level=plevel,
            months_left=float(pr["months_left"].get(roll, 0)), arrears_due=float(cur_t["arrears_due"].get(roll, 0)),
            reasons=reasons, weak_subjects=weak.get(roll, []), asg_missing=asg_missing,
            stress=None if pd.isna(s.get("stress")) else float(s["stress"]),
        )
        recs = recommend_student(row, ctx)
        for x in recs:
            catalog.setdefault(x["key"], dict(name=ACTION_NAMES.get(x["key"], x["key"]), category=x["category"],
                                              evidence=x["evidence"]))
        lo, hi = max(0.0, sg - sp["sgpa"]["rmse"]), min(10.0, sg + sp["sgpa"]["rmse"])
        change3 = float(acad_weeks.loc[roll, W] - acad_weeks.loc[roll, W - 3]) if W - 3 in acad_weeks.columns else 0.0
        watch = (s["acad_risk"] == "Low") and (eng_level(ep) != "Low" or bp >= R.FLAG or change3 >= 0.1)
        top = recs[0] if recs else None
        students.append(dict(
            id=roll, name=s["name"], dept=s["dept"], year=int(s["year"]), sec=s["section"], mentor=s["mentor"],
            score=float(s["success_score"]), band=s["band"], acad=float(s["academic"]), eng=float(s["engagement"]),
            plc=float(s["placement"]), conf=s["confidence_label"], confv=float(s["confidence"]), segment=s["segment"],
            f=rnd(dict(att=s["att_pct"], att_recent=s["att_recent"], att_trend=s["att_trend"], lms=s["lms_avg"],
                   lms_change=s["lms_change"], asg=s["asg_rate"], asg_change=s["asg_change"], cia1=s["cia1_pct"],
                   cia1_absent=s["cia1_absent"], cgpa=s["cgpa"], backlogs=s["backlogs"], arrears_due=row["arrears_due"],
                   proj_att=s["projected_attendance"], need_rate=s["required_rate_for_75"], held=s["classes_held"],
                   attended=s["classes_attended"], remaining=s["classes_remaining"], activities=s["activities"],
                   satisfaction=s["satisfaction"], satisfaction_missing=bool(s["satisfaction_missing"]),
                   faculty_rating=s["faculty_rating"], remark=s["faculty_remark"], apt=s["best_aptitude"],
                   coding=s["best_coding"], mocks=s["mock_interviews"], mock_rating=s["avg_mock_rating"],
                   tech=s["technical_score"], soft=s["soft_skill_score"], certs=s["certifications"],
                   eligible=elig, momentum=s["momentum"], hsc=s["hsc_percent"],
                   lms_last2=en_row.get("lms_last2"), att_last2=en_row.get("att_last2"), asg_last2=en_row.get("asg_last2"),
                   apt_proj=pr["projected"].loc[roll, "best_aptitude"], coding_proj=pr["projected"].loc[roll, "best_coding"],
                   missing=[k for k, *_ in INDICATORS if f"{k}_missing" in s and bool(s[f"{k}_missing"])])),
            pred=dict(
                semester=dict(p=acad_p, level=s["acad_risk"], reasons=reasons["semester"], sgpa=sg, sgpa_band=R.sgpa_band(sg),
                              sgpa_low=lo, sgpa_high=hi, sgpa_reasons=reasons["sgpa"]),
                backlog=dict(p=bp, level=R.level(bp), reasons=reasons["backlog"]),
                engagement=dict(p=ep, level=eng_level(ep), reasons=reasons["engagement"], x_usual=ep / max(en["event_rate"], 1e-9)),
                placement=dict(p=pp, p_now=cap(pr["prob_now"].get(roll)) if s["year"] >= 3 else None, level=plevel,
                               reasons=reasons["placement"], months_left=row["months_left"],
                               gaps=[k for k in ("best_aptitude", "best_coding", "mock_interviews", "soft_skill_score")
                                     if (s["year"] >= 3 or k in ("best_aptitude", "soft_skill_score")) and s[k] < bench[k]]
                                    + ([] if elig or s["year"] <= 2 else ["eligible"])),
            ),
            hist=dict(acad=[cap(acad_weeks.loc[roll, w]) for w in acad_weeks.columns],
                      backlog=[cap(back_weeks.loc[roll, w]) for w in back_weeks.columns],
                      engagement=[cap(eng_weeks.loc[roll, w]) for w in eng_weeks.columns]),
            weekly=dict(att=list(cur_series["att"].loc[roll].round(0)), lms=list(cur_series["logins"].loc[roll]),
                        asg=list(cur_series["asg"].loc[roll].round(2)), att_last=list(last_series["att"].loc[roll].round(0)),
                        lms_last=list(last_series["logins"].loc[roll]), asg_last=list(last_series["asg"].loc[roll].round(2))),
            sgpa_hist=sgh.get(roll, []), weak=weak.get(roll, [])[:2],
            recs=[{k: v for k, v in x.items() if k not in ("evidence", "when")} for x in recs], priority=top["priority"] if top else "None", pscore=top["score"] if top else 0,
            next=top["action"] if top else "No action needed this week", owner=top["owner"] if top else "",
            new=bool(s["newly_flagged"]), watch=bool(watch), change3=change3,
            first_flag=None if pd.isna(s["first_flag_week"]) else int(s["first_flag_week"]),
        ))

    # ---- model cards: what each forecast is, how it was validated, how it compares with the Round 1 baseline
    def card(title, question, target, m, base, usual, usual_name, drivers, extra=None):
        return dict(title=title, question=question, target=target, metrics=m, baseline=base, usual=usual,
                    usual_name=usual_name, drivers=[dict(x, family=FAMILY.get(x["feature"], x["feature"])) for x in drivers],
                    **(extra or {}))

    models = dict(
        semester=card("Semester performance", "Will this student fail a subject (or get SGPA below 6) this semester?",
                      "Fails at least one subject or SGPA below 6.0", sp["metrics"], sp["baseline"], sp["usual"],
                      "Usual lists (attendance < 75%, CIA-1 < 50%)", sp["drivers"],
                      dict(curve=sp["curve"], sgpa=sp["sgpa"]["metrics"],
                           sgpa_drivers=[dict(x, family=FAMILY.get(x["feature"], x["feature"])) for x in sp["sgpa"]["drivers"]],
                           validation=f"Trained on {C.TRAIN_SEM}, tested on {C.TEST_SEM} (never seen), at week {W}.")),
        backlog=card("Backlog risk", "Will this student get a new arrear, or fail to clear last semester's arrear?",
                     "New arrear this semester, or last semester's arrear not cleared", bk["metrics"], bk["baseline"],
                     bk["usual"], "Simple rule (has arrears or CIA-1 < 50%)", bk["drivers"],
                     dict(event_rate=bk["event_rate"],
                          validation=f"Trained on {C.TRAIN_SEM}, tested on {C.TEST_SEM} (never seen), at week {W}.")),
        engagement=card("Engagement drop", f"Will this student's engagement fall significantly in the next {en['horizon']} weeks?",
                        "At least 2 of: attendance down 12+ pts, LMS logins halved, submissions down 40+ pts (vs own level)",
                        en["metrics"], en["baseline"], en["usual"], "Simple rule (any signal already falling)", en["drivers"],
                        dict(event_rate=en["event_rate"], all_weeks=en["metrics_all_weeks"], threshold=eng_flag, high=eng_high,
                             validation=f"Trained on weeks 4-12 of {C.TRAIN_SEM}, tested on {C.TEST_SEM} (never seen); "
                                        f"cut-off chosen on the training semester to favour recall.")),
        placement=card("Placement readiness", "Will this student be placement-ready when the placement season starts?",
                       "Placed in last year's season (360 graduates)", pr["metrics"],
                       dict(pr["baseline_cgpa"], name="CGPA only"), pr["baseline_eligibility"],
                       "Eligibility rule only (CGPA 6.5+, no arrears)", pr["drivers"],
                       dict(benchmarks=bench, n_alumni=pr["n_alumni"], placed_rate=pr["placed_rate"], gains=pr["gains"],
                            ready_threshold=pr["ready_threshold"], odds=pm["odds_per_unit"].to_dict(),
                            placed_avg=placed_avg.to_dict(),
                            validation="5-fold cross-validation on last year's 360 graduates; current students are "
                                       "projected to the season start at their own improvement rate.")),
    )

    seg_meta = [dict(name=x["name"], color=x["color"], rule=x["rule"], why=x["why"], owner=x["owner"], kpi=x["kpi"],
                     actions=x["actions"]) for x in SEGMENTS]
    playbooks = segment_playbooks(students, seg_meta, effects, FAMILY)
    priorities = dept_priorities(students, effects, list(C.DEPTS))

    from .pipeline import score_trend
    trend = score_trend(S, panel, hist, plw)

    params = dict(
        score=dict(indicators=[dict(key=k, part=sub, label=lab, lo=lo, hi=hi, invert=inv) for k, sub, lab, lo, hi, inv, *_ in INDICATORS],
                   weights={str(y): w for y, w in wt.items()}, parts=SUB_LABEL,
                   bands=[dict(min=m, name=n) for m, n in C.BANDS]),
        semester=sp["params"], sgpa=sp["sgpa"]["params"], backlog=bk["params"], engagement=en["params"],
        placement=pr["params"], thresholds=dict(flag=R.FLAG, high=R.HIGH, eng_flag=eng_flag, eng_high=eng_high,
                                                ready=pr["ready_threshold"]),
        placement_cgpa_min=C.PLACEMENT_CGPA_MIN, attendance_min=C.ATTENDANCE_MIN,
    )

    depts = [dict(code=k, name=v[0]) for k, v in C.DEPTS.items() if k in set(S["dept"])]
    mentors = (S.groupby(["mentor", "dept"]).size().reset_index(name="students")
               .sort_values(["dept", "mentor"]).to_dict("records"))
    bundle = dict(
        meta=dict(college=C.COLLEGE_NAME, semester=C.CURRENT_SEM, last_semester=C.TEST_SEM, train_semester=C.TRAIN_SEM,
                  week=W, weeks=WEEKS, built_at=time.strftime("%d %b %Y, %H:%M"), depts=depts, mentors=mentors,
                  years=sorted(int(y) for y in S["year"].unique()), n=len(students),
                  using_sample=meta_extra.get("using_sample", True)),
        models=models, params=params, students=students, actions=catalog, families=FAMILY, segments=playbooks, dept_priorities=priorities,
        what_works=effects.to_dict("records"), fairness=fair, insights=ins,
        quality=dict(summary=meta_extra.get("quality", {}).get("summary", {}),
                     sources=[{k: v for k, v in s_.items() if k in ("source", "system", "identifier", "rows_in", "link_rate")}
                              for s_ in meta_extra.get("quality", {}).get("sources", [])],
                     review=meta_extra.get("quality", {}).get("review_queue_size", 0)),
        score_trend=trend.to_dict("records"), round1_backtest=meta_extra.get("backtest", {}),
    )
    out = C.PROC_DIR / "web"
    out.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(clean(bundle), separators=(",", ":"), allow_nan=False)
    (out / "bundle.json").write_text(txt)
    print(f"Web bundle: {len(txt) / 1e6:.1f} MB, {len(students)} students, {time.time() - t0:.1f}s")
    return bundle
