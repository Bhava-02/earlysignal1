-- Undo the demo: remove Meera from Moodle (run with moodle.db)
DELETE FROM mdl_assign_submission WHERE userid = (SELECT id FROM mdl_user WHERE idnumber = '23CS121');
DELETE FROM mdl_logstore_standard_log WHERE userid = (SELECT id FROM mdl_user WHERE idnumber = '23CS121');
DELETE FROM mdl_user WHERE idnumber = '23CS121';
