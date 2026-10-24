"""
Round 2: Predict, Prioritise & Intervene.

Four forecasts per student, each validated on data the model never saw and compared with the Round 1
Success Score as a baseline:

  1. Semester performance  chance of failing a subject this semester (pass/fail) + expected SGPA band
  2. Backlog risk          chance of a NEW arrear this semester, or of NOT clearing last semester's arrear
  3. Engagement drop       chance of a significant fall in attendance or LMS activity in the next 3 weeks
  4. Placement readiness   chance of being placement-ready when the placement season starts

Every model is a regularised linear model on standardised inputs, so each forecast splits exactly into
per-signal contributions ("drivers") that a mentor can read.
"""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C
from .features import GP, snapshot
from .models import BASE_FEATS, CIA_FEATS, FEAT_LABELS, PL_FEATS, PL_LABELS, fit, prep_alumni
from .scoring import compute_scores

FLAG = C.RISK_MEDIUM          # "flagged" = Medium or High, the same rule for every risk model
HIGH = C.RISK_HIGH
LABELS = dict(FEAT_LABELS, arrears_due="Arrears from last semester to clear", week="Week of semester")
SGPA_BANDS = [(8.5, "8.5 and above"), (7.5, "7.5 to 8.4"), (6.0, "6.0 to 7.4"), (-1, "Below 6.0")]
DROP_HORIZON = 3              # engagement drop: look this many weeks ahead
ENG_WEEKS = range(4, 13)      # weeks used to train / test the engagement model (needs 3 weeks ahead)


def level(p):
    return "High" if p >= HIGH else ("Medium" if p >= FLAG else "Low")


def sgpa_band(x):
    return next(lbl for lo, lbl in SGPA_BANDS if x >= lo)


# ---------------------------------------------------------------- targets
def semester_targets(exams, sis):
    """Per student and tracked semester: new arrears, last semester's arrears to clear and whether they stayed."""
    ex = exams.copy()
    ex["gp"] = ex["grade"].map(GP)
    s_ = sis.set_index("roll_no")
    cur_no = 2 * s_["year"] - 1
    if "current_sem_no" in s_:
        cur_no = s_["current_sem_no"].fillna(cur_no)
    ex["rel"] = ex["semester_no"] - ex["roll_no"].map(cur_no)
    first = ex[(ex["attempt"] == 1) & ex["grade"].notna()]
    cleared = set(map(tuple, ex.loc[ex["attempt"] > 1, ["roll_no", "subject_code"]].values))
    rows = []
    for k, sem in enumerate(C.SEMESTERS):
        target = k - (len(C.SEMESTERS) - 1)
        d = pd.DataFrame(index=pd.Index(sis["roll_no"], name="roll_no"))
        d["semester"] = sem
        due = first[(first["rel"] == target - 1) & (first["gp"] == 0)]
        d["arrears_due"] = due.groupby("roll_no").size().reindex(d.index).fillna(0)
        if sem != C.CURRENT_SEM:
            new = first[(first["rel"] == target) & (first["gp"] == 0)].groupby("roll_no").size()
            d["new_arrears"] = new.reindex(d.index).fillna(0)
            stuck = due[[(r, c) not in cleared for r, c in due[["roll_no", "subject_code"]].values]]
            d["not_cleared"] = stuck.groupby("roll_no").size().reindex(d.index).fillna(0)
            d["backlog_event"] = ((d["new_arrears"] > 0) | (d["not_cleared"] > 0)).astype(int)
        rows.append(d.reset_index())
    return pd.concat(rows, ignore_index=True)


def make_frame(panel, hist, targ, semester, week):
    """Signals known by the end of `week` + history + outcomes (for finished semesters)."""
    X = snapshot(panel, semester, week)
    h = hist[hist["semester"] == semester].set_index("roll_no")
    t = targ[targ["semester"] == semester].set_index("roll_no").drop(columns="semester")
    cols = [c for c in ["prior_cgpa", "backlogs", "cia1_pct", "cia1_absent", "acad_fail", "sgpa", "fails"] if c in h]
    return X.join(h[cols], how="right").join(t)


