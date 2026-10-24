"""
Read student data straight from the college's own servers, read-only.

How colleges actually store it:
  * the ERP (fees, admissions, attendance, internal marks, results) runs on MySQL / MariaDB, PostgreSQL,
    Microsoft SQL Server or Oracle, usually on a campus server or a cloud VM run by the ERP vendor;
  * the LMS (Moodle in most colleges) has its own database (MySQL or PostgreSQL);
  * attendance is stored per class hour (one row per student per period, P / A / OD) and marks per subject.

EarlySignal asks each database a few SELECT queries (written once by the college's IT team for their table
names; defaults below fit a typical ERP and Moodle), turns dated rows into semester + week using the academic
calendar, and hands the result to the same checks and pipeline as the Excel upload.

Safety: only single SELECT / WITH statements are allowed, the connection is opened read-only where the
database supports it, passwords are never written to disk, and only the columns needed are read.
"""
import json
import re
import time

import numpy as np
import pandas as pd

from . import config as C
from . import simple_upload as su

CONN_FILE = C.ROOT / "data" / "connection.json"
TZ = "Asia/Kolkata"

DIALECTS = {  # label: (SQLAlchemy driver, default port, pip package)
    "MySQL / MariaDB": ("mysql+pymysql", 3306, "pymysql"),
    "PostgreSQL": ("postgresql+psycopg2", 5432, "psycopg2-binary"),
    "Microsoft SQL Server": ("mssql+pymssql", 1433, "pymssql"),
    "Oracle": ("oracle+oracledb", 1521, "oracledb"),
    "SQLite file": ("sqlite", None, None),
}

