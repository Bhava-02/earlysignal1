"""
Generate realistic, deliberately messy data for a college of ~1,080 students,
exported the way 9 separate campus systems would export it.

Built-in realism (so the analytics have something true to find):
  * Disengagement shows up in a fixed order: LMS logins drop first, then
    assignment submissions (1 week later), then attendance (2 weeks later),
    and marks fall last.
  * Day scholars attend slightly less (commute), which the fairness page surfaces.
  * Very active co-curricular students have a slightly higher chance of an academic dip.
  * Past interventions have different real effects, so effectiveness can be measured.

Built-in mess (so data integration has real work to do):
  * Each system identifies students differently (roll no, 12-digit register no,
    email, LMS user id, "23-CS-045", or only name + department + year).
  * Lower-case / padded / un-padded IDs, Excel-corrupted register numbers,
    personal Gmail addresses, name spelling variants, inconsistent department
    and year labels, duplicate rows, "AB" for absent, "%" signs, impossible values.
"""
import numpy as np
import pandas as pd

from . import config as C

rng = np.random.default_rng(C.SEED)

FEMALE = ["Priya", "Divya", "Kavya", "Sneha", "Harini", "Lakshmi", "Swathi", "Nandhini", "Keerthana", "Aishwarya",
          "Deepika", "Janani", "Sowmya", "Meena", "Anjali", "Pooja", "Ritika", "Shreya", "Ananya", "Fathima",
          "Sandhya", "Gayathri", "Vaishnavi", "Monisha", "Bhavana", "Ishita", "Nikita", "Sahana", "Pavithra", "Revathi",
          "Ayesha", "Madhumitha", "Yamini", "Sruthi", "Dharshini", "Hema", "Ramya", "Sushmitha", "Tanvi", "Varsha"]
MALE = ["Arun", "Karthik", "Vignesh", "Rahul", "Surya", "Praveen", "Dinesh", "Ajith", "Gokul", "Hari",
        "Manoj", "Naveen", "Sanjay", "Vijay", "Aditya", "Rohan", "Mohammed", "Imran", "Siddharth", "Ashwin",
        "Bharath", "Deepak", "Ganesh", "Kishore", "Lokesh", "Madhan", "Nithish", "Pranav", "Ragul", "Santhosh",
        "Tarun", "Yash", "Abishek", "Kavin", "Mukesh", "Sabari", "Vishal", "Arjun", "Dhanush", "Jeevan"]
INITIALS = list("ABCDEGJKLMNPRSTV")
SURNAMES = ["Kumar", "Sharma", "Reddy", "Nair", "Iyer", "Menon", "Patel", "Singh", "Rao", "Pillai", "Das", "Joseph"]