def engagement_labels(panel, semester, week, horizon=DROP_HORIZON):
    """1 = a significant, sustained drop: over the next `horizon` weeks, at least 2 of these 3 happen, each measured
    against the student's OWN level so far: attendance down 12+ points, LMS logins halved, assignment
    submissions down 40+ points. (One bad week of one signal is normal noise and is not counted.)"""
    p = panel[panel["semester"] == semester]
    past, fut = p[p["week"] <= week], p[(p["week"] > week) & (p["week"] <= week + horizon)]
    g0, g1 = past.groupby("roll_no"), fut.groupby("roll_no")
    att0 = 100 * g0["classes_attended"].sum() / g0["classes_held"].sum().replace(0, np.nan)
    att1 = 100 * g1["classes_attended"].sum() / g1["classes_held"].sum().replace(0, np.nan)
    lms0, lms1 = g0["logins"].mean(), g1["logins"].mean()
    s0 = g0["assignments_submitted"].sum() / g0["assignments_due"].sum().replace(0, np.nan)
    s1 = g1["assignments_submitted"].sum() / g1["assignments_due"].sum().replace(0, np.nan)
    n = ((att1 <= att0 - 12).fillna(False).astype(int) + ((lms0 >= 1.0) & (lms1 <= 0.5 * lms0)).fillna(False).astype(int)
         + (s1 <= s0 - 0.4).fillna(False).astype(int))
    return (n >= 2).astype(int).reindex(att0.index).fillna(0).astype(int)


# ---------------------------------------------------------------- the Round 1 Success Score as a baseline
def historical_score(S, panel, hist, plw, semester, week):
    """The Round 1 Success Score as it would have read at `week` of `semester` (behaviour + record of that time)."""
    X = snapshot(panel, semester, week).reindex(S.index)
    h = hist[hist["semester"] == semester].set_index("roll_no").reindex(S.index)
    T = S.copy()
    T["att_pct"] = X["att_pct"].fillna(S["att_pct"])
    T["lms_avg"] = X["lms_avg"].fillna(S["lms_avg"])
    T["asg_rate"] = X["asg_rate"].fillna(S["asg_rate"])
    T["momentum"] = (0.4 * X["lms_change"] + 0.8 * X["asg_change"] + 0.02 * X["att_trend"]).clip(-1, 1).fillna(0)
    T["cgpa"] = h["prior_cgpa"].fillna(S["cgpa"])
    T["backlogs"] = h["backlogs"].fillna(0)
    T["cia1_pct"] = h["cia1_pct"] if week >= C.CIA1_RESULTS_WEEK else S.groupby("year")["cia1_pct"].transform("median")
    T["cia1_pct"] = T["cia1_pct"].fillna(S["cia1_pct"].median())
    T["eligible"] = ((T["cgpa"] >= C.PLACEMENT_CGPA_MIN) & (T["backlogs"] <= C.PLACEMENT_MAX_BACKLOGS)).astype(float)
    sc, *_ = compute_scores(T, plw)
    return sc["success_score"]


# ---------------------------------------------------------------- metrics
def cls_metrics(y, p, thr=FLAG):
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    pred = p >= thr
    return dict(auc=float(roc_auc_score(y, p)), accuracy=float(accuracy_score(y, pred)),
                precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), f1=float(f1_score(y, pred, zero_division=0)),
                flagged=int(pred.sum()), positives=int(y.sum()), n=int(len(y)), threshold=thr)


def baseline_same_volume(y, score, n_flag):
    """Round 1 baseline: flag the same number of students, lowest Success Score first."""
    y = np.asarray(y).astype(int)
    s = pd.Series(np.asarray(score, dtype=float))
    pred = np.zeros(len(y), dtype=bool)
    if n_flag > 0:
        pred[s.rank(method="first").values <= n_flag] = True
    return dict(auc=float(roc_auc_score(y, -s.values)), accuracy=float(accuracy_score(y, pred)),
                precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), f1=float(f1_score(y, pred, zero_division=0)),
                flagged=int(pred.sum()))


