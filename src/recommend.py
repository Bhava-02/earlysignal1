"""
Recommendation engine: from forecasts and their drivers to specific actions.

Every recommendation names:
  target    the student (or segment / department when aggregated)
  action    what to do, concretely
  reason    the forecast and the drivers that triggered it, with the student's own numbers
  owner     faculty mentor, subject faculty, counsellor, training & placement cell, HOD, exam cell
  priority  Urgent (this week) / High (within 2 weeks) / Medium (this month) / Low (when possible)
  evidence  why this action: measured effect in this college's past records, or the placement model's odds
  success   what "done" looks like, so the follow-up can be checked
"""
import numpy as np
import pandas as pd

ACTION_NAMES = {
    "condonation": "Attendance condonation review", "attendance": "Attendance recovery plan",
    "counselling": "Counselling referral", "remedial": "Remedial classes", "peer": "Peer tutoring",
    "arrear_plan": "Arrear-clearing plan", "checkin": "Mentor check-in", "assignments": "Assignment catch-up",
    "rebalance": "Workload rebalance", "eligibility": "Clear arrears for placement eligibility",
    "mock": "Mock interview drive", "coding": "Coding bootcamp", "aptitude": "Aptitude crash course",
    "soft": "Soft-skills workshop", "foundation": "Placement foundation track", "peer_mentor": "Peer mentor / stretch track",
}
PRIORITY_RANK = {"Urgent": 4, "High": 3, "Medium": 2, "Low": 1}
WHEN = {"Urgent": "This week", "High": "Within 2 weeks", "Medium": "This month", "Low": "When possible"}
OWNERS = ["Faculty mentor", "Subject faculty", "Counsellor", "Training & placement cell", "HOD", "Exam cell",
          "Club coordinator"]


def evidence_lines(effects, place_odds):
    """Measured effects from the college's own past semesters (alerted students, matched by CGPA band)."""
    ev = {}
    for _, r in effects.iterrows():
        if r["action"] == "No action taken":
            continue
        ev[r["action"]] = (f"In the last two semesters, alerted students who got {r['action'].lower()} failed "
                           f"{r['fail_rate']:.0%} of the time, against {r['expected_without_action']:.0%} for similar "
                           f"students with no help (about {max(r['failures_prevented_per_100'], 0):.0f} fewer failures per 100).")
    o = place_odds
    ev["mock"] = f"Last year's graduates: each extra mock interview raised the odds of placement by {(o['mock_interviews'] - 1):.0%}."
    ev["coding"] = f"Last year's graduates: +10 coding score raised the odds of placement by {(o['best_coding'] ** 10 - 1):.0%}."
    ev["aptitude"] = f"Last year's graduates: +10 aptitude score raised the odds of placement by {(o['best_aptitude'] ** 10 - 1):.0%}."
    ev["soft"] = f"Last year's graduates: +10 soft-skills score raised the odds of placement by {(o['soft_skill_score'] ** 10 - 1):.0%}."
    ev["eligible"] = f"Last year's graduates: becoming eligible (CGPA 6.5+, no arrears) multiplied the odds of placement by about {o['eligible']:.0f}."
    ev["attendance"] = "College rule: below 75% attendance a student cannot write the end-semester exams."
    ev["early"] = "Behaviour drops first (LMS, then submissions, then attendance), marks last: a check-in now costs 15 minutes."
    return ev


def per100(effects, action):
    r = effects[effects["action"] == action]
    return float(r["failures_prevented_per_100"].iloc[0]) if len(r) else 0.0


