"""
What-if simulator and "Path to Green": the smallest realistic set of changes that moves a
student out of risk. Uses the same scoring formula and the same two models as the dashboard,
so the numbers always agree.
"""
import numpy as np
import pandas as pd

from . import config as C
from .scoring import INDICATORS, score_one

IND_KEYS = [k for k, *_ in INDICATORS]


def baseline_values(row):
    return {k: float(row[k]) for k in IND_KEYS}


def projected_attendance(row, rate):
    """End-of-semester attendance if the student attends `rate` (0-1) of the remaining classes."""
    held, attd, rem = row["classes_held"], row["classes_attended"], row["classes_remaining"]
    return 100 * (attd + rate * rem) / (held + rem)


def simulate(row, models, changes):
    """changes: attend_rate (0-1 of remaining classes), asg_rate, lms_avg, mock_add, aptitude_add,
    coding_add, cert_add, arrears_cleared. Returns score, sub-scores, risk and placement probability."""
    v = baseline_values(row)
    behaviour_changed = False
    if "attend_rate" in changes:
        v["att_pct"] = max(row["att_pct"], projected_attendance(row, changes["attend_rate"]))
        behaviour_changed = True
    if "asg_rate" in changes:
        v["asg_rate"] = max(row["asg_rate"], changes["asg_rate"])
        behaviour_changed = True
    if "lms_avg" in changes:
        v["lms_avg"] = max(row["lms_avg"], changes["lms_avg"])
        behaviour_changed = True
    v["mock_interviews"] += changes.get("mock_add", 0)
    if changes.get("mock_add", 0) and row["mock_interviews"] == 0:
        v["avg_mock_rating"] = 2.8  # a typical first-round rating
    v["best_aptitude"] = min(99, v["best_aptitude"] + changes.get("aptitude_add", 0))
    v["best_coding"] = min(99, v["best_coding"] + changes.get("coding_add", 0))
    v["certifications"] += changes.get("cert_add", 0)
    v["backlogs"] = max(0, v["backlogs"] - changes.get("arrears_cleared", 0))
    v["eligible"] = float(v["cgpa"] >= C.PLACEMENT_CGPA_MIN and v["backlogs"] <= C.PLACEMENT_MAX_BACKLOGS)
    if behaviour_changed:
        v["momentum"] = max(v["momentum"], 0.0)

    score, subs = score_one(v, int(row["year"]), models["placement_weights"])

    X = pd.DataFrame([{
        "att_pct": v["att_pct"], "att_trend": max(row["att_trend"], 0) if behaviour_changed else row["att_trend"],
        "lms_avg": v["lms_avg"], "lms_change": max(row["lms_change"], 0) if behaviour_changed else row["lms_change"],
        "asg_rate": v["asg_rate"], "asg_change": max(row["asg_change"], 0) if behaviour_changed else row["asg_change"],
        "prior_cgpa": row["cgpa"], "backlogs": v["backlogs"], "cia1_pct": row["cia1_pct"], "cia1_absent": row["cia1_absent"],
    }])
    prob = float(models["risk_model"].predict_proba(X[models["risk_features"]])[:, 1][0])
    pprob = np.nan
    if row["year"] >= 3:
        P = pd.DataFrame([{k: v[k] for k in ["best_aptitude", "best_coding", "mock_interviews", "avg_mock_rating",
                                              "technical_score", "soft_skill_score", "certifications", "eligible"]}])
        if v["mock_interviews"] == 0:
            P["avg_mock_rating"] = 2.5
        pprob = float(models["placement_model"].predict_proba(P)[:, 1][0])
    return dict(score=score, subs=subs, prob=prob, pprob=pprob, values=v)


def level(prob):
    return "High" if prob >= C.RISK_HIGH else ("Medium" if prob >= C.RISK_MEDIUM else "Low")


def plevel(pprob, eligible):
    if np.isnan(pprob):
        return "Pre-placement"
    return "High" if (pprob < 0.35 or not eligible) else ("Medium" if pprob < 0.6 else "Low")