def rule_metrics(y, pred):
    y, pred = np.asarray(y).astype(int), np.asarray(pred).astype(bool)
    return dict(accuracy=float(accuracy_score(y, pred)), precision=float(precision_score(y, pred, zero_division=0)),
                recall=float(recall_score(y, pred, zero_division=0)), f1=float(f1_score(y, pred, zero_division=0)),
                flagged=int(pred.sum()))


def params_of(model, feats):
    """Everything needed to re-run a fitted pipeline in the browser (what-if) and to explain it."""
    steps = list(model.named_steps.values())
    imp, sc, est = steps[0], steps[1], steps[2]
    coef = est.coef_[0] if est.coef_.ndim > 1 else est.coef_
    icpt = est.intercept_[0] if np.ndim(est.intercept_) else est.intercept_
    return dict(features=list(feats), median=[float(v) for v in imp.statistics_], mean=[float(v) for v in sc.mean_],
                scale=[float(v) for v in sc.scale_], coef=[float(v) for v in coef], intercept=float(icpt))


def drivers_of(model, X, feats):
    steps = list(model.named_steps.values())
    imp, sc, est = steps[0], steps[1], steps[2]
    coef = est.coef_[0] if est.coef_.ndim > 1 else est.coef_
    Z = sc.transform(imp.transform(X[feats]))
    return pd.DataFrame(Z * coef, index=X.index, columns=feats)


def global_drivers(model, X, feats):
    con = drivers_of(model, X, feats)
    steps = list(model.named_steps.values())
    coef = steps[2].coef_[0] if steps[2].coef_.ndim > 1 else steps[2].coef_
    imp = con.abs().mean()
    tot = imp.sum() or 1
    return [dict(feature=f, label=LABELS.get(f, PL_LABELS.get(f, f)), weight=float(c), importance=float(imp[f] / tot),
                 direction="raises" if c > 0 else "lowers") for f, c in sorted(zip(feats, coef), key=lambda x: -imp[x[0]])]


