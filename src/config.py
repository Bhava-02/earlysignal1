"""Central settings for EarlySignal. Change values here, not inside the code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RAW_DIR = ROOT / "data" / "raw"
RAW_DIR = SAMPLE_RAW_DIR
PROC_DIR = ROOT / "data" / "processed"
SETTINGS_FILE = ROOT / "data" / "settings.json"

APP_NAME = "EarlySignal"
TAGLINE = "Smarter insights. Brighter futures."
COLLEGE_NAME = "Sample Engineering College"

# Demo sign-ins for the prototype (not real security): email -> (password, display name, role, department scope)
DEMO_USERS = {
    "admin@college.edu.in": ("admin123", "Admin", "Principal / Admin", None),
    "hod.cse@college.edu.in": ("hod123", "Dr. R. Lakshmi", "HOD, CSE", "CSE"),
}

SEED = 42
COLLEGE_CODE = "4127"
EMAIL_DOMAIN = "college.edu.in"

# short name: (full name, university dept code, roll-number code, students per batch)
DEPTS = {
    "CSE": ("Computer Science & Engineering", "104", "CS", 120),
    "IT": ("Information Technology", "205", "IT", 90),
    "ECE": ("Electronics & Communication Engineering", "106", "EC", 90),
    "MECH": ("Mechanical Engineering", "114", "ME", 60),
}

# admission year -> current year of study (academic year 2026-27, odd semester running)
BATCHES = {2023: 4, 2024: 3, 2025: 2}

# Semesters with weekly data. The last one is the semester running now.
SEMESTERS = ["2025-ODD", "2026-EVEN", "2026-ODD"]
TRAIN_SEM, TEST_SEM, CURRENT_SEM = SEMESTERS
CURRENT_WEEK = 9          # we are in week 9 of 16
WEEKS_PER_SEM = 16
CIA1_RESULTS_WEEK = 7     # CIA-1 held in week 6, marks visible from week 7
SUBJECTS_PER_SEM = 5

# Campus rules
ATTENDANCE_MIN = 75.0       # below this a student is not eligible to write end-semester exams
PLACEMENT_CGPA_MIN = 6.5    # typical recruiter eligibility cut-off
PLACEMENT_MAX_BACKLOGS = 0  # most recruiters require no standing arrears

# Success Score weights by year of study: placement matters more as placement season nears
SCORE_WEIGHTS = {
    1: {"academic": 0.50, "engagement": 0.30, "placement": 0.20},
    2: {"academic": 0.50, "engagement": 0.30, "placement": 0.20},
    3: {"academic": 0.40, "engagement": 0.25, "placement": 0.35},
    4: {"academic": 0.35, "engagement": 0.20, "placement": 0.45},
}

# Academic risk levels = estimated chance of failing at least one subject this semester
RISK_HIGH = 0.60
RISK_MEDIUM = 0.30

# Score bands shown on the dashboard
BANDS = [(70, "Thriving"), (55, "On Track"), (40, "Needs Attention"), (0, "At Risk")]


# the sample college's own settings, kept so the demo server can always be built from them
_SAMPLE = dict(RAW_DIR=RAW_DIR, COLLEGE_NAME=COLLEGE_NAME, COLLEGE_CODE=COLLEGE_CODE, EMAIL_DOMAIN=EMAIL_DOMAIN,
               SEMESTERS=list(SEMESTERS), TRAIN_SEM=TRAIN_SEM, TEST_SEM=TEST_SEM, CURRENT_SEM=CURRENT_SEM,
               CURRENT_WEEK=CURRENT_WEEK, WEEKS_PER_SEM=WEEKS_PER_SEM, DEPTS=dict(DEPTS))


class sample_mode:
    """with C.sample_mode(): ...  temporarily uses the sample college's settings (whatever data is loaded now)."""

    def __enter__(self):
        g = globals()
        self.saved = {k: g[k] for k in _SAMPLE}
        g.update(_SAMPLE)

    def __exit__(self, *exc):
        globals().update(self.saved)


# ---------------------------------------------------------------- college's own settings (saved from the Upload page)
def _apply_settings():
    global RAW_DIR, COLLEGE_CODE, EMAIL_DOMAIN, SEMESTERS, TRAIN_SEM, TEST_SEM, CURRENT_SEM, CURRENT_WEEK, DEPTS, \
        COLLEGE_NAME, WEEKS_PER_SEM
    if not SETTINGS_FILE.exists():
        return
    import json
    try:
        s = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return
    if s.get("raw_dir"):
        RAW_DIR = Path(s["raw_dir"])
    COLLEGE_NAME = s.get("college_name", COLLEGE_NAME)
    COLLEGE_CODE = str(s.get("college_code", COLLEGE_CODE))
    EMAIL_DOMAIN = s.get("email_domain", EMAIL_DOMAIN)
    if s.get("semesters") and len(s["semesters"]) == 3:
        SEMESTERS = list(s["semesters"])
        TRAIN_SEM, TEST_SEM, CURRENT_SEM = SEMESTERS
    CURRENT_WEEK = int(s.get("current_week", CURRENT_WEEK))
    WEEKS_PER_SEM = int(s.get("weeks_per_sem", WEEKS_PER_SEM))
    if s.get("depts"):
        DEPTS = {k: tuple(v) for k, v in s["depts"].items()}


_apply_settings()
