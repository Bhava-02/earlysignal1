-- ============================================================================
-- DEMO: the same student on the Moodle LMS (moodle.db)
-- idnumber holds the roll number, which is how EarlySignal links the two systems.
-- Weeks 1-5: active. Weeks 6-9: logins stop and assignments are not submitted.
-- ============================================================================
INSERT INTO mdl_user (id, username, idnumber, email, firstname, lastname, deleted)
VALUES ((SELECT MAX(id) FROM mdl_user) + 1, '23cs121', '23CS121', '23cs121@college.edu.in', 'Meera', 'Subramani', 0);

-- Log-ins: 6 a week in weeks 1-5, 1 in week 6, none after
INSERT INTO mdl_logstore_standard_log (id, eventname, component, action, target, userid, courseid, timecreated)
WITH w(w, n) AS (VALUES (1,6),(2,6),(3,6),(4,6),(5,6),(6,1)),
     k(k) AS (VALUES (0),(1),(2),(3),(4),(5))
SELECT (SELECT MAX(id) FROM mdl_logstore_standard_log) + ROW_NUMBER() OVER (ORDER BY w.w, k.k),
       '\core\event\user_loggedin', 'core', 'loggedin', 'user',
       (SELECT id FROM mdl_user WHERE idnumber = '23CS121'), 0,
       CAST(STRFTIME('%s', '2026-08-10') AS INTEGER) - 19800 + 86400 * (7 * (w.w - 1) + k.k % 5) + 36000 + 600 * k.k
FROM w JOIN k ON k.k < w.n;

-- Assignments of this semester (weeks 1-9): submitted until week 5, then not
INSERT INTO mdl_assign_submission (id, assignment, userid, status, timemodified, latest)
SELECT (SELECT MAX(id) FROM mdl_assign_submission) + ROW_NUMBER() OVER (ORDER BY a.id),
       a.id, (SELECT id FROM mdl_user WHERE idnumber = '23CS121'),
       CASE WHEN CAST(SUBSTR(a.name, INSTR(a.name, 'week ') + 5) AS INTEGER) <= 5 THEN 'submitted' ELSE 'new' END,
       a.duedate - 7200, 1
FROM mdl_assign a
WHERE a.name LIKE '%(2026-ODD, week %'
  AND CAST(SUBSTR(a.name, INSTR(a.name, 'week ') + 5) AS INTEGER) <= 9;
