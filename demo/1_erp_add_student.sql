-- ============================================================================
-- DEMO: add ONE new student to the college ERP database (college_erp.db)
--
-- Meera Subramani, CSE final year, joined a week late as a lateral-entry student.
-- Her attendance is fine for weeks 1-5, then falls away. EarlySignal should flag her.
--
-- EarlySignal itself never runs INSERT. This is what the college's own ERP does when
-- a student is admitted. EarlySignal only READS the result on the next sync.
-- ============================================================================

-- 1. The student record  (department 1 = CSE, mentor 509 = Dr. R. Lakshmi)
INSERT INTO students
  (student_id, roll_no,  register_no,    full_name,         gender, department_id, batch_year,
   current_semester, section, hostel_flag, first_graduate, mentor_staff_id, email,                    hsc_percentage, status)
VALUES
  (2081,       '23CS121','412723104121', 'Meera Subramani', 'F',    1,             2023,
   7,                'A',     'N',         'Y',            509,             '23cs121@college.edu.in', 86.4,           'ACTIVE');

-- 2. Past results: semesters 5 and 6, all passed (these give her a CGPA)
INSERT INTO exam_marks (mark_id, student_id, subject_id, cia1, cia1_status, cia2, end_sem, grade, attempt_no)
SELECT (SELECT MAX(mark_id) FROM exam_marks) + ROW_NUMBER() OVER (ORDER BY subject_id),
       2081, subject_id, 38, 'P', 36, 74, 'A', 1
FROM subjects WHERE department_id = 1 AND semester IN (5, 6);

-- 3. This semester (7): the first internal test (CIA-1) was weak
INSERT INTO exam_marks (mark_id, student_id, subject_id, cia1, cia1_status, cia2, end_sem, grade, attempt_no)
SELECT (SELECT MAX(mark_id) FROM exam_marks) + ROW_NUMBER() OVER (ORDER BY subject_id),
       2081, subject_id, 21, 'P', NULL, NULL, NULL, 1
FROM subjects WHERE department_id = 1 AND semester = 7;

-- 4. Period-wise attendance, weeks 1-9 of 2026-ODD (term starts 2026-08-10).
--    4 class hours per subject per week. Weeks 1-5 present; week 6-7 half; weeks 8-9 absent.
INSERT INTO attendance (attendance_id, student_id, subject_id, class_date, period_no, status)
WITH w(w) AS (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9)),
     k(k) AS (VALUES (0),(1),(2),(3))
SELECT (SELECT MAX(attendance_id) FROM attendance) + ROW_NUMBER() OVER (ORDER BY w.w, s.subject_id, k.k),
       2081, s.subject_id,
       DATE('2026-08-10', '+' || (7 * (w.w - 1) + k.k) || ' days'),
       k.k + 1,
       CASE WHEN w.w <= 5 THEN 'P'
            WHEN w.w <= 7 THEN CASE WHEN k.k % 2 = 0 THEN 'P' ELSE 'A' END
            ELSE 'A' END
FROM w CROSS JOIN k
JOIN subjects s ON s.department_id = 1 AND s.semester = 7;

-- 5. Placement training: decent aptitude, weak coding, no mock interview yet
INSERT INTO placement_training (id, student_id, test_type, score, test_date)
VALUES ((SELECT MAX(id) FROM placement_training) + 1, 2081, 'Aptitude', 64, '2026-08-15'),
       ((SELECT MAX(id) FROM placement_training) + 2, 2081, 'Coding',   38, '2026-09-15');

-- 6. Skills assessment
INSERT INTO skill_assessments (id, student_id, technical_score, soft_skill_score, assessed_on)
VALUES ((SELECT MAX(id) FROM skill_assessments) + 1, 2081, 58, 62, '2026-07-20');
