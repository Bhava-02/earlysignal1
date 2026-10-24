"""
Two explainable models.

1. Early-warning model (academic risk): logistic regression on weekly behaviour,
   trained on past semesters and back-tested on a semester it never saw.
   One model per week of the semester, so it only ever uses data that existed by then.

2. Placement-readiness model: logistic regression trained on last year's
   graduating batch (who actually got placed). Its coefficients also set the
   weights of the Placement Readiness part of the Success Score.

Logistic regression was chosen over black-box models on purpose: every flag can be
broken into exact per-indicator contributions that a mentor can read.
"""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C
from .features import snapshot

BASE_FEATS = ["att_pct", "att_trend", "lms_avg", "lms_change", "asg_rate", "asg_change", "prior_cgpa", "backlogs"]
CIA_FEATS = ["cia1_pct", "cia1_absent"]
FEAT_LABELS = {
    "att_pct": "Attendance so far", "att_trend": "Attendance trend (last 4 weeks)",
    "lms_avg": "LMS logins per week", "lms_change": "Change in LMS activity (last 3 weeks)",
    "asg_rate": "Assignment completion", "asg_change": "Change in assignment completion",
    "prior_cgpa": "CGPA before this semester", "backlogs": "Standing arrears",
    "cia1_pct": "CIA-1 average", "cia1_absent": "CIA-1 papers missed",
}


def feats_for(week):
    return BASE_FEATS + (CIA_FEATS if week >= C.CIA1_RESULTS_WEEK else [])


def frame(panel, hist, semester, week):
    X = snapshot(panel, semester, week)
    h = hist[hist["semester"] == semester].set_index("roll_no")
    cols = ["prior_cgpa", "backlogs", "cia1_pct", "cia1_absent"] + (["acad_fail"] if "acad_fail" in h and h["acad_fail"].notna().any() else [])
    return X.join(h[cols], how="right")


def fit(X, y):
    m = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))
    m.fit(X, y)
    return m


def best_threshold(y, p):
    best, thr = -1, 0.5
    for t in np.arange(0.15, 0.8, 0.01):
        pred = p >= t
        tp = (pred & (y == 1)).sum()
        prec = tp / max(pred.sum(), 1)
        rec = tp / max((y == 1).sum(), 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-9)
        if f1 > best:
            best, thr = f1, t
    return float(round(thr, 2))


def traditional_rule(X, week):
    """What most colleges do today: the attendance-shortage list, plus the slow-learner list after CIA-1 marks."""
    flag = X["att_pct"] < C.ATTENDANCE_MIN
    if week >= C.CIA1_RESULTS_WEEK:
        flag |= X["cia1_pct"] < 50
    return flag


def contributions(model, X, feats):
    """Exact per-feature contribution to the log-odds of risk, relative to an average student."""
    imp, sc, lr = model.named_steps.values()
    Z = sc.transform(imp.transform(X[feats]))
    return pd.DataFrame(Z * lr.coef_[0], index=X.index, columns=feats)


# ---------------------------------------------------------------- academic early warning
def backtest(panel, hist, weeks=range(3, 13)):
    train_sem, test_sem = C.TRAIN_SEM, C.TEST_SEM
    rows, flags_model, flags_rule = [], {}, {}
    for w in weeks:
        f = feats_for(w)
        tr, te = frame(panel, hist, train_sem, w), frame(panel, hist, test_sem, w)
        m = fit(tr[f], tr["acad_fail"])
        thr = C.RISK_MEDIUM  # "flagged" = Medium or High risk, the same rule the live dashboard uses
        p = m.predict_proba(te[f])[:, 1]
        y = te["acad_fail"].values
        pred = p >= thr
        rule = traditional_rule(te, w).values
        flags_model[w] = pd.Series(pred, index=te.index)
        flags_rule[w] = pd.Series(rule, index=te.index)

        def pr(pr_):
            tp = (pr_ & (y == 1)).sum()
            return tp / max((y == 1).sum(), 1), tp / max(pr_.sum(), 1)

        rec, prec = pr(pred)
        rrec, rprec = pr(rule)
        rows.append(dict(week=w, auc=roc_auc_score(y, p), recall=rec, precision=prec, flagged_pct=pred.mean(),
                         rule_recall=rrec, rule_precision=rprec, rule_flagged_pct=rule.mean(), threshold=thr))
    curve = pd.DataFrame(rows)
    te = frame(panel, hist, test_sem, 7)
    y = te["acad_fail"]
    fm, fr = pd.DataFrame(flags_model), pd.DataFrame(flags_rule)
    first_model = fm.apply(lambda r: r.idxmax() if r.any() else np.nan, axis=1)
    first_rule = fr.apply(lambda r: r.idxmax() if r.any() else 13, axis=1)  # otherwise: CIA-2 marks in week 13
    fails = y[y == 1].index
    both = [i for i in fails if not np.isnan(first_model[i])]
    lead = float(np.mean([first_rule[i] - first_model[i] for i in both])) if both else 0.0
    # failures the traditional lists never caught by week 9: they "looked fine" on attendance and marks
    looked_fine = fr.loc[fails][~fr.loc[fails, [c for c in fr.columns if c <= 9]].any(axis=1)].index
    by6 = lambda F: float(F.loc[fails, [c for c in F.columns if c <= 6]].any(axis=1).mean())
    summary = dict(
        train_semester=train_sem, test_semester=test_sem, students_tested=int(len(te)), eventual_failures=int(len(fails)),
        recall_by_week6=by6(fm), rule_recall_by_week6=by6(fr),
        recall_by_week9=float(fm.loc[fails, [c for c in fm.columns if c <= 9]].any(axis=1).mean()),
        rule_recall_by_week9=float(fr.loc[fails, [c for c in fr.columns if c <= 9]].any(axis=1).mean()),
        avg_weeks_earlier_than_rule=round(lead, 1),
        silent_strugglers=int(len(looked_fine)),
        silent_caught_by_week9=float(fm.loc[looked_fine, [c for c in fm.columns if c <= 9]].any(axis=1).mean()) if len(looked_fine) else 0.0,
        auc_week6=float(curve.loc[curve.week == 6, "auc"].iloc[0]), auc_week9=float(curve.loc[curve.week == 9, "auc"].iloc[0]),
        precision_week9=float(curve.loc[curve.week == 9, "precision"].iloc[0]),
        rule_precision_week9=float(curve.loc[curve.week == 9, "rule_precision"].iloc[0]),
    )
    detail = pd.DataFrame({"failed": y, "model_first_week": first_model, "rule_first_week": first_rule,
                           "model_flag_w9": fm[9], "rule_flag_w9": fr[9]})
    return curve, summary, detail