# slot: (which server, template sheet it feeds, needed?, what it is, default SQL for a typical ERP / Moodle)
SLOTS = {
    "students": ("erp", "Students", True, "Active students, with department and current semester", """
SELECT s.roll_no, s.full_name AS name, d.dept_code AS department, s.current_semester, s.section, s.gender,
       CASE WHEN s.hostel_flag = 'Y' THEN 'Hostel' ELSE 'Day Scholar' END AS residence,
       CASE WHEN s.first_graduate = 'Y' THEN 'Yes' ELSE 'No' END AS first_graduate,
       m.staff_name AS mentor, s.email, s.hsc_percentage AS hsc
FROM students s
JOIN departments d ON d.department_id = s.department_id
LEFT JOIN staff m ON m.staff_id = s.mentor_staff_id
WHERE s.status = 'ACTIVE'"""),
    "calendar": ("erp", None, True, "Academic calendar: when each semester starts", """
SELECT term_name, start_date, end_date
FROM academic_terms
ORDER BY start_date"""),
    "marks": ("erp", "Marks", True, "Internal tests, end-semester marks and grades", """
SELECT s.roll_no, sb.semester, sb.subject_code, sb.subject_name, m.cia1, m.cia1_status, m.cia2, m.end_sem,
       m.grade, m.attempt_no AS attempt
FROM exam_marks m
JOIN students s ON s.student_id = m.student_id
JOIN subjects sb ON sb.subject_id = m.subject_id"""),
    "attendance": ("erp", "Attendance", True, "Period-wise attendance, counted per day", """
SELECT s.roll_no, a.class_date, sb.subject_code, COUNT(*) AS classes_held,
       SUM(CASE WHEN a.status IN ('P', 'OD') THEN 1 ELSE 0 END) AS classes_attended
FROM attendance a
JOIN students s ON s.student_id = a.student_id
JOIN subjects sb ON sb.subject_id = a.subject_id
GROUP BY s.roll_no, a.class_date, sb.subject_code"""),
    "lms_users": ("lms", "LMS", False, "Moodle accounts (idnumber holds the roll number)", """
SELECT idnumber AS roll_no
FROM mdl_user
WHERE deleted = 0 AND idnumber <> ''"""),
    "lms_logins": ("lms", "LMS", False, "Moodle log-in events", """
SELECT u.idnumber AS roll_no, l.timecreated
FROM mdl_logstore_standard_log l
JOIN mdl_user u ON u.id = l.userid
WHERE l.eventname LIKE '%user_loggedin'"""),
    "lms_assignments": ("lms", "LMS", False, "Moodle assignments: due date and whether submitted", """
SELECT u.idnumber AS roll_no, a.duedate, s.status
FROM mdl_assign_submission s
JOIN mdl_assign a ON a.id = s.assignment
JOIN mdl_user u ON u.id = s.userid
WHERE s.latest = 1"""),
    "placement": ("erp", "Other details", False, "Placement training: aptitude, coding, mock interviews", """
SELECT s.roll_no,
       MAX(CASE WHEN p.test_type = 'Aptitude' THEN p.score END) AS aptitude_score,
       MAX(CASE WHEN p.test_type = 'Coding' THEN p.score END) AS coding_score,
       SUM(CASE WHEN p.test_type = 'Mock Interview' THEN 1 ELSE 0 END) AS mock_interviews_done,
       AVG(CASE WHEN p.test_type = 'Mock Interview' THEN 1.0 * p.score END) AS mock_interview_rating
FROM placement_training p
JOIN students s ON s.student_id = p.student_id
GROUP BY s.roll_no"""),
    "skills": ("erp", "Other details", False, "Skills assessment scores", """
SELECT s.roll_no, MAX(k.technical_score) AS technical_skill_score, MAX(k.soft_skill_score) AS soft_skill_score
FROM skill_assessments k
JOIN students s ON s.student_id = k.student_id
GROUP BY s.roll_no"""),
    "activities": ("erp", "Other details", False, "Events, clubs, hackathons and certifications", """
SELECT s.roll_no,
       SUM(CASE WHEN a.activity_type NOT IN ('Certification', 'Hackathon') THEN 1 ELSE 0 END) AS events_and_clubs,
       SUM(CASE WHEN a.activity_type = 'Hackathon' THEN 1 ELSE 0 END) AS hackathons,
       SUM(CASE WHEN a.activity_type = 'Certification' THEN 1 ELSE 0 END) AS certifications
FROM student_activities a
JOIN students s ON s.student_id = a.student_id
GROUP BY s.roll_no"""),
    "feedback": ("erp", "Other details", False, "Faculty participation ratings", """
SELECT s.roll_no, AVG(1.0 * f.participation_rating) AS faculty_rating, MIN(f.remark) AS faculty_remark
FROM faculty_feedback f
JOIN students s ON s.student_id = f.student_id
GROUP BY s.roll_no"""),
    "survey": ("erp", "Other details", False, "Student satisfaction survey", """
SELECT s.roll_no, AVG(1.0 * v.course_satisfaction) AS course_satisfaction,
       AVG(1.0 * v.feels_supported) AS feels_supported, AVG(1.0 * v.workload_stress) AS workload_stress
FROM student_survey v
JOIN students s ON s.student_id = v.student_id
GROUP BY s.roll_no"""),
    "past_actions": ("erp", "Past actions", False, "Mentor actions already taken (dated)", """
SELECT s.roll_no, ma.action_date, ma.action, ma.done_by
FROM mentor_actions ma
JOIN students s ON s.student_id = ma.student_id"""),
    "past_placements": ("erp", "Past placements", False, "Last year's graduates and who got placed", """
SELECT a.roll_no AS student_id, d.dept_code AS department, a.final_cgpa, a.standing_arrears,
       a.aptitude_score, a.coding_score, a.technical_score AS technical_skill_score, a.soft_skill_score,
       a.mock_interviews AS mock_interviews_done, a.mock_rating AS mock_interview_rating, a.certifications,
       CASE WHEN a.internship = 'Y' THEN 'Yes' ELSE 'No' END AS internship,
       CASE WHEN a.placed = 'Y' THEN 'Yes' ELSE 'No' END AS placed
FROM alumni_placements a
LEFT JOIN departments d ON d.department_id = a.department_id"""),
}
DEFAULT_SQL = {k: v[4].strip() for k, v in SLOTS.items()}


# ---------------------------------------------------------------- safety
FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|exec|execute|call|into|"
                       r"attach|detach|pragma|copy|lock|vacuum|load_file|outfile)\b", re.I)