# ---------------------------------------------------------------- reasons in plain words
def reason(feat, v, kind="risk"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    t = {
        "att_pct": f"Attendance {v:.0f}% so far",
        "att_trend": f"Attendance {'fell' if v < 0 else 'rose'} {abs(v):.0f} pts in the last 4 weeks",
        "lms_avg": f"{v:.1f} LMS logins a week",
        "lms_change": f"LMS activity {'down' if v < 0 else 'up'} {abs(v) * 100:.0f}% in the last 3 weeks",
        "asg_rate": f"{v * 100:.0f}% of assignments submitted",
        "asg_change": f"Assignment submissions {'down' if v < 0 else 'up'} {abs(v) * 100:.0f} pts recently",
        "prior_cgpa": f"CGPA {v:.2f} before this semester",
        "backlogs": f"{v:.0f} standing arrear(s)",
        "arrears_due": f"{v:.0f} arrear(s) from last semester still to clear",
        "cia1_pct": f"CIA-1 average {v:.0f}%",
        "cia1_absent": f"Missed {v:.0f} CIA-1 paper(s)",
        "week": f"Week {v:.0f} of the semester",
    }.get(feat)
    return t


def top_reasons(con_row, raw_row, sign=1, k=3, cut=0.2):
    r = (sign * con_row).sort_values(ascending=False)
    out = []
    for f, v in r.items():
        if v <= cut or len(out) >= k:
            break
        txt = reason(f, raw_row.get(f))
        if txt:
            out.append(dict(feature=f, text=txt, impact=round(float(v), 2)))
    return out


# ---------------------------------------------------------------- 1. semester performance
def semester_performance(panel, hist, targ, S, plw):
    W = C.CURRENT_WEEK
    f = BASE_FEATS + (CIA_FEATS if W >= C.CIA1_RESULTS_WEEK else [])
    tr = make_frame(panel, hist, targ, C.TRAIN_SEM, W)
    te = make_frame(panel, hist, targ, C.TEST_SEM, W)
    m = fit(tr[f], tr["acad_fail"])
    p = m.predict_proba(te[f])[:, 1]
    met = cls_metrics(te["acad_fail"], p)
    base_score = historical_score(S, panel, hist, plw, C.TEST_SEM, W).reindex(te.index)
    base = baseline_same_volume(te["acad_fail"], base_score.fillna(base_score.median()), met["flagged"])
    rule = te["att_pct"] < C.ATTENDANCE_MIN
    if W >= C.CIA1_RESULTS_WEEK:
        rule |= te["cia1_pct"] < 50
    usual = rule_metrics(te["acad_fail"], rule)
    # recall week by week (who was caught by then), model vs Success Score at equal volume
    curve = []
    for w in range(3, W + 1):
        fw = BASE_FEATS + (CIA_FEATS if w >= C.CIA1_RESULTS_WEEK else [])
        trw, tew = make_frame(panel, hist, targ, C.TRAIN_SEM, w), make_frame(panel, hist, targ, C.TEST_SEM, w)
        mw = fit(trw[fw], trw["acad_fail"])
        pw = mw.predict_proba(tew[fw])[:, 1]
        cm = cls_metrics(tew["acad_fail"], pw)
        bs = historical_score(S, panel, hist, plw, C.TEST_SEM, w).reindex(tew.index)
        cb = baseline_same_volume(tew["acad_fail"], bs.fillna(bs.median()), cm["flagged"])
        curve.append(dict(week=w, model_recall=cm["recall"], baseline_recall=cb["recall"], model_auc=cm["auc"],
                          baseline_auc=cb["auc"]))
    # live: train on both finished semesters
    live_tr = pd.concat([tr, te])
    lm = fit(live_tr[f], live_tr["acad_fail"])
    cur = make_frame(panel, hist, targ, C.CURRENT_SEM, W)
    con = drivers_of(lm, cur, f)

    # expected SGPA (regression) and its band
    ok_tr, ok_te = tr["sgpa"].notna(), te["sgpa"].notna()
    reg = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=1.0))
    reg.fit(tr.loc[ok_tr, f], tr.loc[ok_tr, "sgpa"])
    pr = reg.predict(te.loc[ok_te, f])
    yt = te.loc[ok_te, "sgpa"].values
    bands_t, bands_p = [sgpa_band(v) for v in yt], [sgpa_band(v) for v in pr]
    order = [b for _, b in SGPA_BANDS]
    within1 = np.mean([abs(order.index(a) - order.index(b)) <= 1 for a, b in zip(bands_t, bands_p)])
    naive = te.loc[ok_te, "prior_cgpa"].values
    bs_tr = historical_score(S, panel, hist, plw, C.TRAIN_SEM, W).reindex(tr.index)
    bs_te = historical_score(S, panel, hist, plw, C.TEST_SEM, W).reindex(te.index)
    lin = np.polyfit(bs_tr[ok_tr].fillna(bs_tr.median()), tr.loc[ok_tr, "sgpa"], 1)
    via_score = np.polyval(lin, bs_te[ok_te].fillna(bs_te.median()))
    sg_met = dict(mae=float(mean_absolute_error(yt, pr)), rmse=float(np.sqrt(mean_squared_error(yt, pr))),
                  band_accuracy=float(np.mean(np.array(bands_t) == np.array(bands_p))), within_one_band=float(within1),
                  n=int(ok_te.sum()),
                  baseline_cgpa_mae=float(mean_absolute_error(yt, naive)),
                  baseline_score_mae=float(mean_absolute_error(yt, via_score)),
                  baseline_cgpa_band_accuracy=float(np.mean(np.array(bands_t) == np.array([sgpa_band(v) for v in naive]))))
    lreg = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=1.0))
    lreg.fit(live_tr.loc[live_tr["sgpa"].notna(), f], live_tr.loc[live_tr["sgpa"].notna(), "sgpa"])
    sg_live = pd.Series(np.clip(lreg.predict(cur[f]), 0, 10), index=cur.index)
    sg_con = drivers_of(lreg, cur, f)
    return dict(
        features=f, model=lm, current=cur, prob=pd.Series(lm.predict_proba(cur[f])[:, 1], index=cur.index),
        contrib=con, metrics=met, baseline=base, usual=usual, curve=curve, drivers=global_drivers(lm, cur, f),
        params=params_of(lm, f),
        sgpa=dict(pred=sg_live, contrib=sg_con, metrics=sg_met, params=params_of(lreg, f), rmse=sg_met["rmse"],
                  drivers=global_drivers(lreg, cur, f)))