def path_to_green(row, models, target_score=55.0, max_steps=10):
    """Greedy search: repeatedly take the lever step with the best improvement per unit of effort."""
    year = int(row["year"])
    cur_rate = row["att_recent"] / 100
    levers = {
        "attend_rate": dict(steps=[r for r in (0.80, 0.85, 0.90, 0.95, 1.0) if r > cur_rate + 0.02], cost=1.0),
        "asg_rate": dict(steps=[r for r in (0.7, 0.8, 0.9, 1.0) if r > row["asg_rate"] + 0.02], cost=1.0),
        "lms_avg": dict(steps=[x for x in (3, 4, 5, 6) if x > row["lms_avg"] + 0.3], cost=0.5),
        "mock_add": dict(steps=[1, 2, 3, 4] if year >= 3 else [], cost=1.5),
        "aptitude_add": dict(steps=[5, 10, 15], cost=2.0),
        "coding_add": dict(steps=[5, 10, 15] if year >= 3 else [], cost=2.0),
        "cert_add": dict(steps=[1, 2], cost=2.0),
        "arrears_cleared": dict(steps=list(range(1, int(row["backlogs"]) + 1))[:3], cost=3.0),
    }

    def utility(r):
        u = r["score"] - 80 * max(0.0, r["prob"] - (C.RISK_MEDIUM - 0.02))
        if year >= 3:
            u += 40 * min(r["pprob"], 0.62) + (15 if r["values"]["eligible"] else 0)
        return u

    cgpa_ok = row["cgpa"] >= C.PLACEMENT_CGPA_MIN  # arrears can be cleared this term; CGPA cannot

    def done(r):
        ok = r["score"] >= target_score - 0.5 and r["prob"] < C.RISK_MEDIUM
        if year >= 3:
            ok &= r["pprob"] >= 0.6 and (bool(r["values"]["eligible"]) or not cgpa_ok)
        return ok

    plan, pos = {}, {k: 0 for k in levers}
    # Non-negotiable first step: stay eligible to write the end-semester exams
    if row["projected_attendance"] < C.ATTENDANCE_MIN and row["required_rate_for_75"] <= 100:
        need = row["required_rate_for_75"] / 100
        steps = levers["attend_rate"]["steps"]
        first = next((r for r in steps if r >= need), None)
        if first is not None:
            plan["attend_rate"] = first
            pos["attend_rate"] = steps.index(first) + 1
    start = simulate(row, models, {})
    cur = simulate(row, models, plan)
    for _ in range(max_steps):
        if done(cur):
            break
        best = None
        for k, L in levers.items():
            if pos[k] >= len(L["steps"]):
                continue
            trial = dict(plan, **{k: L["steps"][pos[k]]})
            r = simulate(row, models, trial)
            gain = (utility(r) - utility(cur)) / L["cost"]
            if best is None or gain > best[0]:
                best = (gain, k, trial, r)
        if best is None or best[0] <= 0.05:
            break
        _, k, plan, cur = best
        pos[k] += 1
    return dict(plan=plan, start=start, end=cur, reached=done(cur), steps=describe(row, plan))


def describe(row, plan):
    out = []
    for k, v in plan.items():
        if k == "attend_rate":
            out.append(f"Attend {v * 100:.0f}% of the remaining ~{row['classes_remaining']:.0f} classes "
                       f"(attendance ends at {projected_attendance(row, v):.0f}% instead of {row['projected_attendance']:.0f}%)")
        elif k == "asg_rate":
            out.append(f"Submit {v * 100:.0f}% of assignments from now on (currently {row['asg_rate'] * 100:.0f}%)")
        elif k == "lms_avg":
            out.append(f"Log in to the LMS {v:.0f}+ times a week (currently {row['lms_avg']:.1f})")
        elif k == "mock_add":
            out.append(f"Complete {v} mock interview{'s' if v > 1 else ''} (done so far: {row['mock_interviews']:.0f})")
        elif k == "aptitude_add":
            out.append(f"Raise aptitude score by {v} points through the placement cell's practice tests")
        elif k == "coding_add":
            out.append(f"Raise coding score by {v} points (weekly practice track)")
        elif k == "cert_add":
            out.append(f"Earn {v} relevant certification{'s' if v > 1 else ''} (NPTEL / industry)")
        elif k == "arrears_cleared":
            out.append(f"Clear {v} standing arrear{'s' if v > 1 else ''} in the next attempt")
    return out