def check_sql(sql):
    """Only one SELECT (or WITH ... SELECT) statement. Returns the cleaned SQL or raises ValueError."""
    s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    s = re.sub(r"--[^\n]*", " ", s).strip().rstrip(";").strip()
    if not s:
        raise ValueError("The query is empty.")
    if ";" in s:
        raise ValueError("Only one statement is allowed (remove the ';').")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise ValueError("Only SELECT queries are allowed. EarlySignal never changes your data.")
    bad = FORBIDDEN.search(re.sub(r"'[^']*'", "''", s))  # ignore words inside quoted text
    if bad:
        raise ValueError(f"'{bad.group(1).upper()}' is not allowed. EarlySignal only reads data.")
    return s


# ---------------------------------------------------------------- connections
def engine(cfg, password=""):
    """cfg: dict(dialect, host, port, database, username) or dict(dialect='SQLite file', database=path)."""
    try:
        import sqlalchemy as sa
    except ImportError as e:
        raise RuntimeError("The database library is missing. Run: pip install sqlalchemy") from e
    driver, port, pkg = DIALECTS[cfg["dialect"]]
    if driver == "sqlite":
        import sqlite3
        path = cfg["database"]
        return sa.create_engine("sqlite://", creator=lambda: sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                                                                              check_same_thread=False))
    url = sa.engine.URL.create(driver, username=cfg.get("username") or None, password=password or None,
                               host=cfg.get("host") or None, port=int(cfg.get("port") or port),
                               database=cfg.get("database") or None)
    kw = {"pool_pre_ping": True}
    if driver.startswith("postgresql"):
        kw["connect_args"] = {"options": "-c default_transaction_read_only=on", "connect_timeout": 10}
    elif driver.startswith("mysql"):
        kw["connect_args"] = {"connect_timeout": 10}
    try:
        eng = sa.create_engine(url, **kw)
    except ModuleNotFoundError as e:
        raise RuntimeError(f"The driver for {cfg['dialect']} is not installed. Run: pip install {pkg}") from e
    if driver.startswith("mysql"):
        @sa.event.listens_for(eng, "connect")
        def _ro(dbapi_con, _):  # noqa: ANN001
            with dbapi_con.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
    return eng


def test(cfg, password=""):
    """Connect and list tables. Returns (ok, message, tables)."""
    try:
        import sqlalchemy as sa
        eng = engine(cfg, password)
        with eng.connect() as con:
            names = sa.inspect(con).get_table_names()
        eng.dispose()
        return True, f"Connected. {len(names)} tables found.", names
    except Exception as e:  # show the reason in plain words
        return False, friendly(e), []


def preview(cfg, password, sql, n=15):
    """Run one SELECT on the server and return its first n rows: (DataFrame or None, seconds, problem or None)."""
    t0 = time.time()
    try:
        from sqlalchemy import text
        sql = check_sql(sql)
        eng = engine(cfg, password)
        with eng.connect() as con:
            df = next(iter(pd.read_sql(text(sql), con, chunksize=n)), pd.DataFrame())
        eng.dispose()
        return df, round(time.time() - t0, 2), None
    except Exception as e:  # show the reason in plain words
        return None, round(time.time() - t0, 2), friendly(e)


def friendly(e):
    msg = str(e).split("\n")[0]
    low = msg.lower()
    if "password" in low or "access denied" in low or "authentication" in low:
        return "The username or password was not accepted. " + msg[:160]
    if "could not connect" in low or "timed out" in low or "connection refused" in low or "can't connect" in low \
            or "name or service not known" in low:
        return ("The server could not be reached. Check the address and port, and that this machine is allowed "
                "through the college firewall or VPN. " + msg[:160])
    return msg[:300]


BIG = {"attendance", "lms_logins", "lms_assignments"}  # can be millions of rows: read in chunks, stored compactly


def _compact(df):
    """Text columns become categories and date text becomes dates, so a million rows take a few MB."""
    for c in df.columns:
        col = df[c]
        if pd.api.types.is_numeric_dtype(col):
            if pd.api.types.is_integer_dtype(col):
                df[c] = pd.to_numeric(col, downcast="integer")
            continue
        k = su.key(c)
        if "date" in k or "time" in k:
            d = pd.to_datetime(col, errors="coerce")
            if d.notna().any():
                df[c] = d
                continue
        df[c] = col.astype("category")
    return df