# ---------------------------------------------------------------- 2. backlog risk
def backlog_risk(panel, hist, targ, S, plw):
    W = C.CURRENT_WEEK
    feats = lambda w: BASE_FEATS + ["arrears_due"] + (CIA_FEATS if w >= C.CIA1_RESULTS_WEEK else [])
    f = feats(W)
    tr, te = make_frame(panel, hist, targ, C.TRAIN_SEM, W), make_frame(panel, hist, targ, C.TEST_SEM, W)
    m = fit(tr[f], tr["backlog_event"])
    p = m.predict_proba(te[f])[:, 1]
    met = cls_metrics(te["backlog_event"], p)
    bs = historical_score(S, panel, hist, plw, C.TEST_SEM, W).reindex(te.index)
    base = baseline_same_volume(te["backlog_event"], bs.fillna(bs.median()), met["flagged"])
    rule = (te["backlogs"] > 0) | (te["cia1_pct"] < 50) if W >= C.CIA1_RESULTS_WEEK else (te["backlogs"] > 0)
    usual = rule_metrics(te["backlog_event"], rule)
    live = pd.concat([tr, te])
    weekly = {}
    for w in range(3, W + 1):
        fw = feats(w)
        lw = pd.concat([make_frame(panel, hist, targ, C.TRAIN_SEM, w), make_frame(panel, hist, targ, C.TEST_SEM, w)])
        mw = fit(lw[fw], lw["backlog_event"])
        cw = make_frame(panel, hist, targ, C.CURRENT_SEM, w)
        weekly[w] = pd.Series(mw.predict_proba(cw[fw])[:, 1], index=cw.index)
    lm = fit(live[f], live["backlog_event"])
    cur = make_frame(panel, hist, targ, C.CURRENT_SEM, W)
    return dict(features=f, model=lm, current=cur, prob=weekly[W], weekly=pd.DataFrame(weekly),
                contrib=drivers_of(lm, cur, f), metrics=met, baseline=base, usual=usual,
                drivers=global_drivers(lm, cur, f), params=params_of(lm, f),
                event_rate=float(te["backlog_event"].mean()))


# ---------------------------------------------------------------- 3. engagement drop
ENG_FEATS = BASE_FEATS + ["lms_last2", "att_last2", "asg_last2", "week"]
LABELS.update(lms_last2="LMS logins in the last 2 weeks vs own average", att_last2="Attendance in the last 2 weeks vs own average",
              asg_last2="Assignments submitted in the last 2 weeks")


def recent_signals(panel, semester, week):
    """The freshest signals: the last 2 weeks compared with the student's own level so far."""
    p = panel[(panel["semester"] == semester) & (panel["week"] <= week)]
    last = p[p["week"] > week - 2]
    g, gl = p.groupby("roll_no"), last.groupby("roll_no")
    out = pd.DataFrame(index=g.size().index)
    out["lms_last2"] = (gl["logins"].mean() - g["logins"].mean()) / (g["logins"].mean() + 1)
    att_all = 100 * g["classes_attended"].sum() / g["classes_held"].sum().replace(0, np.nan)
    att_l = 100 * gl["classes_attended"].sum() / gl["classes_held"].sum().replace(0, np.nan)
    out["att_last2"] = (att_l - att_all).fillna(0)
    due, sub = gl["assignments_due"].sum(), gl["assignments_submitted"].sum()
    out["asg_last2"] = (sub / due.replace(0, np.nan))
    return out


def eng_frame(panel, hist, targ, semester, w):
    X = make_frame(panel, hist, targ, semester, w).join(recent_signals(panel, semester, w))
    X["week"] = w
    return X


