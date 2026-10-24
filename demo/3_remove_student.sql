-- Undo the demo: remove Meera from the ERP (run with college_erp.db)
DELETE FROM attendance          WHERE student_id = 2081;
DELETE FROM exam_marks          WHERE student_id = 2081;
DELETE FROM placement_training  WHERE student_id = 2081;
DELETE FROM skill_assessments   WHERE student_id = 2081;
DELETE FROM students            WHERE student_id = 2081;