def _read_big(con, sql, text):
    from pandas.api.types import union_categoricals
    chunks = [_compact(ch) for ch in pd.read_sql(text(sql), con.execution_options(stream_results=True),
                                                 chunksize=100_000)]
    if not chunks:
        return pd.DataFrame()
    out = {}
    for c in chunks[0].columns:
        parts = [ch[c] for ch in chunks]
        if all(isinstance(p.dtype, pd.CategoricalDtype) for p in parts):
            out[c] = pd.Series(union_categoricals(parts, ignore_order=True))
        else:
            out[c] = pd.concat([p.astype(object) if isinstance(p.dtype, pd.CategoricalDtype) else p for p in parts],
                               ignore_index=True)
    return pd.DataFrame(out)


def run(cfgs, queries, passwords=None, progress=None):
    """Run every slot whose server is configured. Returns {slot: DataFrame or error string}, {slot: seconds}."""
    try:
        from sqlalchemy import text
    except ImportError:
        msg = "The database library is missing. Run: pip install -r requirements.txt"
        return {s: msg for s in SLOTS}, {s: 0 for s in SLOTS}
    passwords = passwords or {}
    out, secs, engines = {}, {}, {}
    for slot, (server, *_rest) in SLOTS.items():
        sql = (queries or {}).get(slot) or DEFAULT_SQL[slot]
        if not cfgs.get(server):
            continue
        t0 = time.time()
        try:
            sql = check_sql(sql)
            if server not in engines:
                engines[server] = engine(cfgs[server], passwords.get(server, ""))
            with engines[server].connect() as con:
                out[slot] = _read_big(con, sql, text) if slot in BIG else pd.read_sql(text(sql), con)
        except Exception as e:  # keep going; report per query
            out[slot] = friendly(e)
        secs[slot] = round(time.time() - t0, 2)
        if progress:
            v = out[slot]
            progress(f"{SLOTS[slot][3]}: " + (f"{len(v):,} rows" if isinstance(v, pd.DataFrame) else f"problem: {v}"))
    for e in engines.values():
        e.dispose()
    return out, secs


# ---------------------------------------------------------------- results -> template sheets
def _col(df, *names):
    keys = {su.key(c): c for c in df.columns}
    for n in names:
        if su.key(n) in keys:
            return keys[su.key(n)]
    return None


def _rolls(s):
    """Normalise roll numbers once per distinct value (fast on millions of rows)."""
    s = s.astype(object)
    m = {x: su.norm_roll(x) for x in pd.unique(s)}
    return s.map(m)


def _num(s):
    return pd.to_numeric(s, errors="coerce").astype(float) if pd.api.types.is_numeric_dtype(s) else su.num(s)