def _eng_stack(panel, hist, targ, semester, weeks):
    parts = []
    for w in weeks:
        X = eng_frame(panel, hist, targ, semester, w)
        X["drop"] = engagement_labels(panel, semester, w).reindex(X.index).fillna(0).astype(int)
        X["wk"] = w
        parts.append(X)
    return pd.concat(parts)


def engagement_drop(panel, hist, targ, S, plw):
    W = C.CURRENT_WEEK
    f = ENG_FEATS
    tr = _eng_stack(panel, hist, targ, C.TRAIN_SEM, ENG_WEEKS)
    te = _eng_stack(panel, hist, targ, C.TEST_SEM, ENG_WEEKS)
    m = fit(tr[f], tr["drop"])
    # a rarer event (about 1 in 7) needs a lower cut-off: pick the one that maximises F2 (recall counts double)
    # on the TRAINING semester, then apply it unchanged to the test semester
    thr = best_f2_threshold(tr["drop"], m.predict_proba(tr[f])[:, 1])
    p = m.predict_proba(te[f])[:, 1]
    met = cls_metrics(te["drop"], p, thr)
    # at the current week only (the question a mentor asks today)
    at_w = (te["wk"] == W).values
    met_w = cls_metrics(te.loc[at_w, "drop"], p[at_w], thr)
    bs = historical_score(S, panel, hist, plw, C.TEST_SEM, W).reindex(te[at_w].index)
    base = baseline_same_volume(te.loc[at_w, "drop"], bs.fillna(bs.median()), met_w["flagged"])
    declining = (te["lms_change"] <= -0.25) | (te["asg_change"] <= -0.2) | (te["att_trend"] <= -6)
    usual = rule_metrics(te.loc[at_w, "drop"], declining[at_w])
    both = pd.concat([tr, te])
    lm = fit(both[f], both["drop"])
    weekly = {}
    for w in range(4, W + 1):
        X = eng_frame(panel, hist, targ, C.CURRENT_SEM, w)
        weekly[w] = pd.Series(lm.predict_proba(X[f])[:, 1], index=X.index)
    cur = eng_frame(panel, hist, targ, C.CURRENT_SEM, W)
    return dict(features=f, model=lm, current=cur, prob=weekly[W], weekly=pd.DataFrame(weekly),
                contrib=drivers_of(lm, cur, f), metrics=met_w, metrics_all_weeks=met, baseline=base, usual=usual,
                drivers=global_drivers(lm, cur, f), params=params_of(lm, f), event_rate=float(te.loc[at_w, "drop"].mean()),
                horizon=DROP_HORIZON, threshold=thr, high=max(0.25, round(2.5 * thr, 2)))


def best_f2_threshold(y, p):
    y = np.asarray(y).astype(int)
    best, thr = -1, 0.3
    for t in np.arange(0.08, 0.6, 0.01):
        pred = p >= t
        tp = (pred & (y == 1)).sum()
        prec, rec = tp / max(pred.sum(), 1), tp / max(y.sum(), 1)
        f2 = 5 * prec * rec / max(4 * prec + rec, 1e-9)
        if f2 > best:
            best, thr = f2, float(round(t, 2))
    return thr