def recommend_student(r, ctx):
    """r: one student's merged row (dict). ctx: benchmarks, evidence, thresholds. Returns a list of actions."""
    ev, B = ctx["evidence"], ctx["bench"]
    recs = []

    def add(key, action, category, owner, priority, reason, evidence, success, model, score):
        recs.append(dict(key=key, action=action, category=category, owner=owner, priority=priority,
                         when=WHEN[priority], reason=reason, evidence=evidence, success=success, model=model,
                         score=round(float(score), 1)))

    acad, back, eng = r["acad_prob"], r["backlog_prob"], r["eng_prob"]
    acad_lvl, back_lvl, eng_lvl = r["acad_risk"], r["backlog_level"], r["eng_level"]
    reasons = lambda k: "; ".join(x["text"] for x in r["reasons"].get(k, [])[:3])
    W, weeks = ctx["week"], ctx["weeks"]

    # 1. exam eligibility (attendance) comes first: it is a hard rule with a deadline
    if r["projected_attendance"] < 75:
        need = r["required_rate_for_75"]
        if need > 100:
            add("condonation", "Start the attendance condonation / medical-leave review with the HOD", "Attendance", "HOD",
                "Urgent", f"Projected to finish at {r['projected_attendance']:.0f}% attendance; even full attendance from now "
                f"cannot reach 75%.", ev["attendance"], "Decision on condonation recorded before the exam registration deadline",
                "Semester performance", 98)
        else:
            pr = "Urgent" if need >= 85 else "High"
            add("attendance", f"Attendance recovery plan: attend at least {min(100, np.ceil(need / 5) * 5):.0f}% of the "
                f"remaining ~{r['classes_remaining']:.0f} classes", "Attendance", "Faculty mentor", pr,
                f"Projected to finish at {r['projected_attendance']:.0f}% (below 75%) at the current pace of "
                f"{r['att_recent']:.0f}%; needs {need:.0f}% of the remaining classes.", ev["attendance"],
                f"Attendance back on track for 75% by week {min(W + 3, weeks)}", "Semester performance",
                70 + 25 * min(1, (75 - r["projected_attendance"]) / 25))

    # 2. sudden collapse across several signals: wellbeing first, not a warning letter
    collapse = (r["att_trend"] <= -15) and (r["lms_change"] <= -0.5 or r["asg_change"] <= -0.5)
    stressed = (r.get("stress") or 0) >= 5 and (acad >= ctx["flag"] or eng_lvl != "Low")
    if collapse or stressed:
        if collapse:
            why = (f"Sudden drop in several signals at once: attendance {r['att_trend']:+.0f} pts in 4 weeks, "
                   f"LMS activity {r['lms_change'] * 100:+.0f}%, submissions {r['asg_change'] * 100:+.0f} pts")
            if r["cgpa"] >= 7.5:
                why += f", in a student with CGPA {r['cgpa']:.2f}: this points to a personal problem, not ability"
        else:
            why = f"Rated workload stress 5 out of 5 in the student survey, and already at {max(acad, eng):.0%} risk"
        add("counselling", "Mentor conversation within 48 hours, then a counselling referral if needed", "Wellbeing",
            "Counsellor", "Urgent", why + ".", ev.get("Counselling referral", ev["early"]),
            "Student met; cause identified; attendance and LMS logins rising within 2 weeks", "Engagement drop", 95)

    # 3. academic risk with weak marks: subject help
    if acad >= ctx["flag"] and r["cia1_pct"] < 60:
        weak = r.get("weak_subjects") or []
        subj = ", ".join(f"{s['subject']} ({s['cia1']:.0f}%)" for s in weak[:2])
        pr = "Urgent" if acad_lvl == "High" else "High"
        add("remedial", f"Remedial classes in the weakest subjects{': ' + subj if subj else ''}", "Academic",
            "Subject faculty", pr, f"{acad:.0%} chance of failing a subject this semester. Drivers: {reasons('semester')}.",
            ev.get("Remedial classes", ""), f"CIA-2 at least 10 points above CIA-1 ({r['cia1_pct']:.0f}%) in those subjects",
            "Semester performance", 60 + 35 * acad)
    elif acad >= ctx["flag"] and 40 <= r["cia1_pct"] < 70 and not collapse:
        add("peer", "Peer tutoring with a Placement-Ready Star from the same class", "Academic", "Faculty mentor",
            "Medium" if acad_lvl == "Medium" else "High", f"{acad:.0%} chance of failing a subject. Drivers: {reasons('semester')}.",
            ev.get("Peer tutoring", ""), "Two tutoring sessions a week until CIA-2", "Semester performance", 45 + 30 * acad)

    # 4. backlog: arrears to clear or a new one forming
    if back >= ctx["flag"] and (r["arrears_due"] > 0 or r["backlogs"] > 0):
        n = int(max(r["arrears_due"], r["backlogs"]))
        pr = "High" if (back_lvl == "High" or r["year"] == 4) else "Medium"
        add("arrear_plan", f"Arrear-clearing plan for {n} subject(s): register for the arrear exam, 6-week revision "
            "timetable, fortnightly check by subject faculty", "Academic", "Subject faculty", pr,
            f"{back:.0%} chance of a new or uncleared arrear this semester. Drivers: {reasons('backlog')}."
            + (" Clearing arrears also restores placement eligibility." if r["year"] >= 3 and r["cgpa"] >= 6.5 else ""),
            ev.get("Remedial classes", ""), "All arrears registered; revision plan followed; cleared in the next attempt",
            "Backlog risk", 50 + 40 * back)
    elif back >= ctx["high"] and r["cia1_pct"] < 50 and not any(x["key"] == "remedial" for x in recs):
        add("remedial", "Remedial classes before CIA-2 to avoid a new arrear", "Academic", "Subject faculty", "High",
            f"{back:.0%} chance of a new arrear. Drivers: {reasons('backlog')}.", ev.get("Remedial classes", ""),
            "CIA-2 above 50% in every subject", "Backlog risk", 50 + 35 * back)

    # 5. engagement: falling behaviour before marks fall
    if eng_lvl in ("High", "Medium") and not collapse:
        pr = "High" if eng_lvl == "High" or r["segment"] == "Silent Strugglers" else "Medium"
        add("checkin", "Informal mentor check-in this week (a conversation, not a warning letter)", "Engagement",
            "Faculty mentor", pr, f"{eng:.0%} chance of a significant drop in attendance/LMS/submissions in the next "
            f"{ctx['horizon']} weeks ({eng / max(ctx['eng_base'], 1e-9):.1f}x the usual rate). Drivers: {reasons('engagement')}.",
            ev.get("Mentor meeting", ev["early"]), "LMS logins and submissions back to the student's own earlier level in 2 weeks",
            "Engagement drop", 40 + 50 * min(1, eng / max(ctx["eng_high"], 1e-9)))
    if r["asg_rate"] < 0.6 and (acad >= ctx["flag"] or eng_lvl != "Low"):
        add("assignments", f"Assignment catch-up: agree dates for the {r['asg_missing']:.0f} missing submission(s)",
            "Engagement", "Faculty mentor", "Medium",
            f"Only {r['asg_rate']:.0%} of assignments submitted so far (class average {ctx['asg_avg']:.0%}).",
            ev["early"], "All pending assignments submitted within 2 weeks", "Semester performance", 40 + 20 * (1 - r["asg_rate"]))

    # 6. busy outside class, slipping inside
    if r["segment"] == "Busy but Slipping":
        add("rebalance", "Weekly schedule with the mentor; lighter club load in the 3 weeks before CIA-2", "Academic",
            "Club coordinator", "Medium", f"{r['activities']:.0f} events/clubs in 12 months while academic health is "
            f"{r['academic']:.0f}/100.", "Keep the activities; rebalance the timing.", "CIA-2 back to CIA-1 level or better",
            "Semester performance", 45)

    # 7. placement readiness before the season
    if r["year"] >= 3:
        lvl, season = r["place_level"], r["months_left"]
        urgent = r["year"] == 4
        base_pr = "High" if urgent else "Medium"
        why_now = "placement season is on now" if urgent else f"placement season starts in about {season:.0f} months"
        if not r["eligible"] and r["cgpa"] >= 6.5:
            add("eligibility", "Clear the standing arrear(s) to become eligible for recruiters", "Placement",
                "Faculty mentor", "High", f"Not eligible today only because of {r['backlogs']:.0f} arrear(s); CGPA {r['cgpa']:.2f} "
                f"is above the 6.5 cut-off; {why_now}.", ev["eligible"], "Eligible before the next drive", "Placement readiness",
                70 if urgent else 55)
        if lvl in ("Not on track", "Almost ready"):
            pscore = (60 if urgent else 45) + 25 * (1 - r["place_prob"])
            if r["mock_interviews"] < B["mock_interviews"]:
                add("mock", f"Book {int(B['mock_interviews'] - r['mock_interviews'])} mock interview(s) in the next drive",
                    "Placement", "Training & placement cell", base_pr,
                    f"{r['mock_interviews']:.0f} mock interview(s) done; most placed seniors had {B['mock_interviews']:.0f}+; "
                    f"{r['place_prob']:.0%} chance of being placement-ready by the season ({why_now}).", ev["mock"],
                    f"{B['mock_interviews']:.0f}+ mock interviews with a rating of {B['avg_mock_rating']}+", "Placement readiness",
                    pscore + 5)
            if 0 < r["best_coding"] < B["best_coding"] or (r["best_coding"] == 0):
                add("coding", "Coding bootcamp: weekly practice track with a target score", "Placement",
                    "Training & placement cell", base_pr,
                    f"Coding score {r['best_coding']:.0f} (benchmark {B['best_coding']:.0f}; placed seniors averaged "
                    f"{ctx['placed_avg']['best_coding']:.0f}); {why_now}.", ev["coding"],
                    f"Coding score {B['best_coding']:.0f}+ in the next test", "Placement readiness", pscore + 3)
            if r["best_aptitude"] < B["best_aptitude"]:
                add("aptitude", "Aptitude crash course (quant, logical, verbal) with fortnightly tests", "Placement",
                    "Training & placement cell", base_pr if r["best_aptitude"] < B["best_aptitude"] - 10 else "Medium",
                    f"Aptitude {r['best_aptitude']:.0f} (benchmark {B['best_aptitude']:.0f}); {why_now}.", ev["aptitude"],
                    f"Aptitude {B['best_aptitude']:.0f}+ in the next test", "Placement readiness", pscore)
            if r["soft_skill_score"] < B["soft_skill_score"]:
                add("soft", "Communication and group-discussion workshop", "Placement", "Training & placement cell",
                    "Medium", f"Soft-skills score {r['soft_skill_score']:.0f} (benchmark {B['soft_skill_score']:.0f}).",
                    ev["soft"], f"Soft-skills score {B['soft_skill_score']:.0f}+ in the next assessment",
                    "Placement readiness", pscore - 8)
    elif r["year"] <= 2 and r["best_aptitude"] < B["best_aptitude"] - 10:
        add("foundation", "Join the placement foundation track (aptitude basics, one test a month)", "Placement",
            "Training & placement cell", "Low", f"Aptitude {r['best_aptitude']:.0f} vs the {B['best_aptitude']:.0f} most "
            "placed seniors reached; there is time to build it.", ev["aptitude"], "Aptitude +10 by the end of the year",
            "Placement readiness", 20)

    # 8. strong students: use them
    if r["segment"] == "Placement-Ready Stars" and not recs:
        add("peer_mentor", "Invite as a peer mentor; nominate for hackathons and dream-company prep", "Opportunity",
            "HOD", "Low", f"Success Score {r['success_score']:.0f}, low risk on every forecast.",
            "Peer tutoring helps the tutored student and keeps strong students stretched.", "Peer-mentoring hours logged",
            "All forecasts", 10)

    recs.sort(key=lambda x: (-PRIORITY_RANK[x["priority"]], -x["score"]))
    # one action per key, at most 5
    seen, out = set(), []
    for x in recs:
        if x["key"] not in seen:
            seen.add(x["key"])
            out.append(x)
    return out[:5]