def _dates(s):
    """Dates, datetimes or Moodle-style Unix timestamps -> local calendar dates."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_datetime(s, unit="s", utc=True).dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    d = pd.to_datetime(s, errors="coerce")
    if getattr(d.dt, "tz", None) is not None:
        d = d.dt.tz_convert(TZ).dt.tz_localize(None)
    return d.dt.normalize()


class Calendar:
    def __init__(self, cal):
        start = _col(cal, "start_date", "start", "from_date", "begins")
        name = _col(cal, "term_name", "term", "name", "semester")
        if start is None:
            raise ValueError("The calendar query must return a start_date column.")
        c = pd.DataFrame({"name": cal[name] if name else cal[start].astype(str),
                          "start": _dates(cal[start])}).dropna(subset=["start"])
        self.c = c.sort_values("start").reset_index(drop=True)
        self.current = len(self.c) - 1

    def set_current(self, latest):
        """The current term is the one the newest attendance date falls in."""
        idx = int(np.searchsorted(self.c["start"].values, np.datetime64(latest), side="right") - 1)
        self.current = max(idx, 0)

    def place(self, dates):
        """dates -> (terms back from now: 0 = this semester, -1 = last ...), week of that term."""
        d = _dates(dates)
        idx = np.searchsorted(self.c["start"].values, d.values.astype("datetime64[ns]"), side="right") - 1
        ok = (idx >= 0) & d.notna().values
        start = self.c["start"].values[np.clip(idx, 0, None)]
        week = ((d.values - start) / np.timedelta64(1, "D")) // 7 + 1
        rel = idx - self.current
        return pd.Series(np.where(ok, rel, np.nan), index=dates.index), pd.Series(np.where(ok, week, np.nan),
                                                                                  index=dates.index)


def to_sheets(res):
    """Query results -> {template sheet: DataFrame} for simple_upload.prepare(), plus notes."""
    notes = []
    sheets = {}
    S, _ = su.standardise("Students", res["students"])
    S["roll"] = S["Roll No"].map(su.norm_roll)
    cur = pd.Series(su.num(S["Current semester"]).values, index=S["roll"].values)
    cur = cur[~cur.index.duplicated()]
    if cur.isna().all():
        raise ValueError("the students query must return each student's current_semester (1 to 8)")
    sheets["Students"] = res["students"]
    sheets["Marks"] = res["marks"].copy()
    st_ = _col(sheets["Marks"], "cia1_status", "cia1_absent", "absent")
    c1 = _col(sheets["Marks"], "Internal test 1", "cia1", "internal1", "ia1", "test1")
    if st_ and c1:  # ERPs often keep 'absent' in a separate column
        ab = sheets["Marks"][st_].astype(str).str.upper().isin(["AB", "ABSENT", "Y", "1", "TRUE"])
        sheets["Marks"][c1] = sheets["Marks"][c1].astype(object)
        sheets["Marks"].loc[ab, c1] = "AB"
        sheets["Marks"] = sheets["Marks"].drop(columns=[st_])

    cal = Calendar(res["calendar"])
    A = res["attendance"]
    roll = _rolls(A[_col(A, "Roll No", "roll_no", "rollno", "regno")])
    dcol = _col(A, "class_date", "date", "attendance_date", "day")
    if dcol is None:
        sheets["Attendance"] = A  # already weekly with semester numbers
    else:
        latest = _dates(A[dcol]).max()
        cal.set_current(latest)
        rel, week = cal.place(A[dcol])
        held, attd = A[_col(A, "classes_held", "held", "total")], A[_col(A, "classes_attended", "attended", "present")]
        subj = _col(A, "subject_code", "subject", "course_code")
        W = pd.DataFrame({"Roll No": roll, "Semester": roll.map(cur) + rel, "Week": week,
                          "Subject code": A[subj].astype(object) if subj else "ALL",
                          "Classes held": _num(held).values, "Classes attended": _num(attd).values})
        n_daily = len(A)
        del A
        res["attendance"] = None  # free memory
        W = W.dropna(subset=["Semester", "Week"])
        sheets["Attendance"] = W.groupby(["Roll No", "Semester", "Week", "Subject code"], as_index=False)[
            ["Classes held", "Classes attended"]].sum()
        notes.append(f"Attendance: {n_daily:,} daily rows -> {len(sheets['Attendance']):,} weekly rows. This semester "
                     f"is '{cal.c['name'].iloc[cal.current]}' (starts {cal.c['start'].iloc[cal.current]:%d %b %Y}).")

    # ---- LMS (Moodle): weekly logins and assignments, with a 0 for weeks a student never logged in
    users = res.get("lms_users")
    if isinstance(users, pd.DataFrame) and len(users):
        lms_rolls = set(_rolls(users.iloc[:, 0]))
        grid = sheets["Attendance"][["Roll No", "Semester", "Week"]].drop_duplicates()
        grid = grid[grid["Roll No"].isin(lms_rolls)]
        G = grid.set_index(["Roll No", "Semester", "Week"])
        G["Logins"] = 0.0
        lg = res.get("lms_logins")
        if isinstance(lg, pd.DataFrame) and len(lg):
            r = _rolls(lg.iloc[:, 0])
            rel, wk = cal.place(lg[_col(lg, "timecreated", "time", "login_time", "date")])
            k = pd.DataFrame({"Roll No": r, "Semester": r.map(cur) + rel, "Week": wk}).dropna()
            G["Logins"] = k.groupby(["Roll No", "Semester", "Week"]).size().reindex(G.index).fillna(0)
        asg = res.get("lms_assignments")
        if isinstance(asg, pd.DataFrame) and len(asg):
            r = _rolls(asg.iloc[:, 0])
            rel, wk = cal.place(asg[_col(asg, "duedate", "due_date", "due")])
            stt = asg[_col(asg, "status")].astype(str).str.lower()
            k = pd.DataFrame({"Roll No": r, "Semester": r.map(cur) + rel, "Week": wk,
                              "sub": stt.isin(["submitted", "graded", "done", "1", "y"])}).dropna(subset=["Semester", "Week"])
            g = k.groupby(["Roll No", "Semester", "Week"])["sub"]
            G["Assignments due"] = g.size().reindex(G.index).fillna(0)
            G["Assignments submitted"] = g.sum().reindex(G.index).fillna(0)
        sheets["LMS"] = G.reset_index()

    # ---- one-row-per-student extras merged into "Other details"
    parts = [res[s] for s in ("placement", "skills", "activities", "feedback", "survey")
             if isinstance(res.get(s), pd.DataFrame) and len(res[s])]
    if parts:
        merged = None
        for p in parts:
            p = p.copy()
            rc = _col(p, "Roll No", "roll_no", "rollno")
            p["Roll No"] = p.pop(rc).map(su.norm_roll)
            p = p.drop_duplicates("Roll No")
            merged = p if merged is None else merged.merge(p, on="Roll No", how="outer")
        sheets["Other details"] = merged

    pa = res.get("past_actions")
    if isinstance(pa, pd.DataFrame) and len(pa):
        dcol = _col(pa, "action_date", "date", "done_on")
        if dcol:
            r = pa[_col(pa, "Roll No", "roll_no", "rollno")].map(su.norm_roll)
            rel, wk = cal.place(pa[dcol])
            sheets["Past actions"] = pd.DataFrame({
                "Roll No": r, "Semester": r.map(cur) + rel, "Week": wk, "Action": pa[_col(pa, "action")],
                "Done by": pa[_col(pa, "done_by", "owner", "staff")] if _col(pa, "done_by", "owner", "staff") else ""})
        else:
            sheets["Past actions"] = pa
    pp = res.get("past_placements")
    if isinstance(pp, pd.DataFrame) and len(pp):
        sheets["Past placements"] = pp
    return sheets, notes


def sync(cfgs, queries=None, passwords=None, progress=None):
    """Run the queries and check the data. Returns dict(result=prepare() output, notes, report rows, ok)."""
    t0 = time.time()
    res, secs = run(cfgs, queries, passwords, progress)
    report, errors = [], []
    for slot, (server, sheet, need, label, _) in SLOTS.items():
        if slot not in res:
            if need:
                errors.append(f"{label}: no {server.upper()} connection.")
            continue
        v = res[slot]
        if isinstance(v, str):
            report.append(dict(slot=slot, label=label, rows=None, secs=secs[slot], error=v))
            (errors if need else []).append(f"{label}: {v}")
            res[slot] = None
        else:
            report.append(dict(slot=slot, label=label, rows=len(v), secs=secs[slot], error=None))
            if need and not len(v):
                errors.append(f"{label}: the query returned no rows.")
    if errors:
        return dict(ok=False, errors=errors, report=report, result=None, notes=[])
    try:
        if progress:
            progress("Turning dates into semesters and weeks, and checking everything ...")
        sheets, notes = to_sheets(res)
        del res
        result = su.prepare(sheets)
    except Exception as e:  # unexpected shape: say which
        return dict(ok=False, errors=[f"Could not read the query results: {e}"], report=report, result=None, notes=[])
    notes.append(f"Read in {time.time() - t0:.1f} s.")
    return dict(ok=result["ok"], errors=[], report=report, result=result, notes=notes)


# ---------------------------------------------------------------- saved connection (never the password)
def load_conn():
    if CONN_FILE.exists():
        try:
            return json.loads(CONN_FILE.read_text())
        except Exception:
            pass
    return {}


def save_conn(conn):
    clean = json.loads(json.dumps(conn))
    for k in ("erp", "lms"):
        if isinstance(clean.get(k), dict):
            clean[k].pop("password", None)
    CONN_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONN_FILE.write_text(json.dumps(clean, indent=1))


def demo_cfgs():
    from . import demo_server as ds
    return {"erp": dict(dialect="SQLite file", database=str(ds.ERP_DB)),
            "lms": dict(dialect="SQLite file", database=str(ds.LMS_DB))}
