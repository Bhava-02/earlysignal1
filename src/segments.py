"""
Rule-based student segments. Rules (not k-means) on purpose: faculty need groups that are
stable, explainable in one sentence, and tied to a specific action.
A student gets the first segment whose rule matches, in priority order.
"""
import numpy as np
import pandas as pd

SEGMENTS = [
    dict(name="Critical: Act This Week", color="#B42318",
         rule="High academic risk AND at least two of: projected attendance below 75%, falling LMS/assignment activity, 2+ arrears, CIA-1 below 40%",
         why="Multiple warning signs at once; likely to fail or be detained without help.",
         actions=["Mentor meeting within 48 hours", "Counselling referral if attendance or stress is the driver",
                  "Remedial classes in the weakest subjects", "Inform parents only after the student is heard"],
         owner="Mentor + HOD", kpi="Back above 75% attendance and submitting work within 3 weeks"),
    dict(name="Silent Strugglers", color="#C4320A",
         rule="Marks, attendance and arrears still look fine, but at least two behaviour signals are falling (LMS logins, assignment submissions, attendance trend)",
         why="Marks and attendance lists will not catch them for weeks. Behaviour is already slipping.",
         actions=["Informal mentor check-in this week (not a warning letter)", "Ask about workload, health, family",
                  "Pair with a peer study group", "Re-check LMS activity in 2 weeks"],
         owner="Mentor", kpi="LMS logins and submissions back to their own earlier level"),
    dict(name="Book-smart, Job-shy", color="#B54708",
         rule="3rd/4th year, Academic Health 65+ but placement risk Medium/High",
         why="Strong academics but not converting to placement readiness; easiest wins for placement numbers.",
         actions=["Enrol in the next mock-interview drive (biggest measured effect)", "Weekly coding practice track",
                  "Resume review", "Aptitude crash course if aptitude < 60"],
         owner="Placement cell", kpi="2+ mock interviews and coding score +10 within 6 weeks"),
    dict(name="Busy but Slipping", color="#7A5AF8",
         rule="Top 25% in events/clubs AND (Academic Health below 55 or academic risk Medium/High)",
         why="Highly involved outside class; academics are paying the price. Don't take the activities away; rebalance.",
         actions=["Mentor helps plan a weekly schedule", "Club coordinator agrees lighter load near exams",
                  "Targeted support in the 1-2 weakest subjects"],
         owner="Mentor + club coordinator", kpi="CIA-2 marks back to CIA-1 level or better"),
    dict(name="Academic Catch-up", color="#DC6803",
         rule="Academic risk Medium/High with a weak academic record (CGPA below 6.5, arrears, or CIA-1 below 50%)",
         why="Not a sudden change; the gap has been building. Needs subject help and an arrear-clearing plan, not a pep talk.",
         actions=["Remedial classes in the 1-2 weakest subjects (best measured effect on marks)",
                  "Peer tutoring with a Placement-Ready Star", "Arrear-clearing plan with dates",
                  "Fortnightly progress check by subject faculty"],
         owner="Subject faculty + mentor", kpi="CIA-2 at least 10 points above CIA-1; arrears cleared next attempt"),
    dict(name="Placement-Ready Stars", color="#067647",
         rule="Academic Health 65+ and Placement Readiness 65+ (2nd years: Success Score 70+)",
         why="On track. Keep them stretched and use them as peer mentors.",
         actions=["Invite to dream-company prep track", "Peer mentor for Silent Strugglers in their class",
                  "Nominate for hackathons and internships"],
         owner="Placement cell + HOD", kpi="Dream/core offers; peer-mentoring hours"),
    dict(name="Steady Middle", color="#475467",
         rule="Everyone else",
         why="No urgent flags. Small, regular nudges keep them from drifting.",
         actions=["Monthly mentor group meeting", "Share the attendance and assignment dashboard with them",
                  "Open invitation to mock interviews and certifications"],
         owner="Mentor", kpi="Stay On Track or move up a band"),
]
ORDER = ["Critical: Act This Week", "Silent Strugglers", "Busy but Slipping", "Academic Catch-up",
         "Book-smart, Job-shy", "Placement-Ready Stars", "Steady Middle"]
SEGMENTS = sorted(SEGMENTS, key=lambda s: ORDER.index(s["name"]))
SEG = {s["name"]: s for s in SEGMENTS}


def assign(df):
    act_q75 = df["activities"].quantile(0.75)
    looks_fine = (df["att_pct"] >= 75) & (df["cia1_pct"] >= 55) & (df["backlogs"] == 0)
    declining = (df["lms_change"] <= -0.25) | (df["asg_change"] <= -0.2) | (df["att_trend"] <= -6)
    risky = df["acad_risk"].isin(["High", "Medium"])
    weak_record = (df["cgpa"] < 6.5) | (df["backlogs"] >= 1) | (df["cia1_pct"] < 50)
    rules = {
        "Critical: Act This Week": (df["acad_risk"] == "High") & (
            ((df["projected_attendance"] < 75).astype(int) + declining.astype(int) + (df["backlogs"] >= 2).astype(int)
             + (df["cia1_pct"] < 40).astype(int)) >= 2),
        "Silent Strugglers": looks_fine & (((df["lms_change"] <= -0.3).astype(int) + (df["asg_change"] <= -0.2).astype(int)
                                            + (df["att_trend"] <= -6).astype(int)) >= 2),
        "Busy but Slipping": (df["activities"] >= max(act_q75, 3)) & ((df["academic"] < 55) | risky),
        "Academic Catch-up": risky & weak_record,
        "Book-smart, Job-shy": (df["year"] >= 3) & (df["academic"] >= 65) & df["placement_risk"].isin(["High", "Medium"]),
        "Placement-Ready Stars": ((df["year"] >= 3) & (df["academic"] >= 65) & (df["placement"] >= 65))
                                 | ((df["year"] <= 2) & (df["success_score"] >= 70)),
    }
    return pd.Series(np.select([rules[n] for n in ORDER[:-1]], ORDER[:-1], default=ORDER[-1]), index=df.index)