def live_risk(panel, hist):
    """Train on both past semesters, score the current semester week by week."""
    probs, flags, models = {}, {}, {}
    for w in range(3, C.CURRENT_WEEK + 1):
        f = feats_for(w)
        tr = pd.concat([frame(panel, hist, C.TRAIN_SEM, w), frame(panel, hist, C.TEST_SEM, w)])
        m = fit(tr[f], tr["acad_fail"])
        thr = C.RISK_MEDIUM
        cur = frame(panel, hist, C.CURRENT_SEM, w)
        probs[w] = pd.Series(m.predict_proba(cur[f])[:, 1], index=cur.index)
        flags[w] = probs[w] >= thr
        models[w] = (m, thr)
    P, F = pd.DataFrame(probs), pd.DataFrame(flags)
    m, thr = models[C.CURRENT_WEEK]
    f = feats_for(C.CURRENT_WEEK)
    cur = frame(panel, hist, C.CURRENT_SEM, C.CURRENT_WEEK)
    contrib = contributions(m, cur, f)
    coefs = pd.Series(m.named_steps["logisticregression"].coef_[0], index=f)
    return dict(probs=P, flags=F, threshold=thr, model=m, features=f, current=cur, contrib=contrib, coefs=coefs)


# ---------------------------------------------------------------- placement readiness
PL_FEATS = ["best_aptitude", "best_coding", "mock_interviews", "avg_mock_rating", "technical_score",
            "soft_skill_score", "certifications", "eligible"]
PL_LABELS = {"best_aptitude": "Aptitude score", "best_coding": "Coding score", "mock_interviews": "Mock interviews done",
             "avg_mock_rating": "Mock interview rating", "technical_score": "Technical skills",
             "soft_skill_score": "Soft skills", "certifications": "Certifications", "eligible": "Recruiter eligibility"}


def prep_alumni(al):
    a = al.copy()
    a["eligible"] = ((a["final_cgpa"] >= C.PLACEMENT_CGPA_MIN) & (a["standing_backlogs"] <= C.PLACEMENT_MAX_BACKLOGS)).astype(int)
    a["avg_mock_rating"] = a["avg_mock_rating"].fillna(2.5)
    a["y"] = (a["placed"] == "Yes").astype(int)
    return a


def placement_model(alumni):
    a = prep_alumni(alumni)
    m = fit(a[PL_FEATS], a["y"])
    sd = a[PL_FEATS].std()
    coef = pd.Series(m.named_steps["logisticregression"].coef_[0], index=PL_FEATS)
    odds_per_unit = np.exp(coef / sd)
    placed_avg = a[a["y"] == 1][PL_FEATS].mean()
    auc = roc_auc_score(a["y"], m.predict_proba(a[PL_FEATS])[:, 1])
    return dict(model=m, coef=coef, odds_per_unit=odds_per_unit, placed_avg=placed_avg, auc=float(auc), n_alumni=len(a),
                placement_rate=float(a["y"].mean()), eligible_rate=float(a["eligible"].mean()),
                placed_rate_eligible=float(a.loc[a["eligible"] == 1, "y"].mean()),
                placed_rate_ineligible=float(a.loc[a["eligible"] == 0, "y"].mean()))