SUBJECT_POOL = {
    "CSE": ["Programming in C", "Data Structures", "Digital Principles", "OOP with Java", "Discrete Mathematics",
            "Design & Analysis of Algorithms", "Database Management Systems", "Operating Systems", "Computer Networks",
            "Theory of Computation", "Software Engineering", "Compiler Design", "Machine Learning", "Cloud Computing",
            "Web Technologies", "Artificial Intelligence", "Cryptography & Network Security", "Big Data Analytics",
            "Deep Learning", "Distributed Systems", "Internet of Things", "Mobile App Development",
            "Natural Language Processing", "DevOps", "Computer Architecture", "Probability & Statistics",
            "Engineering Mathematics I", "Engineering Mathematics II", "Engineering Physics", "Professional English",
            "Human Values & Ethics", "Data Mining", "Information Retrieval", "Blockchain", "Project Management"],
    "IT": ["Programming in C", "Data Structures", "Digital Logic", "Java Programming", "Discrete Mathematics",
           "Algorithms", "Database Systems", "Operating Systems", "Computer Networks", "Web Engineering",
           "Software Testing", "Information Security", "Cloud Architecture", "Data Science", "Machine Learning",
           "Full Stack Development", "Mobile Computing", "Embedded Systems", "IoT Systems", "Big Data",
           "UI/UX Design", "Cyber Forensics", "Natural Language Processing", "Deep Learning", "Agile Methods",
           "Engineering Mathematics I", "Engineering Mathematics II", "Engineering Physics", "Professional English",
           "Probability & Statistics", "Computer Organisation", "Distributed Computing", "Data Visualisation",
           "Blockchain", "Professional Ethics"],
    "ECE": ["Circuit Theory", "Electronic Devices", "Signals & Systems", "Digital Electronics", "Electromagnetic Fields",
            "Analog Circuits", "Linear Integrated Circuits", "Communication Theory", "Control Systems",
            "Microprocessors", "Digital Signal Processing", "Transmission Lines", "VLSI Design", "Embedded Systems",
            "Antenna & Wave Propagation", "Digital Communication", "Optical Communication", "Wireless Networks",
            "Satellite Communication", "RF Engineering", "Image Processing", "IoT Systems", "Radar Engineering",
            "Engineering Mathematics I", "Engineering Mathematics II", "Engineering Physics", "Professional English",
            "Probability & Random Processes", "Python Programming", "Network Analysis", "Medical Electronics",
            "MEMS", "Machine Learning for ECE", "Mobile Communication", "Professional Ethics"],
    "MECH": ["Engineering Mechanics", "Engineering Graphics", "Thermodynamics", "Fluid Mechanics",
             "Strength of Materials", "Manufacturing Technology", "Kinematics of Machinery", "Thermal Engineering",
             "Dynamics of Machinery", "Design of Machine Elements", "Heat & Mass Transfer", "Metrology",
             "CAD/CAM", "Finite Element Analysis", "Automobile Engineering", "Robotics", "Power Plant Engineering",
             "Refrigeration & AC", "Mechatronics", "Industrial Engineering", "Additive Manufacturing",
             "Composite Materials", "Renewable Energy", "Engineering Mathematics I", "Engineering Mathematics II",
             "Engineering Physics", "Professional English", "Numerical Methods", "Python Programming",
             "Materials Science", "Hydraulics & Pneumatics", "Quality Engineering", "Operations Research",
             "Total Quality Management", "Professional Ethics"],
}
MENTORS = {
    "CSE": ["Dr. R. Lakshmi", "Prof. S. Karthikeyan", "Dr. M. Fathima", "Prof. V. Anand", "Dr. K. Meenakshi", "Prof. P. Rajesh"],
    "IT": ["Dr. A. Sundar", "Prof. N. Kavitha", "Dr. T. Ramesh", "Prof. G. Shalini", "Dr. B. Prakash"],
    "ECE": ["Dr. J. Srinivasan", "Prof. L. Revathi", "Dr. H. Mohan", "Prof. D. Uma", "Dr. C. Venkatesh"],
    "MECH": ["Dr. S. Murugan", "Prof. R. Balaji", "Dr. P. Selvi"],
}
DEPT_LABEL_VARIANTS = {
    "CSE": ["CSE", "Computer Science", "C.S.E", "cse", "CS"],
    "IT": ["IT", "Information Tech", "I.T", "it"],
    "ECE": ["ECE", "Electronics & Comm", "E.C.E", "ece", "EC"],
    "MECH": ["MECH", "Mechanical", "Mech", "ME"],
}
YEAR_LABEL_VARIANTS = {2: ["II", "2", "2nd Year", "Second"], 3: ["III", "3", "3rd Year", "Third"],
                       4: ["IV", "4", "Final Year", "4th Year"]}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def ramp(weeks_since):
    """0 before onset, rising to 1 over two weeks after onset."""
    return np.clip((weeks_since + 1) / 2.0, 0, 1)


def name_variant(first, last, style):
    """How a name might be typed into a system that has no student ID."""
    r = rng.random()
    if style == "initial":
        options = [f"{first} {last}", f"{first.upper()} {last}", f"{first}.{last}", f"{last}. {first}",
                   f"{last} {first}", f"{first} {last}."]
    else:
        options = [f"{first} {last}", f"{first.upper()} {last.upper()}", f"{first} {last[0]}", f"{last} {first}"]
    v = options[int(r * len(options))]
    if rng.random() < 0.05 and len(first) > 4:  # typo: swap two adjacent letters
        i = int(rng.integers(1, len(first) - 2))
        typo = first[:i] + first[i + 1] + first[i] + first[i + 2:]
        v = v.replace(first, typo).replace(first.upper(), typo.upper())
    return v


