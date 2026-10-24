# Demo: add a student with SQL, then watch EarlySignal pick her up

Run from the project folder. The demo college server must exist (Data sources > "Start the demo server",
or `python -m src.demo_server`).

```bash
# 1. Before: how many students?
python demo/run_sql.py erp -q "SELECT COUNT(*) FROM students"          # 1080

# 2. The college ERP admits a student (plain INSERT statements, shown on screen)
python demo/run_sql.py erp demo/1_erp_add_student.sql
python demo/run_sql.py lms demo/2_moodle_add_user.sql

# 3. Show she is in the college database
python demo/run_sql.py erp -q "SELECT roll_no, full_name, current_semester FROM students WHERE roll_no='23CS121'"

# 4. Refresh EarlySignal (or press "Sync now" on the Data sources page)
python -m src.sync --demo                    # about 15 seconds
python -m src.pipeline --web                 # Round 2 only; then rebuild the React file

# 5. Undo
python demo/run_sql.py erp demo/3_remove_student.sql
python demo/run_sql.py lms demo/4_moodle_remove_user.sql
```

Expected: 1,081 students. Meera Subramani (23CS121, CSE year 4) appears as High risk, segment
"Critical: Act This Week", first step "Attendance recovery plan", owner Faculty mentor.
