"""
Student Success Score (0-100) = weighted blend of three sub-scores:

  Academic Health      CGPA, CIA-1 marks, attendance, standing arrears, faculty rating
  Engagement           LMS logins, assignment completion, momentum (recent trend),
                       co-curricular activity, student satisfaction
  Placement Readiness  aptitude, coding, mock interviews (count + rating), technical
                       and soft skills, certifications, recruiter eligibility

Each indicator is scaled to 0-1 against fixed, explainable bounds (e.g. attendance 60%->0, 100%->1),
so a score means the same thing for every student and every semester.
Sub-score weights shift by year of study (placement matters more in final year).
Placement indicator weights are learned from last year's placement outcomes.

Because the score is a weighted sum, it splits exactly into per-indicator
contributions (points above / below the average student of the same year).
"""
import numpy as np
import pandas as pd

from . import config as C

# key, sub-score, label, low bound, high bound, invert, weight, years it applies to
INDICATORS = [
    ("cgpa", "academic", "CGPA", 5.0, 9.5, False, 0.30, (1, 2, 3, 4)),
    ("cia1_pct", "academic", "CIA-1 marks (this semester)", 30, 90, False, 0.25, (1, 2, 3, 4)),
    ("att_pct", "academic", "Attendance (this semester)", 60, 100, False, 0.20, (1, 2, 3, 4)),
    ("backlogs", "academic", "Standing arrears", 0, 4, True, 0.15, (1, 2, 3, 4)),
    ("faculty_rating", "academic", "Faculty participation rating", 1, 5, False, 0.10, (1, 2, 3, 4)),
    ("lms_avg", "engagement", "LMS logins / week", 0, 6, False, 0.20, (1, 2, 3, 4)),
    ("asg_rate", "engagement", "Assignment completion", 0.4, 1.0, False, 0.30, (1, 2, 3, 4)),
    ("momentum", "engagement", "Momentum (last 3-4 weeks)", -0.6, 0.6, False, 0.20, (1, 2, 3, 4)),
    ("activities", "engagement", "Events, clubs & hackathons (12 mo)", 0, 6, False, 0.15, (1, 2, 3, 4)),
    ("satisfaction", "engagement", "Satisfaction & feeling supported", 1, 5, False, 0.15, (1, 2, 3, 4)),
    ("best_aptitude", "placement", "Aptitude score", 30, 90, False, None, (1, 2, 3, 4)),
    ("best_coding", "placement", "Coding score", 20, 90, False, None, (3, 4)),
    ("mock_interviews", "placement", "Mock interviews done", 0, 4, False, None, (3, 4)),
    ("avg_mock_rating", "placement", "Mock interview rating", 1, 5, False, None, (3, 4)),
    ("technical_score", "placement", "Technical skills", 30, 90, False, None, (1, 2, 3, 4)),
    ("soft_skill_score", "placement", "Soft skills", 30, 90, False, None, (1, 2, 3, 4)),
    ("certifications", "placement", "Certifications", 0, 3, False, None, (1, 2, 3, 4)),
    ("eligible", "placement", "Recruiter eligibility (CGPA & arrears)", 0, 1, False, 0.15, (1, 2, 3, 4)),
]
IND = {i[0]: i for i in INDICATORS}
SUB_LABEL = {"academic": "Academic Health", "engagement": "Engagement", "placement": "Placement Readiness"}


def placement_weights(coef):
    """Turn the placement model's standardised coefficients into indicator weights (sum 0.85 + eligibility 0.15)."""
    keys = [k for k, *_ in INDICATORS if IND[k][1] == "placement" and k != "eligible"]
    c = coef.reindex(keys).clip(lower=0.02)
    return (0.85 * c / c.sum()).to_dict()


def weight_table(pl_weights):
    """Effective weight of every indicator for each year of study (all weights for a year sum to 1)."""
    out = {}
    for year, subw in C.SCORE_WEIGHTS.items():
        w = {}
        for sub in SUB_LABEL:
            items = [(k, pl_weights.get(k, IND[k][6]) if IND[k][6] is None else IND[k][6])
                     for k, *_ in INDICATORS if IND[k][1] == sub and year in IND[k][7]]
            tot = sum(v for _, v in items)
            for k, v in items:
                w[k] = subw[sub] * v / tot
        out[year] = w
    return out


def normalise(df):
    N = pd.DataFrame(index=df.index)
    for k, sub, label, lo, hi, inv, *_ in INDICATORS:
        x = ((df[k] - lo) / (hi - lo)).clip(0, 1)
        N[k] = 1 - x if inv else x
    return N


def compute_scores(df, pl_weights):
    """df: one row per student with raw indicator columns + `year` + `<key>_missing` flags."""
    wt = weight_table(pl_weights)
    N = normalise(df)
    out = pd.DataFrame(index=df.index)
    contrib = pd.DataFrame(0.0, index=df.index, columns=[k for k, *_ in INDICATORS])
    for year, w in wt.items():
        idx = df.index[df["year"] == year]
        if not len(idx):
            continue
        for sub in SUB_LABEL:
            keys = [k for k in w if IND[k][1] == sub]
            tot = sum(w[k] for k in keys)
            out.loc[idx, sub] = 100 * sum(N.loc[idx, k] * w[k] for k in keys) / tot
        out.loc[idx, "success_score"] = 100 * sum(N.loc[idx, k] * w[k] for k in w)
        means = N.loc[idx, list(w)].mean()
        for k in w:
            contrib.loc[idx, k] = 100 * w[k] * (N.loc[idx, k] - means[k])
        avail = sum(w[k] * (~df.loc[idx, f"{k}_missing"]).astype(float) for k in w)
        out.loc[idx, "confidence"] = 100 * avail
    out["band"] = pd.cut(out["success_score"], bins=[-1, 40, 55, 70, 101],
                         labels=["At Risk", "Needs Attention", "On Track", "Thriving"]).astype(str)
    out["confidence_label"] = np.select([out["confidence"] >= 90, out["confidence"] >= 75], ["High", "Medium"], "Low")
    return out, contrib, N, wt


def score_one(values, year, pl_weights, cohort_means=None):
    """Recompute the Success Score for a single (possibly what-if) set of indicator values."""
    w = weight_table(pl_weights)[year]
    total, subs = 0.0, {}
    for sub in SUB_LABEL:
        keys = [k for k in w if IND[k][1] == sub]
        tot = sum(w[k] for k in keys)
        s = 0.0
        for k in keys:
            _, _, _, lo, hi, inv, *_ = IND[k]
            x = min(max((values[k] - lo) / (hi - lo), 0), 1)
            x = 1 - x if inv else x
            s += w[k] * x
            total += w[k] * x
        subs[sub] = 100 * s / tot
    return 100 * total, subs