# ---------------------------------------------------------------- students
def make_students():
    corr = np.array([
        # ability engage drive  extra  soft
        [1.00, 0.35, 0.30, 0.00, 0.15],
        [0.35, 1.00, 0.35, 0.20, 0.10],
        [0.30, 0.35, 1.00, 0.25, 0.20],
        [0.00, 0.20, 0.25, 1.00, 0.40],
        [0.15, 0.10, 0.20, 0.40, 1.00],
    ])
    L = np.linalg.cholesky(corr)
    rows = []
    for batch, yos in C.BATCHES.items():
        yy = str(batch)[2:]
        for dept, (dname, ucode, rcode, n) in C.DEPTS.items():
            mentors = MENTORS[dept]
            for i in range(1, n + 1):
                z = np.clip(L @ rng.standard_normal(5), -2.0, 2.5)  # extreme cases would have left the college
                female = rng.random() < 0.45
                first = rng.choice(FEMALE if female else MALE)
                style = "initial" if rng.random() < 0.65 else "surname"
                last = rng.choice(INITIALS) if style == "initial" else rng.choice(SURNAMES)
                rows.append(dict(
                    roll_no=f"{yy}{rcode}{i:03d}", register_no=f"{C.COLLEGE_CODE}{yy}{ucode}{i:03d}",
                    first=first, last=last, name_style=style, name=f"{first} {last}",
                    gender="F" if female else "M", dept=dept, batch=batch, year=yos,
                    section="ABC"[(i - 1) * 3 // n] if n >= 90 else "AB"[(i - 1) * 2 // n],
                    residence="Hostel" if rng.random() < 0.40 else "Day Scholar",
                    first_graduate="Yes" if rng.random() < 0.25 else "No",
                    mentor=mentors[(i - 1) % len(mentors)],
                    ability=z[0], engage=z[1], drive=z[2], extra=z[3], soft=z[4],
                    hsc_percent=float(np.clip(round(78 + 9 * z[0] + rng.normal(0, 5), 1), 55, 99.5)),
                    personal_email=(f"{first.lower()}{last.lower()[0]}{rng.integers(2000, 2008)}"
                                    f"@{rng.choice(['gmail.com', 'gmail.com', 'yahoo.com', 'outlook.com'])}"),
                ))
    df = pd.DataFrame(rows)
    df["email"] = df["roll_no"].str.lower() + "@" + C.EMAIL_DOMAIN
    return df


def subjects_for(dept, sem_no):
    pool = SUBJECT_POOL[dept]
    rcode = C.DEPTS[dept][2]
    out = []
    for k in range(C.SUBJECTS_PER_SEM):
        idx = ((sem_no - 1) * C.SUBJECTS_PER_SEM + k) % len(pool)
        difficulty = ((sum(map(ord, pool[idx])) % 7) - 3) / 3.0  # stable -1..1
        out.append((f"{rcode}{sem_no}{k + 1:02d}", pool[idx], difficulty))
    return out


def grade_point(total, endsem):
    if endsem < 45 or total < 50:
        return "RA", 0
    for cut, g, gp in [(91, "O", 10), (81, "A+", 9), (71, "A", 8), (61, "B+", 7), (56, "B", 6), (50, "C", 5)]:
        if total >= cut:
            return g, gp
    return "RA", 0


# ---------------------------------------------------------------- simulation
def simulate(students):
    att_rows, lms_rows, exam_rows, int_rows, fb_rows, survey_rows = [], [], [], [], [], []
    truth = []  # hidden ground truth, used only for sanity checks
    W = C.WEEKS_PER_SEM
    weeks = np.arange(1, W + 1)
    intervention_effect = {"Mentor meeting": 0.60, "Remedial classes": 0.30, "Peer tutoring": 0.45,
                           "Counselling referral": 0.75, "Parent call": 0.15}
    marks_bonus = {"Remedial classes": 5.0, "Peer tutoring": 2.5}

    for s in students.itertuples():
        cur_sem_no = 2 * s.year - 1
        tracked = {C.SEMESTERS[0]: cur_sem_no - 2, C.SEMESTERS[1]: cur_sem_no - 1, C.SEMESTERS[2]: cur_sem_no}
        day = 1.0 if s.residence == "Day Scholar" else 0.0

        # earlier semesters: results only
        for sem_no in range(1, cur_sem_no - 2):
            eng_s = s.engage + rng.normal(0, 0.5)
            for code, title, diff in subjects_for(s.dept, sem_no):
                internal = np.clip(36 + 7 * s.ability + 4.5 * eng_s - 3 * diff + rng.normal(0, 5), 5, 50)
                endsem = np.clip(80 + 10 * s.ability + 5 * eng_s - 4 * diff + rng.normal(0, 7), 0, 100)
                total = internal / 50 * 40 + endsem * 0.6
                g, gp = grade_point(total, endsem)
                exam_rows.append(dict(register_no=s.register_no, student_name=s.name, sem_label=f"Sem {sem_no}",
                                      semester_no=sem_no, subject_code=code, subject_name=title,
                                      cia1=round(internal), cia2=round(internal + rng.normal(0, 3)),
                                      end_sem=round(endsem), grade=g, attempt=1))
                if g == "RA" and rng.random() < 0.65:  # cleared in a later arrear attempt
                    endsem2 = max(45, endsem + rng.normal(14, 6))
                    g2, _ = grade_point(internal / 50 * 40 + endsem2 * 0.6, endsem2)
                    exam_rows.append(dict(register_no=s.register_no, student_name=s.name, sem_label=f"Sem {sem_no}",
                                          semester_no=sem_no, subject_code=code, subject_name=title,
                                          cia1=round(internal), cia2=None, end_sem=round(endsem2),
                                          grade=g2 if g2 != "RA" else "C", attempt=2))

        for sem_label, sem_no in tracked.items():
            is_current = sem_label == C.CURRENT_SEM
            last_week = C.CURRENT_WEEK if is_current else W
            # disengagement episode
            p_shock = sigmoid(-2.0 - 0.8 * s.engage - 0.3 * s.ability + (0.35 if s.extra > 1.0 else 0))
            shocked = rng.random() < p_shock
            w0 = int(rng.integers(2, 10)) if shocked else 99
            sev = rng.uniform(0.45, 0.95) if shocked else 0.0
            # Past semesters: the college already had a simple alert (a student's LMS logins over the last
            # 2 weeks fall to half their own first-3-week level, or 3 of the last 4 assignments are missed).
            # Mentors followed up on about 60% of alerts, whoever they had time for, with one action.
            # Current-semester actions are logged from the dashboard instead.
            itype, iweek, alerted = None, None, False
            sev_w = np.full(W, sev)
            logins_h, due_h, sub_h = [], [], []
            eng_lms, eng_asg, eng_att = np.zeros(W), np.zeros(W), np.zeros(W)
            for w in range(1, W + 1):
                if not is_current and not alerted and w >= 5:
                    base, recent = np.mean(logins_h[:3]), np.mean(logins_h[-2:])
                    missed = sum(due_h[-4:]) - sum(sub_h[-4:])
                    if (base >= 1.5 and recent <= 0.4 * base) or missed >= 5:
                        alerted = True
                        if rng.random() < 0.6:
                            itype = str(rng.choice(list(intervention_effect)))
                            iweek = min(w + int(rng.integers(0, 2)), W)
                            recover = min(0.95, intervention_effect[itype] * rng.uniform(0.7, 1.3))
                            sev_w[iweek - 1:] = sev * (1 - recover)
                            int_rows.append(dict(roll_no=s.roll_no, semester=sem_label, week=iweek, action=itype,
                                                 owner="Mentor" if itype in ("Mentor meeting", "Parent call") else
                                                 ("Counsellor" if itype == "Counselling referral" else "Subject faculty")))
                drop = 2.6 * sev_w[w - 1]
                eng_lms[w - 1] = s.engage - drop * ramp(w - w0)
                eng_asg[w - 1] = s.engage - drop * ramp(w - w0 - 1)
                eng_att[w - 1] = s.engage - drop * ramp(w - w0 - 2)
                lam = max(0.2, 3.4 + 1.3 * eng_lms[w - 1] + 0.4 * s.ability)
                logins = int(rng.poisson(lam))
                due = 0 if w in (6, 12, 16) else 2
                sub = int(rng.binomial(due, sigmoid(1.8 + 1.0 * eng_asg[w - 1] + 0.3 * s.ability))) if due else 0
                logins_h.append(logins)
                due_h.append(due)
                sub_h.append(sub)
                if w > last_week:
                    continue
                lms_rows.append(dict(roll_no=s.roll_no, semester=sem_label, week=w, logins=logins,
                                     minutes=round(logins * rng.gamma(4, 7), 1), assignments_due=due,
                                     assignments_submitted=sub, quiz_attempts=int(rng.poisson(0.6 + 0.3 * logins))))
                p_att = sigmoid(2.3 + 0.75 * eng_att[w - 1] - 0.28 * day)
                for code, title, diff in subjects_for(s.dept, sem_no):
                    held = 3 if rng.random() < 0.1 else 4
                    att_rows.append(dict(roll_no=s.roll_no, semester=sem_label, week=w, subject_code=code,
                                         classes_held=held, classes_attended=int(rng.binomial(held, p_att))))

            # marks for this semester
            e1 = eng_lms[:6].mean()
            e2 = eng_lms[6:12].mean()
            efull = eng_lms.mean()
            bonus = marks_bonus.get(itype, 0)
            # events no system can see (illness during exams, family emergency): keeps the model honest
            exam_hit = {}
            if rng.random() < 0.05:
                for c, _, _ in subjects_for(s.dept, sem_no)[: int(rng.integers(1, 4))]:
                    exam_hit[c] = rng.uniform(12, 28)
            fails = 0
            gps = []
            for code, title, diff in subjects_for(s.dept, sem_no):
                cia1 = np.clip(36 + 7 * s.ability + 4.5 * e1 - 3 * diff + rng.normal(0, 5), 8, 50)
                cia2 = np.clip(36 + 7 * s.ability + 4.5 * e2 - 3 * diff + bonus + rng.normal(0, 5), 8, 50)
                cia1_val = "AB" if (shocked and w0 <= 6 and rng.random() < 0.15) else round(cia1)
                if is_current:
                    exam_rows.append(dict(register_no=s.register_no, student_name=s.name, sem_label=f"Sem {sem_no}",
                                          semester_no=sem_no, subject_code=code, subject_name=title,
                                          cia1=cia1_val, cia2=None, end_sem=None, grade=None, attempt=1))
                    continue
                endsem = np.clip(80 + 10 * s.ability + 5 * s.engage - 15 * (s.engage - efull) - 4 * diff + bonus
                                 - exam_hit.get(code, 0) + rng.normal(0, 8), 0, 100)
                internal = ((0 if cia1_val == "AB" else cia1) + cia2) / 2
                g, gp = grade_point(internal / 50 * 40 + endsem * 0.6, endsem)
                fails += g == "RA"
                gps.append(gp)
                exam_rows.append(dict(register_no=s.register_no, student_name=s.name, sem_label=f"Sem {sem_no}",
                                      semester_no=sem_no, subject_code=code, subject_name=title, cia1=cia1_val,
                                      cia2=round(cia2), end_sem=round(endsem), grade=g, attempt=1))
                if g == "RA" and sem_label == C.SEMESTERS[0] and rng.random() < 0.55:
                    endsem2 = max(45, endsem + rng.normal(14, 6))
                    exam_rows.append(dict(register_no=s.register_no, student_name=s.name, sem_label=f"Sem {sem_no}",
                                          semester_no=sem_no, subject_code=code, subject_name=title,
                                          cia1=cia1_val, cia2=None, end_sem=round(endsem2), grade="C", attempt=2))
            truth.append(dict(roll_no=s.roll_no, semester=sem_label, shocked=shocked, onset=w0, severity=sev,
                              intervention=itype, fails=fails))

            if is_current:
                e8 = eng_lms[7]
                for code, title, diff in subjects_for(s.dept, sem_no):
                    rating = int(np.clip(round(3 + 0.6 * s.ability + 0.7 * e8 + rng.normal(0, 0.6)), 1, 5))
                    remark = {5: "Excellent participation", 4: "Attentive and regular",
                              3: "Satisfactory", 2: "Irregular submissions lately",
                              1: "Disengaged in class; needs follow-up"}[rating]
                    fb_rows.append(dict(student=s.roll_no, subject_code=code, participation_rating=rating,
                                        remark=remark, given_in_week=8))
                if rng.random() < (0.5 if shocked and w0 <= 7 else 0.75):
                    e7 = eng_lms[6]
                    survey_rows.append(dict(
                        respondent_email=s.personal_email if rng.random() < 0.12 else s.email,
                        course_satisfaction=int(np.clip(round(3.6 + 0.4 * e7 + rng.normal(0, 0.8)), 1, 5)),
                        feels_supported=int(np.clip(round(3.4 + 0.35 * e7 + rng.normal(0, 0.9)), 1, 5)),
                        workload_stress=int(np.clip(round(2.9 - 0.45 * e7 + rng.normal(0, 0.9)), 1, 5)),
                        submitted_week=7))
    return (pd.DataFrame(att_rows), pd.DataFrame(lms_rows), pd.DataFrame(exam_rows), pd.DataFrame(int_rows),
            pd.DataFrame(fb_rows), pd.DataFrame(survey_rows), pd.DataFrame(truth))


# ---------------------------------------------------------------- placement, skills, engagement
def placement_features(s, final=True):
    """Final-year style placement indicators for a latent student profile."""
    bonus = {"CSE": 10, "IT": 8, "ECE": 0, "MECH": -8}[s["dept"]]
    return dict(
        aptitude=float(np.clip(50 + 11 * s["ability"] + 6 * s["drive"] + rng.normal(0, 7), 10, 99)),
        coding=float(np.clip(42 + 13 * s["ability"] + 9 * s["drive"] + bonus + rng.normal(0, 8), 5, 99)),
        technical=float(np.clip(50 + 12 * s["ability"] + 8 * s["drive"] + bonus / 2 + rng.normal(0, 7), 10, 99)),
        soft=float(np.clip(55 + 10 * s["soft"] + 4 * s["extra"] + rng.normal(0, 7), 15, 99)),
    )


def make_placement_and_skills(students):
    rows, skill_rows = [], []
    for s in students.to_dict("records"):
        f = placement_features(s)
        yr = s["year"]
        n_apt = {4: int(rng.integers(3, 5)), 3: 2, 2: 1}[yr]
        n_cod = {4: int(rng.integers(2, 4)), 3: int(rng.integers(1, 3)), 2: 0}[yr]
        gain = 2.5 + 2.0 * max(s["drive"], -0.5)
        key = s["register_no"] if rng.random() < 0.6 else (s["email"] if rng.random() < 0.85 else s["personal_email"])
        for k in range(n_apt):
            sc = np.clip(f["aptitude"] - gain * (n_apt - 1 - k) + rng.normal(0, 3), 5, 100)
            rows.append(dict(candidate_id=key, test_type="Aptitude", attempt_month=f"2026-{3 + 2 * k:02d}",
                             score=f"{sc:.0f}%" if rng.random() < 0.5 else f"{sc:.0f}"))
        for k in range(n_cod):
            sc = np.clip(f["coding"] - gain * (n_cod - 1 - k) + rng.normal(0, 3), 0, 100)
            rows.append(dict(candidate_id=key, test_type="Coding", attempt_month=f"2026-{4 + 2 * k:02d}",
                             score=f"{sc:.0f}"))
        if yr >= 3:
            lam = (0.8 + 1.1 * max(s["drive"] + 0.5, 0)) if yr == 4 else (0.25 + 0.5 * max(s["drive"], 0))
            n_mock = int(min(rng.poisson(lam), 6))
            for k in range(n_mock):
                r = np.clip(2.6 + 0.45 * s["drive"] + 0.35 * s["soft"] + 0.15 * k + rng.normal(0, 0.4), 1, 5)
                rows.append(dict(candidate_id=key, test_type="Mock Interview", attempt_month=f"2026-{7 + k % 3:02d}",
                                 score=f"{r:.1f}/5"))
        if rng.random() < 0.92:
            yy, code, num = s["roll_no"][:2], s["roll_no"][2:4], s["roll_no"][4:]
            skill_rows.append(dict(student_ref=f"{yy}-{code}-{num}", technical_score=round(f["technical"]),
                                   soft_skill_score=round(f["soft"]), assessed_on="2026-08-20"))
    rows = pd.DataFrame(rows)
    dup = rows.sample(frac=0.02, random_state=C.SEED)
    return pd.concat([rows, dup]).sample(frac=1, random_state=1).reset_index(drop=True), pd.DataFrame(skill_rows)


EVENT_NAMES = {
    "Workshop": ["Git & GitHub Workshop", "IoT Hands-on Workshop", "Resume Building Workshop", "AI Tools Workshop",
                 "PCB Design Workshop", "CAD Modelling Workshop"],
    "Club Activity": ["Coding Club Weekly", "Robotics Club Meet", "Literary Club Session", "Photography Club Walk",
                      "Entrepreneurship Cell Meet", "Music Club Practice"],
    "Hackathon": ["Smart India Hackathon (Internal)", "HackFest 2026", "Code Sprint 24h", "GreenTech Hackathon"],
    "Symposium": ["National Technical Symposium", "Paper Presentation Contest", "Project Expo"],
    "Sports": ["Inter-department Cricket", "Athletics Meet", "Chess Championship", "Basketball League"],
    "Volunteering": ["NSS Blood Donation Camp", "Village Literacy Drive", "Tree Plantation Drive"],
    "Certification": ["NPTEL: Data Structures", "Coursera: Python for Everybody", "AWS Academy Cloud Foundations",
                      "Cisco NetAcad CCNA-1", "NPTEL: Industrial Safety", "Google Data Analytics Certificate"],
}


def make_engagement(students):
    rows = []
    for s in students.to_dict("records"):
        for sem_label, months in [(C.SEMESTERS[1], ["2026-01", "2026-02", "2026-03", "2026-04"]),
                                  (C.SEMESTERS[2], ["2026-07", "2026-08", "2026-09", "2026-10"])]:
            lam = np.exp(0.35 + 0.65 * s["extra"] + 0.2 * s["drive"])
            if sem_label == C.CURRENT_SEM:
                lam *= 0.6  # semester only half over
            n = int(min(rng.poisson(lam), 14))
            tw = np.array([0.22, 0.24, 0.08 + (0.06 if s["dept"] in ("CSE", "IT") else 0) + 0.04 * max(s["drive"], 0),
                           0.10, 0.12, 0.10, 0.08 + 0.06 * max(s["drive"], 0)])
            tw = tw / tw.sum()
            types = list(EVENT_NAMES)
            for _ in range(n):
                t = types[rng.choice(len(types), p=tw)]
                rows.append(dict(event_month=rng.choice(months), event_type=t, event_name=rng.choice(EVENT_NAMES[t]),
                                 participant_name=name_variant(s["first"], s["last"], s["name_style"]),
                                 department=rng.choice(DEPT_LABEL_VARIANTS[s["dept"]]),
                                 year_of_study=rng.choice(YEAR_LABEL_VARIANTS[s["year"]])))
    return pd.DataFrame(rows)


def make_alumni():
    """Last graduating batch (admitted 2022) with final placement outcomes, from the placement cell."""
    rows = []
    for dept, (_, _, _, n) in C.DEPTS.items():
        for i in range(n):
            z = np.clip(rng.standard_normal(5), -2.0, 2.5)
            s = dict(dept=dept, ability=z[0], drive=0.3 * z[0] + 0.95 * z[2], extra=z[3], soft=0.4 * z[3] + 0.9 * z[4])
            f = placement_features(s)
            cgpa = float(np.clip(7.0 + 0.9 * s["ability"] + 0.2 * s["drive"] + rng.normal(0, 0.35), 4.8, 9.8))
            backlogs = int(rng.poisson(max(0.05, 0.6 - 0.9 * s["ability"]))) if cgpa < 7.2 else 0
            mocks = int(min(rng.poisson(0.8 + 1.1 * max(s["drive"] + 0.5, 0)), 6))
            mock_rating = float(np.clip(2.6 + 0.45 * s["drive"] + 0.35 * s["soft"] + rng.normal(0, 0.4), 1, 5)) if mocks else np.nan
            certs = int(rng.poisson(np.exp(0.2 + 0.3 * s["drive"] + 0.4 * s["extra"])))
            internship = int(rng.random() < sigmoid(-1 + 0.8 * s["drive"]))
            eligible = cgpa >= C.PLACEMENT_CGPA_MIN and backlogs == 0
            logit = (1.6 + 1.1 * (f["coding"] - 50) / 15 + 0.8 * (f["aptitude"] - 52) / 13 + 0.75 * (mocks - 1.6) / 1.3
                     + 0.45 * ((mock_rating if mocks else 2.2) - 2.8) / 0.6 + 0.6 * (f["soft"] - 56) / 12
                     + 0.25 * (f["technical"] - 52) / 14 + 0.08 * (certs - 1.5) / 1.3 + 0.35 * internship
                     - (3.0 if not eligible else 0))
            placed = rng.random() < sigmoid(logit)
            tier = None
            if placed:
                tier = "Dream (8+ LPA)" if f["coding"] > 72 and rng.random() < 0.6 else (
                    "Core (5-8 LPA)" if rng.random() < 0.55 else "Mass recruiter (3-5 LPA)")
            rows.append(dict(alumni_id=f"22{C.DEPTS[dept][2]}{i + 1:03d}", dept=dept, final_cgpa=round(cgpa, 2),
                             standing_backlogs=backlogs, best_aptitude=round(f["aptitude"]), best_coding=round(f["coding"]),
                             technical_score=round(f["technical"]), soft_skill_score=round(f["soft"]),
                             mock_interviews=mocks, avg_mock_rating=round(mock_rating, 1) if mocks else None,
                             certifications=certs, internship=internship, placed="Yes" if placed else "No",
                             offer_tier=tier))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- mess the exports up
def export_sis(students):
    df = students[["roll_no", "name", "gender", "dept", "batch", "year", "section", "residence", "first_graduate",
                   "mentor", "hsc_percent", "email"]].copy()
    df = df.rename(columns={"roll_no": "Roll No", "name": "Student Name", "gender": "Gender", "dept": "Dept",
                            "batch": "Batch", "year": "Year", "section": "Sec", "residence": "Residence",
                            "first_graduate": "First Graduate", "mentor": "Mentor", "hsc_percent": "HSC %",
                            "email": "Official Email"})
    m = rng.random(len(df)) < 0.06
    df.loc[m, "Student Name"] = df.loc[m, "Student Name"].str.upper() + "  "
    m = rng.random(len(df)) < 0.05
    df.loc[m, "Dept"] = df.loc[m, "Dept"].map(lambda d: rng.choice(DEPT_LABEL_VARIANTS[d]))
    dup = df.sample(n=14, random_state=3)
    return pd.concat([df, dup]).sample(frac=1, random_state=2).reset_index(drop=True)


def mess_roll(r):
    x = rng.random()
    if x < 0.15:
        return r.lower()
    if x < 0.22:
        return f" {r} "
    if x < 0.27:
        return r[:4] + str(int(r[4:]))  # 23CS045 -> 23CS45
    return r


def export_attendance(att):
    att = att.copy()
    rolls = att["roll_no"].unique()
    mapping = {r: mess_roll(r) for r in rolls}
    att["roll_no"] = att["roll_no"].map(mapping)
    bad = rng.random(len(att)) < 0.003
    att.loc[bad, "classes_attended"] = att.loc[bad, "classes_held"] + 1   # impossible values
    dup = att.sample(frac=0.01, random_state=4)
    drop = rng.random(len(att)) < 0.01                                     # missing uploads
    return pd.concat([att[~drop], dup]).reset_index(drop=True).rename(columns={"roll_no": "RollNo"})


def export_lms(lms, students):
    users = students[["roll_no", "email", "personal_email", "first", "last"]].copy()
    users["lms_user_id"] = ["u" + str(10000 + i) for i in rng.permutation(len(users))]
    personal = rng.random(len(users)) < 0.14
    users["login_email"] = np.where(personal, users["personal_email"], users["email"])
    users["display_name"] = [f"{f} {l}" if rng.random() < 0.7 else f"{f.lower()} {l.lower()}"
                             for f, l in zip(users["first"], users["last"])]
    dept_year = students.set_index("roll_no")[["dept", "year"]]
    users["enrolled_courses"] = [";".join(c for c, _, _ in subjects_for(dept_year.at[r, "dept"], 2 * dept_year.at[r, "year"] - 1))
                                 for r in users["roll_no"]]
    act = lms.merge(users[["roll_no", "lms_user_id"]], on="roll_no").drop(columns="roll_no")
    act = act[["lms_user_id", "semester", "week", "logins", "minutes", "assignments_due",
               "assignments_submitted", "quiz_attempts"]]
    bad = rng.random(len(act)) < 0.002
    act.loc[bad, "minutes"] = -act.loc[bad, "minutes"]
    dup = act.sample(frac=0.015, random_state=5)
    act = pd.concat([act, dup]).sample(frac=1, random_state=6).reset_index(drop=True)
    return users[["lms_user_id", "login_email", "display_name", "enrolled_courses"]], act


def export_exams(exams):
    ex = exams.copy()
    ex["register_no"] = ex["register_no"].astype(str)
    corrupt_regs = rng.choice(ex["register_no"].unique(), size=30, replace=False)
    m = ex["register_no"].isin(corrupt_regs)
    ex.loc[m, "register_no"] = ex.loc[m, "register_no"].map(lambda r: f"{int(r) / 1e11:.5f}E+11")  # Excel damage
    return ex


def generate():
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    students = make_students()
    att, lms, exams, interventions, fb, survey, truth = simulate(students)
    placement, skills = make_placement_and_skills(students)
    engagement = make_engagement(students)
    alumni = make_alumni()
    lms_users, lms_act = export_lms(lms, students)

    export_sis(students).to_csv(C.RAW_DIR / "01_sis_student_master.csv", index=False)
    export_exams(exams).to_csv(C.RAW_DIR / "02_exam_cell_results.csv", index=False)
    export_attendance(att).to_csv(C.RAW_DIR / "03_attendance_weekly.csv", index=False)
    lms_users.to_csv(C.RAW_DIR / "04a_lms_users.csv", index=False)
    lms_act.to_csv(C.RAW_DIR / "04b_lms_weekly_activity.csv", index=False)
    engagement.to_csv(C.RAW_DIR / "05_student_affairs_events.csv", index=False)
    placement.to_csv(C.RAW_DIR / "06_placement_training_scores.csv", index=False)
    skills.to_csv(C.RAW_DIR / "07_skills_assessment.csv", index=False)
    fb.to_csv(C.RAW_DIR / "08a_faculty_feedback.csv", index=False)
    survey.to_csv(C.RAW_DIR / "08b_student_survey.csv", index=False)
    interventions.to_csv(C.RAW_DIR / "09_intervention_log_past.csv", index=False)
    alumni.to_csv(C.RAW_DIR / "10_alumni_placement_outcomes.csv", index=False)
    truth.to_csv(C.RAW_DIR / "_ground_truth_DO_NOT_USE.csv", index=False)
    return {p.name: sum(1 for _ in open(p)) - 1 for p in sorted(C.RAW_DIR.glob("*.csv"))}


if __name__ == "__main__":
    for k, v in generate().items():
        print(f"{k:45s} {v:>8,} rows")