def segment_playbooks(students, segments, effects, ctx_family):
    """Per segment: who they are, what is forecast, what drives it, and the actions the engine assigns most."""
    out = []
    for seg in segments:
        g = [s for s in students if s["segment"] == seg["name"]]
        if not g:
            continue
        acts = {}
        for s in g:
            for r in s["recs"]:
                a = acts.setdefault(r["key"], dict(key=r["key"], action=ACTION_NAMES.get(r["key"], r["action"]),
                                                   owner=r["owner"], n=0, urgent=0, category=r["category"]))
                a["n"] += 1
                a["urgent"] += r["priority"] in ("Urgent", "High")
        drv = {}
        for s in g:
            fams = {ctx_family.get(x["feature"], x["feature"])
                    for k in ("semester", "backlog", "engagement", "placement") for x in (s["pred"][k]["reasons"] or [])[:2]}
            for lab in fams:
                drv[lab] = drv.get(lab, 0) + 1
        top_acts = sorted(acts.values(), key=lambda a: (-a["urgent"], -a["n"]))[:4]
        n = len(g)
        out.append(dict(
            name=seg["name"], color=seg["color"], rule=seg["rule"], why=seg["why"], owner=seg["owner"], kpi=seg["kpi"],
            students=n,
            forecast=dict(fail=float(np.mean([s["pred"]["semester"]["p"] for s in g])),
                          backlog=float(np.mean([s["pred"]["backlog"]["p"] for s in g])),
                          engagement=float(np.mean([s["pred"]["engagement"]["p"] for s in g])),
                          ready=float(np.mean([s["pred"]["placement"]["level"] == "On track" for s in g if s["year"] >= 3]))
                          if any(s["year"] >= 3 for s in g) else None),
            drivers=[dict(label=k, students=v) for k, v in sorted(drv.items(), key=lambda x: -x[1])[:5]],
            actions=top_acts))
    return out


