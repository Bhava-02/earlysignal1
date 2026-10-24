"""Run a .sql file against one of the demo college databases, like a college's DBA would.

    python demo/run_sql.py erp   demo/1_erp_add_student.sql
    python demo/run_sql.py lms   demo/2_moodle_add_user.sql
    python demo/run_sql.py erp   -q "SELECT roll_no, full_name FROM students WHERE roll_no = '23CS121'"
"""
import sqlite3
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "demo_server"
DB = {"erp": DIR / "college_erp.db", "lms": DIR / "moodle.db"}

which, what = sys.argv[1], sys.argv[2]
with sqlite3.connect(DB[which]) as con:
    if what == "-q":
        cur = con.execute(sys.argv[3])
        print(" | ".join(c[0] for c in cur.description))
        for row in cur.fetchall():
            print(" | ".join(str(x) for x in row))
    else:
        con.executescript(Path(what).read_text())
        print(f"Ran {what} on {DB[which].name}")
