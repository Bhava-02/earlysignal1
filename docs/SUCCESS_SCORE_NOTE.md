# EarlySignal: the Student Success Score

*Short note for the KPMG Smart Campus Analytics challenge. Numbers below come from the included dataset
(1,080 students, semester 2026-ODD, week 9 of 16).*

## 1. What the score is

The **Student Success Score (0–100)** summarises how a student is doing right now across three areas:

| Sub-score | What it captures | Indicators |
|---|---|---|
| **Academic Health** | Are they passing, and will they stay exam-eligible? | CGPA, CIA-1 marks this semester, attendance this semester, standing arrears, faculty participation rating |
| **Engagement** | Are they showing up and keeping up, and which way is it trending? | LMS logins/week, assignment completion, momentum (last 3–4 weeks vs earlier), events/clubs/hackathons, satisfaction survey |
| **Placement Readiness** | Would they get placed if recruitment opened today? | Aptitude, coding, mock interviews (count and rating), technical and soft skills, certifications, recruiter eligibility (CGPA ≥ 6.5 and no standing arrears) |

**Think of it as a marksheet out of 100.** Each indicator has maximum marks. A student gets full marks at a top
level (for example CGPA 9.5 or more), zero at a bottom level (CGPA 5.0 or less), and marks in proportion in between.
The Success Score is the total of all the marks. As a formula: Score = Σ (maximum marks × how far the student is
between the bottom and top level).

Bands: **Thriving** ≥ 70 · **On Track** 55–70 · **Needs Attention** 40–55 · **At Risk** < 40.

## 2. How indicators are combined

**Scaling.** Every indicator is scaled to 0–1 against *fixed, explainable bounds*, not against other students.
For example, attendance 60% → 0 and 100% → 1; CGPA 5.0 → 0 and 9.5 → 1; arrears 0 → 1 and 4+ → 0.
So a score of 62 means the same thing in every department and every semester.

**Weights shift by year of study.** Placement matters more as placement season approaches:

| | Academic | Engagement | Placement |
|---|---|---|---|
| 2nd year | 50% | 30% | 20% |
| 3rd year | 40% | 25% | 35% |
| 4th year | 35% | 20% | 45% |

**Placement weights are learned, not guessed.** The weights inside Placement Readiness come from a logistic
regression trained on last year's 360 graduates and whether they were actually placed (AUC 0.97).
The data showed each extra mock interview raised placement odds by about **113%**, while each extra
certification raised them by only about **13%**. The weights reflect that.

**Effective weight of each indicator (all weights for a year add to 100%):**

| Indicator | Scale (0 → 1) | Y2 | Y3 | Y4 |
|---|---|---|---|---|
| CGPA | 5.0 → 9.5 | 15.0% | 12.0% | 10.5% |
| CIA-1 marks (this semester) | 30 → 90 | 12.5% | 10.0% | 8.8% |
| Attendance (this semester) | 60 → 100 | 10.0% | 8.0% | 7.0% |
| Standing arrears | 4 → 0 | 7.5% | 6.0% | 5.2% |
| Faculty participation rating | 1 → 5 | 5.0% | 4.0% | 3.5% |
| LMS logins / week | 0 → 6 | 6.0% | 5.0% | 4.0% |
| Assignment completion | 40% → 100% | 9.0% | 7.5% | 6.0% |
| Momentum (last 3–4 weeks) | falling → rising | 6.0% | 5.0% | 4.0% |
| Events, clubs & hackathons (12 months) | 0 → 6 | 4.5% | 3.8% | 3.0% |
| Satisfaction & feeling supported | 1 → 5 | 4.5% | 3.8% | 3.0% |
| Aptitude score | 30 → 90 | 6.5% | 5.5% | 7.0% |
| Coding score | 20 → 90 | – | 8.4% | 10.8% |
| Mock interviews done | 0 → 4 | – | 7.7% | 9.9% |
| Mock interview rating | 1 → 5 | – | 2.1% | 2.7% |
| Technical skills | 30 → 90 | 0.3% | 0.2% | 0.3% |
| Soft skills | 30 → 90 | 5.5% | 4.7% | 6.0% |
| Certifications | 0 → 3 | 1.4% | 1.2% | 1.5% |
| Recruiter eligibility | no → yes | 6.2% | 5.2% | 6.8% |

**Explainability.** Because the score is a weighted sum, it splits *exactly* into per-indicator contributions:
"+3.1 points from assignment completion, −4.5 from CGPA" relative to the average student of the same year.
That is the "What's affecting the score" panel on every student's profile.

**Missing data.** A missing indicator (no survey response, no skills test, LMS account not linked) is filled with
the median for that year, so the score stays fair, and the student's **Data confidence** drops. Confidence is the
share of the score's weight backed by real data: High ≥ 90%, Medium 75–90%, Low below 75%.

## 3. Risk flags (separate from the score)

The score describes *now*. The two risk flags predict *outcomes*.

**Academic risk:** the chance of failing at least one subject this semester.
- A logistic regression on weekly behaviour (attendance, LMS logins, assignment completion, each as level *and*
  recent trend), CIA-1 marks (once published in week 7), prior CGPA and standing arrears.
- One model per week, so it only uses what was known at that point in the semester.
- **High ≥ 60% · Medium 30–60% · Low < 30%.** Also raised to at least Medium if attendance is projected to end
  below 75% (exam eligibility).
- **Back-test:** trained on 2025-ODD, tested on 2026-EVEN, which it never saw. By **week 6** it had flagged **78%** of the
  students who went on to fail, against **41%** for the usual attendance-shortage and low-marks lists, and on
  average **2.1 weeks earlier**. AUC 0.94 at week 6 and 0.97 at week 9.

**Placement risk** (3rd and 4th years): High if the placement model gives below a 35% chance, or the student is not
eligible for most recruiters; Medium below 60%.

Each flag lists its top reasons in plain words, taken from the model's exact per-feature contributions,
for example "LMS activity down 62% in the last 3 weeks" or "Coding score 31 (placed seniors averaged 60)".

## 4. From score to action

- **Segments:** 7 rule-based groups, each with a playbook, an owner and a success measure. Examples: Silent
  Strugglers (marks fine, behaviour falling), Book-smart Job-shy (CGPA 8+ but not placement-ready), Academic
  Catch-up.
- **Action plan tab:** the smallest realistic set of changes that moves a student out of risk, computed with the same
  formula and models.
- **What works:** past actions evaluated against comparable students who got no action. Remedial classes cut
  failures by about a third; parent calls showed almost no effect.

## 5. Limits and safeguards

- The prototype runs on **synthetic data** built to behave like real campus systems, including their mess.
  Real data will be noisier; the models should be re-validated every semester.
- Gender, residence and first-graduate status are **never model inputs**. The Fairness page checks flag rates and
  accuracy across these groups.
- The score supports a mentor conversation. It **never decides** anything about a student on its own.