def dept_priorities(students, effects, depts):
    """Which intervention to prioritise per department: students needing it x urgency x measured effect."""
    eff = {"remedial": per100(effects, "Remedial classes"), "counselling": per100(effects, "Counselling referral"),
           "checkin": per100(effects, "Mentor meeting"), "peer": per100(effects, "Peer tutoring")}
    out = {}
    for d in ["All"] + list(depts):
        g = students if d == "All" else [s for s in students if s["dept"] == d]
        acts = {}
        for s in g:
            for r in s["recs"]:
                if r["category"] == "Opportunity":
                    continue
                a = acts.setdefault(r["key"], dict(key=r["key"], action=ACTION_NAMES.get(r["key"], r["action"]), owner=r["owner"],
                                                   category=r["category"], students=0, urgent=0, weight=0.0))
                a["students"] += 1
                a["urgent"] += r["priority"] in ("Urgent", "High")
                a["weight"] += PRIORITY_RANK[r["priority"]]
        for a in acts.values():
            a["prevented"] = round(a["students"] * eff.get(a["key"], 0) / 100, 1) if a["key"] in eff else None
            a["value"] = a["weight"] * (1 + eff.get(a["key"], 0) / 20)
        out[d] = sorted(acts.values(), key=lambda a: -a["value"])[:6]
    return out
