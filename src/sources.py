"""The source files EarlySignal reads, what each must contain, and which are optional."""
import pandas as pd

# file name -> label, system it comes from, required?, columns that must be present, what is lost if missing
SOURCES = {
    "01_sis_student_master.csv": dict(
        label="Student list", system="Student information system / ERP", required=True,
        cols=["Roll No", "Student Name", "Gender", "Dept", "Batch", "Year", "Sec", "Residence", "First Graduate",
              "Mentor", "HSC %", "Official Email"],
        missing="Nothing works without the list of students."),
    "02_exam_cell_results.csv": dict(
        label="Exam results", system="Exam cell", required=True,
        cols=["register_no", "student_name", "sem_label", "semester_no", "subject_code", "subject_name", "cia1", "cia2",
              "end_sem", "grade", "attempt"],
        missing="Needed for CGPA, arrears, internal marks and to learn who failed in past semesters."),
    "03_attendance_weekly.csv": dict(
        label="Weekly attendance", system="Attendance system", required=True,
        cols=["RollNo", "semester", "week", "subject_code", "classes_held", "classes_attended"],
        missing="Needed for attendance, shortage warnings and the weekly risk model."),
    "04a_lms_users.csv": dict(
        label="LMS accounts", system="Online learning portal (LMS)", required=False,
        cols=["lms_user_id", "login_email", "display_name", "enrolled_courses"],
        missing="LMS logins and assignment trends are left out; early warnings rely on attendance and marks only."),
    "04b_lms_weekly_activity.csv": dict(
        label="LMS weekly activity", system="Online learning portal (LMS)", required=False,
        cols=["lms_user_id", "semester", "week", "logins", "minutes", "assignments_due", "assignments_submitted",
              "quiz_attempts"],
        missing="LMS logins and assignment trends are left out."),
    "05_student_affairs_events.csv": dict(
        label="Events, clubs and certifications", system="Student affairs office", required=False,
        cols=["event_month", "event_type", "event_name", "participant_name", "department", "year_of_study"],
        missing="Co-curricular activity and certifications count as unknown."),
    "06_placement_training_scores.csv": dict(
        label="Placement training scores", system="Placement cell / training vendor", required=False,
        cols=["candidate_id", "test_type", "attempt_month", "score"],
        missing="Aptitude, coding and mock interviews count as unknown; placement readiness is less reliable."),
    "07_skills_assessment.csv": dict(
        label="Skills tests", system="Skills assessment platform", required=False,
        cols=["student_ref", "technical_score", "soft_skill_score", "assessed_on"],
        missing="Technical and soft-skill scores count as unknown."),
    "08a_faculty_feedback.csv": dict(
        label="Faculty feedback", system="Faculty feedback portal", required=False,
        cols=["student", "subject_code", "participation_rating", "remark", "given_in_week"],
        missing="Faculty ratings count as unknown."),
    "08b_student_survey.csv": dict(
        label="Student survey", system="Feedback form", required=False,
        cols=["respondent_email", "course_satisfaction", "feels_supported", "workload_stress", "submitted_week"],
        missing="Student satisfaction counts as unknown."),
    "09_intervention_log_past.csv": dict(
        label="Past actions taken", system="Mentor records", required=False,
        cols=["roll_no", "semester", "week", "action", "owner"],
        missing="'What works' cannot be measured until actions are logged in the app."),
    "10_alumni_placement_outcomes.csv": dict(
        label="Last year's placement results", system="Placement cell", required=False,
        cols=["alumni_id", "dept", "final_cgpa", "standing_backlogs", "best_aptitude", "best_coding", "technical_score",
              "soft_skill_score", "mock_interviews", "avg_mock_rating", "certifications", "internship", "placed",
              "offer_tier"],
        missing="Placement predictions fall back to the built-in sample history until your own is uploaded."),
}


NUMERIC = {"week", "logins", "minutes", "assignments_due", "assignments_submitted", "quiz_attempts", "technical_score",
           "soft_skill_score", "participation_rating", "given_in_week", "course_satisfaction", "feels_supported",
           "workload_stress", "submitted_week", "semester_no", "cia2", "end_sem", "attempt", "classes_held",
           "classes_attended", "final_cgpa", "standing_backlogs", "best_aptitude", "best_coding", "mock_interviews",
           "avg_mock_rating", "certifications", "internship", "Batch", "Year", "HSC %"}


def read_source(raw_dir, name, **kw):
    """Read a source file, or return an empty table with the right columns if it was not provided."""
    p = raw_dir / name
    if p.exists():
        return pd.read_csv(p, **kw), True
    if SOURCES[name]["required"]:
        raise FileNotFoundError(f"Required file missing: {name} ({SOURCES[name]['label']}). "
                                f"{SOURCES[name]['missing']}")
    return pd.DataFrame({c: pd.Series(dtype="float64" if c in NUMERIC else "object")
                         for c in SOURCES[name]["cols"]}), False


def detect(df):
    """Guess which source a table is, from its columns. Returns (file name, missing columns) or (None, None)."""
    cols = set(map(str, df.columns))
    best, score = None, 0.0
    for name, s in SOURCES.items():
        need = set(s["cols"])
        hit = len(cols & need) / len(need)
        if hit > score:
            best, score = name, hit
    if score < 0.5:
        return None, None
    return best, [c for c in SOURCES[best]["cols"] if c not in cols]