# ---------------------------------------------------------------- 4. placement readiness before the season
def placement_readiness(alumni, S, placement_raw):
    a = prep_alumni(alumni)
    y_risk = 1 - a["y"]   # positive class = at risk of NOT being placement-ready
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    mk = lambda: make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(),
                               LogisticRegression(C=0.5, max_iter=1000))
    p_cv = cross_val_predict(mk(), a[PL_FEATS], a["y"], cv=cv, method="predict_proba")[:, 1]
    ready_thr = 0.6
    met = cls_metrics(y_risk, 1 - p_cv, thr=1 - ready_thr)
    met["auc"] = float(roc_auc_score(a["y"], p_cv))
    p_cg = cross_val_predict(mk(), a[["final_cgpa"]], a["y"], cv=cv, method="predict_proba")[:, 1]
    base_cgpa = dict(auc=float(roc_auc_score(a["y"], p_cg)), **rule_metrics(y_risk, p_cg < ready_thr))
    elig = rule_metrics(y_risk, a["eligible"] == 0)
    m = mk().fit(a[PL_FEATS], a["y"])

    # benchmarks: what most placed seniors had reached (their 40th percentile), rounded
    placed = a[a["y"] == 1]
    r5 = lambda x: float(5 * round(x / 5))
    bench = dict(best_aptitude=r5(placed["best_aptitude"].quantile(0.4)),
                 best_coding=r5(placed["best_coding"].quantile(0.4)),
                 mock_interviews=float(max(1, round(placed["mock_interviews"].quantile(0.4)))),
                 avg_mock_rating=round(float(placed.loc[placed["mock_interviews"] > 0, "avg_mock_rating"].quantile(0.4)), 1),
                 soft_skill_score=r5(placed["soft_skill_score"].quantile(0.4)))

    # projection to the season start, assuming the current training schedule continues
    pl = placement_raw.copy()
    gains = {}
    for t, key in [("Aptitude", "apt"), ("Coding", "cod")]:
        g = pl[pl["test_type"] == t].sort_values("attempt_month").groupby("roll_no")["score_num"]
        per = (g.last() - g.first()) / (g.count() - 1).replace(0, np.nan)
        gains[key] = per
    med_apt = float(np.nanmedian(gains["apt"])) if len(gains["apt"].dropna()) else 2.0
    med_cod = float(np.nanmedian(gains["cod"])) if len(gains["cod"].dropna()) else 2.0
    months_left = S["year"].map({4: 0, 3: 9, 2: 21, 1: 33}).fillna(9)
    attempts_left = (months_left / 2).clip(upper=4)
    apt_gain = gains["apt"].reindex(S.index).fillna(med_apt).clip(0, 6)
    cod_gain = gains["cod"].reindex(S.index).fillna(med_cod).clip(0, 6)
    P = S[PL_FEATS].copy().astype(float)
    P["best_aptitude"] = np.minimum(99, P["best_aptitude"] + np.minimum(15, apt_gain * attempts_left))
    has_cod = S["best_coding"] > 0
    P["best_coding"] = np.where(has_cod, np.minimum(99, P["best_coding"] + np.minimum(15, cod_gain * attempts_left)),
                                P["best_coding"])
    P["avg_mock_rating"] = np.where(S["mock_interviews"] > 0, S["avg_mock_rating"], 2.5)
    P["eligible"] = S["eligible"].fillna(0)
    prob = pd.Series(m.predict_proba(P[PL_FEATS])[:, 1], index=S.index)
    prob_now = pd.Series(m.predict_proba(S[PL_FEATS].assign(
        avg_mock_rating=np.where(S["mock_interviews"] > 0, S["avg_mock_rating"], 2.5),
        eligible=S["eligible"].fillna(0)))[:, 1], index=S.index)
    con = drivers_of(m, P, PL_FEATS)
    return dict(model=m, prob=prob, prob_now=prob_now, projected=P, contrib=con, benchmarks=bench,
                metrics=met, baseline_cgpa=base_cgpa, baseline_eligibility=elig, ready_threshold=ready_thr,
                drivers=global_drivers(m, a, PL_FEATS), params=params_of(m, PL_FEATS), months_left=months_left,
                n_alumni=int(len(a)), placed_rate=float(a["y"].mean()),
                gains=dict(aptitude_median_per_attempt=med_apt, coding_median_per_attempt=med_cod))


def placement_level(prob, eligible, year):
    if year <= 2:
        return "Early stage"
    if not eligible or prob < 0.35:
        return "Not on track"
    return "Almost ready" if prob < 0.6 else "On track"


def run(d, hist, panel, S, plw, lr, pm):
    targ = semester_targets(d["exams"], d["sis"])
    sp = semester_performance(panel, hist, targ, S, plw)
    bk = backlog_risk(panel, hist, targ, S, plw)
    en = engagement_drop(panel, hist, targ, S, plw)
    pr = placement_readiness(d["alumni"], S, d["placement"])
    return dict(targets=targ, semester=sp, backlog=bk, engagement=en, placement=pr)
