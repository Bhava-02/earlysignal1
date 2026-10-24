# EarlySignal: Student Success Intelligence

**KPMG Smart Campus Analytics challenge.** Most dashboards show which students are struggling.
EarlySignal shows which students **will** struggle, weeks before marks drop, **why**, the **smallest
action** that changes it, and **whether that action worked**.

## React dashboard (Round 1 features, teal theme)

Round 1 features only: Dashboard, Students, HODs and faculty, Student profile (Overview, Academic, Attendance, LMS,
Engagement, Placement, Skills, Feedback, Action plan with Path to Green and what-if), Analytics, Segments (cards),
Placement, Interventions (suggested actions, follow-ups, what works, weekly report), AI assistant, Data sources,
Data quality and How it works. Line charts are shown as bar charts and every download is a PDF.

It comes in two forms:

| | EarlySignal server (recommended) | Single file `docs/index.html` |
|---|---|---|
| Where | Hugging Face **Docker** Space (`deploy/space/`), or any machine: `uvicorn api:app` | GitHub Pages, a Hugging Face **Static** Space, or just open the file |
| Data | Loads the latest data from the server; Data sources page connects to the college server or takes the Excel upload | The sample college, built into the file |
| Continue with Google, SMS codes | Yes, once the Firebase settings are added | Yes, with an `earlysignal-config.json` next to the file (see below) |
| Codes by email | Yes, once Brevo (or SMTP) is set up | No |

### Sign-in

Users register on **Create an account** (name, phone, email, role, username, password) and return to the sign-in
page. They sign in with username and password, or **Continue with Google** (matched to the account's email). Staff then
choose where to get a 6-digit code: **email** (sent by the server) or **SMS** (sent by Firebase). Students sign in
without a code. Built-in demo accounts have made-up emails and phones, so their code is shown on screen; create your
own account with your real email and phone to receive real codes. If neither email nor SMS is set up, the code is
shown on screen too.

| Built-in role | Username | Password | Sees |
|---|---|---|---|
| Admin | `admin` | `admin123` | Everything; filter by HOD and mentor |
| Principal | `principal` | `principal123` | Same as admin |
| Head of department | `hod.cse` (also `hod.it`, `hod.ece`, `hod.mech`) | `hod123` | Their department; filter by their mentors |
| Class mentor | first initial + surname, e.g. `r.lakshmi`, `p.selvi` | `faculty123` | Only their mentees |
| Student | roll number, e.g. `23CS001` | `student123` | Only their own profile |

Accounts and action logs are kept in the browser that created them (there is no account database), so an account
made on one laptop does not exist on another. This is a demo, not production security.

### Put the server on Hugging Face (free)

```bash
cd frontend && npm install && npm run build && cd ..   # the app for the server (frontend/dist)
python deploy/build_space.py                          # writes deploy/space/
```

1. On huggingface.co: **New Space**, SDK **Docker**, blank template, free CPU.
2. **Files > Add file > Upload files**: drag in everything inside `deploy/space/` (keep the folders). The Space
   builds for about 5 minutes, then opens with the sample college.
3. **Settings > Variables and secrets**: add the settings below. The Space restarts with them.
4. Open the app at its direct address, **https://YOUR-NAME-SPACE-NAME.hf.space** (the app inside the
   huggingface.co page cannot open Google's sign-in window).

| Setting | Type | What it does |
|---|---|---|
| `EARLYSIGNAL_ADMIN_KEY` | secret | Changing data (sync, upload, switch back) needs this key, typed at the top of Data sources. Strongly recommended on a public Space. |
| `BREVO_API_KEY` | secret | Emailed sign-in codes through Brevo |
| `EMAIL_FROM` | variable | The sender address you verified in Brevo |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_APP_ID` | variables | Continue with Google and SMS codes |
| `EARLYSIGNAL_ADMIN_EMAIL` | variable | Shown when the AI assistant cannot answer a question |

Hugging Face blocks outgoing mail ports, so emailed codes go through Brevo's web API. On a host that allows SMTP,
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` work instead (for Gmail: an app password).

**Free Spaces restart now and then.** After a restart the Space shows the sample college again; uploads and syncs
need to be repeated (or use paid persistent storage).

### Emailed codes: Brevo (free, 300 emails a day)

1. Sign up at brevo.com.
2. **Senders, Domains & Dedicated IPs > Senders > Add a sender**: your email address; click the link Brevo emails you.
3. **SMTP & API > API keys > Generate a new API key**.
4. Put the key in `BREVO_API_KEY` and the sender address in `EMAIL_FROM`.

Codes sent from a free email address (such as Gmail) through Brevo can land in spam; tell users to check it. A college
domain verified in Brevo fixes that.

### Continue with Google and SMS codes: Firebase

1. console.firebase.google.com: **Add project** (Google Analytics not needed).
2. **Build > Authentication > Get started > Sign-in method**: enable **Google** (pick a support email) and **Phone**.
3. **Authentication > Settings > Authorized domains > Add domain**: `YOUR-NAME-SPACE-NAME.hf.space` (and your
   GitHub Pages domain, if you use the single file there).
4. **Project settings (gear) > General > Your apps > Web (`</>`)**: register an app and copy `apiKey`, `authDomain`,
   `projectId` and `appId` into the four `FIREBASE_` settings.
5. SMS to real phones needs the **Blaze (pay as you go)** plan; Firebase charges per SMS. Without it, add your number
   under **Phone > Phone numbers for testing** with a fixed code: no SMS is sent, but the whole flow works for a demo.

For the single file on a static host, put the same four values in a file named `earlysignal-config.json` next to
`index.html`:

```json
{ "firebase": { "apiKey": "...", "authDomain": "...", "projectId": "...", "appId": "..." },
  "adminEmail": "admin@yourcollege.edu.in" }
```

### Rebuild after code or data changes

```bash
python -m src.pipeline --web                  # scores everyone and writes data/processed/web/bundle_r1.json
cd frontend && npm install
npm run build                                 # frontend/dist, for the server
npm run build:single                          # frontend/dist-single/index.html, the single file
cp dist-single/index.html ../docs/index.html
```

Run the server locally: `pip install -r requirements-web.txt`, then `uvicorn api:app --port 7860` and open
http://localhost:7860. For development: `cd frontend && npm run dev`. Stack: Python (pandas, scikit-learn, FastAPI)
for the engine and server; React 18, React Router, Recharts, jsPDF and the Firebase web SDK (built with Vite) for the
dashboard. The what-if sliders and Path to Green re-run the exported Round 1 models in the browser.

## Round 1 live demo (Streamlit)

**Open:** https://earlysignal-entf9xh4ukoaymefyelgew.streamlit.app

Sign in with one click on the login page (**Principal / Admin** or **HOD, CSE**), or type
`admin@college.edu.in` / `admin123`. The very first visit after the app wakes up takes about 30 seconds while it
scores the 1,080 sample students; after that every page is instant.

---

## Deploy it free, always on (GitHub + Streamlit Community Cloud)

The link keeps working when your laptop or Nimbus workspace is off.

1. **Create the repository.** On github.com: **New repository** → name `earlysignal` → **Public** → **Create**.
2. **Upload the project.** On the new repository's page: **uploading an existing file**. Open the unzipped
   `earlysignal` folder, select **everything inside it** (including the `.streamlit` and `.github` folders) and drag
   it onto the page. `app.py` must end up at the top level of the repository, not inside another folder.
   Press **Commit changes**.
3. **Deploy.** Go to share.streamlit.io → sign in with GitHub → **Create app** → **Deploy a public app from GitHub**
   → Repository `your-name/earlysignal`, Branch `main`, Main file path `app.py`. Under **App URL** choose a name,
   e.g. `earlysignal-kpmg`. Optional: **Advanced settings** → Python 3.12. Press **Deploy**.
   The first build takes 2 to 4 minutes; you then get `https://earlysignal-kpmg.streamlit.app`.
4. **Keep it awake for the jury.** Free apps sleep after 12 hours without visitors (anyone can wake them with one
   click, but it takes a minute). In the repository open `.github/workflows/keep-awake.yml`, edit the `APP_URL`
   line to your link, and commit. GitHub then visits the app every 6 hours. Check it once under the **Actions** tab
   → **Keep the demo awake** → **Run workflow**.
5. **Every later change:** upload the changed files to the repository; Streamlit Cloud redeploys by itself.

Notes: everyone using the link shares the same app, so if a juror uploads a file or syncs, the others see that data
too (a notice at the top says so, with a one-click way back). Restarting the app always returns to the sample
college. Nothing secret is needed: there are no passwords or API keys in the repository.

---

## Run it on Nimbus (about 5 minutes)

1. **Open your Python workspace** in Nimbus (the one where the Streamlit test worked).
2. **Upload the project.** Drag the unzipped `earlysignal` folder (or `earlysignal.zip`) into the file list on the
   left of VS Code.
3. **Open a terminal** (menu → Terminal → New Terminal) and run these lines one at a time
   (if you uploaded the zip, first run `unzip earlysignal.zip`):

   ```bash
   cd earlysignal
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. **Open the app** the same way you opened the test page: the proxy link ending in `/proxy/8501/`.
   The first load takes about 15 seconds while it builds the scores. After that it is instant.
5. **Sign in** with `admin@college.edu.in` and password `admin123` (whole college), or
   `hod.cse@college.edu.in` / `hod123` to see the app as the CSE head of department.
   These are demo sign-ins, not real security. Refreshing the browser signs you out.

To stop the app press `Ctrl + C` in the terminal. To start it again: `streamlit run app.py`.

**Optional AI features.** Get a free key at aistudio.google.com, then paste it into
*AI assistant key (optional)* at the bottom of the app's menu. Without a key, everything still works and uses built-in
template text. Only anonymised numbers are ever sent to the AI.

**Rebuild everything from scratch** (new data, retrained models): `python -m src.generate_data` then
`python -m src.pipeline`.

---

## What's inside

A sign-in page, then eleven pages in the left menu. Every list of students has a **View** button that opens that
student's profile.

| Page | What it shows | Brief criteria |
|---|---|---|
| Dashboard | Greeting, 4 summary cards, Student Success trend, risk distribution, students needing attention, this week's priorities | Dashboard, trends, insights |
| Students | Searchable directory with department, year and risk filters | Unified student view |
| Student profile | Score ring, and 9 tabs: Overview, Academic, Attendance, LMS, Engagement, Placement, Skills, Feedback, Action plan | Explainable score (bonus) |
| Analytics | Attendance, engagement and placement trends, risk factors, and proof that the early warning works | Key trends, risk identification |
| Segments | 7 student groups as cards, each with a plan you can assign to the whole group | Segmentation (bonus) |
| Placement | Who isn't job-ready, and what gets students placed here | Placement risk |
| Interventions | Suggested actions, follow-ups, what works, and a downloadable weekly report | Decision intelligence |
| AI assistant | Plain-English questions, e.g. "final years with CGPA above 8 and no mock interviews" | AI |
| Data sources | Connect read-only to the college's ERP and Moodle servers with nightly sync, or upload one Excel file | Real-world use |
| Data quality | How 12 messy files became one record per student | Data integration (30%) |
| Fairness | Do flags fall unfairly on any group? | Problem understanding |
| How it works | What the Success Score and risk level mean | Score note |

## Using a college's own data

### Option 1: connect to the college's servers (automatic)

How colleges actually store this data:

| Data | Where it usually lives |
|---|---|
| Students, attendance, internal marks, results | The college ERP: a MySQL, PostgreSQL, SQL Server or Oracle database on a campus server or the vendor's cloud. Attendance is stored per class hour (one row per student per period, P / A / OD). |
| Online activity, assignments | Moodle's own database (MySQL or PostgreSQL): `mdl_user`, `mdl_logstore_standard_log`, `mdl_assign`, `mdl_assign_submission` |
| University results | Excel / PDF from the university portal, usually imported into the ERP |
| Placement training, events, feedback | Excel sheets and Google Forms kept by each office |

**Data sources → College server** connects to these databases **read-only**:

1. **Connect.** The college's IT team creates a read-only login. Enter the server address, database and login
   (MySQL / MariaDB, PostgreSQL, SQL Server or Oracle). Press **Test connection**.
2. **Map once.** 14 short SELECT queries tell EarlySignal where students, marks, attendance and Moodle activity
   live. The defaults fit the demo server and a typical ERP; IT edits table names once. Anything that is not a
   single SELECT is refused, and on PostgreSQL / MySQL the session itself is opened read-only.
3. **Sync now and build.** Period-wise attendance and Moodle timestamps are turned into semester and week using the
   academic calendar, then checked and scored exactly like an upload. For nightly sync, run on a machine inside the
   campus network:
   `0 2 * * * cd /opt/earlysignal && EARLYSIGNAL_ERP_PASSWORD=... python -m src.sync`
   Passwords are never saved by EarlySignal.

**Try it without a college:** choose **Demo college server** and press **Sync now and build**. The demo server is an
ERP database (14 tables, 855,290 period-wise attendance rows) and a Moodle database built from the sample college
(`python -m src.demo_server`, about 15 s, created on first use). Synced through the server path, every student gets
exactly the same scores as the sample college, which shows nothing is lost on the way.

**Prove it's live (for judges):** on the demo server, pick a student who is doing well and press **Record it on the
college server**. This plays the college's attendance system and Moodle: from week 7 the student is marked absent,
stops logging in and stops submitting. Nothing on the dashboard changes until you press **Sync now and build**; then
a before/after table shows, for example, attendance 99% → 66%, risk Low → At Risk, reason "Attendance fell 72 pts in
the last 4 weeks", group Placement-Ready Stars → Critical: Act This Week. The top bar shows "● Live, synced <time>".
**Look inside the server** shows the raw tables (for example period-wise `attendance` rows with dates and P / A / OD),
and **Run on the server** runs any of the 14 queries live. **Undo** rebuilds the demo server.

Also tested against a real PostgreSQL 16 server over TCP with a read-only user: connected, synced 855,290
attendance rows in about 10 s, and an attempted UPDATE was refused by the database.

Other drivers: `pip install -r requirements-server.txt` (PostgreSQL, SQL Server, Oracle). MySQL works out of the box.

If the ERP is a vendor's cloud product without database access, use its scheduled report export with option 2, or ask
the vendor for an API.

### Option 2: upload one Excel file (manual)

Open **Data sources → Excel upload**. Three steps, one Excel file:

1. **Download the template.** One workbook with a "Start here" sheet and a sheet per kind of record. Only three are
   needed: **Students** (one row per student), **Marks** (one row per student, subject and semester) and
   **Attendance** (one row per student per week). LMS, Other details (placement training, skills, activities,
   feedback), Past actions and Past placements are optional. A **filled example** (360 sample CSE students) shows
   what goes where.
2. **Upload the filled file** (or one CSV per sheet). It is checked at once and every problem is explained in plain
   words ("14 rows have a roll number that is not in Students").
3. **Type the college name and press "Build my dashboard".** Semesters, the current week and the departments are read
   from the file. About a minute later every page uses the new data. If anything goes wrong, nothing changes.
   **"Switch back to the sample college"** returns to the demo data.

Three rules: the same Roll No in every sheet; Semester means the semester number (1 to 8); include this semester and
the two before it (the early warning learns from the two past semesters). Column names can differ a little
("CIA 1", "Internal 1", "Reg No", "Total Classes", "Present" all work), any roll-number style and any department names
work, grades can be letters or grade points, and internal marks can be out of 50 or 100.

Tested with a college that looks nothing like the sample (10-digit numeric roll numbers, EEE and AI & DS, first-year
students, an even semester, grade points, marks out of 100, three CSV files only): with just the three required sheets
the early warning still caught 70% of failing students by week 6, against 46% for the usual lists.

IT teams can instead upload raw exports from each system (12 files with different IDs) under **Advanced**; that is how
the sample college is built.

### The data (synthetic, deliberately messy)

`data/raw/` holds 12 files exported "from" 9 campus systems, each identifying students differently:

| File | System | How it identifies a student |
|---|---|---|
| 01_sis_student_master | SIS / ERP | Roll No `23CS045` (the master ID) |
| 02_exam_cell_results | Exam cell | 12-digit register no, some damaged by Excel (`4.12723E+11`) |
| 03_attendance_weekly | Attendance | Roll No in mixed formats (`23cs045`, ` 23CS045 `, `23CS45`) |
| 04a/04b_lms | Moodle LMS | LMS user id + login email (some personal Gmail) |
| 05_student_affairs_events | Student affairs | Only name + department + year, with spelling variants |
| 06_placement_training_scores | Placement vendor | Register no, official email or personal email |
| 07_skills_assessment | Skills platform | `23-CS-045` |
| 08a/08b feedback | Faculty portal, Google Form | Lower-case roll no / respondent email |
| 09_intervention_log_past | Mentors | Past actions and when |
| 10_alumni_placement_outcomes | Placement cell | Last year's graduates and who got placed |

`_ground_truth_DO_NOT_USE.csv` records what the generator really did (who had a disengagement episode). It is only for
checking the generator and is **never read by the models or dashboard**.

### Code

```
app.py                 starts the app and builds the page menu
views/                 one file per page (login, dashboard, students, profile, analytics, segments, ...)
src/ui.py              shared look, data loading, student lists with View buttons
src/connector.py       read-only connection to the college ERP / Moodle servers, default queries, date -> week
src/demo_server.py     builds the demo college server (ERP + Moodle databases) from the sample college
src/sync.py            nightly sync from the command line (cron / Task Scheduler)
src/build.py           installs new data and rebuilds, putting the old data back if anything fails
src/simple_upload.py   the one-workbook template: checks, column-name matching, conversion
src/sources.py         the list of raw source files, required columns, and file recognition (advanced upload)
src/generate_data.py   builds the synthetic college and its messy exports
src/integrate.py       cleaning + identity matching + quality report
src/features.py        weekly behaviour features, academic history
src/models.py          early-warning model (with back-test) + placement model
src/scoring.py         Student Success Score and its exact contributions
src/segments.py        segment rules and playbooks
src/whatif.py          what-if simulator and Path to Green
src/analytics.py       what works, fairness, insights
src/ai.py, src/nlq.py  optional Gemini layer + plain-English query parser (with offline fallbacks)
src/pipeline.py        runs everything, writes data/processed/
docs/SUCCESS_SCORE_NOTE.md   the required note on the score
```

---

## 3-minute demo script

1. **Sign in, Dashboard (20 s).** "191 students are at high risk this week, 15 of them new. Here's the trend, the mix of
   academic and placement risk, and who to contact first."
2. **Analytics, the proof chart (30 s).** "Tested on a semester it had never seen: by week 6 it caught 78% of the students
   who went on to fail. The usual attendance and marks lists caught 41%."
3. **Student profile (60 s).** Press View on a student. Overview: key facts, the factors pulling the score down, why they
   are flagged. Show the LMS tab (activity dropping) and the Action plan tab (smallest plan back on track, conversation
   guide). Press "Create action plan".
4. **Segments and Placement (40 s).** "129 students have good marks but aren't job-ready. One more mock interview roughly
   doubles the odds of getting placed; a certificate adds 13%."
5. **Interventions (20 s).** Show suggested actions and statuses, then press "Generate report".
6. **Data sources (30 s).** Choose the demo college server and press "Sync now and build". "EarlySignal connects
   read-only to the college ERP and Moodle, the way colleges actually store data: 855,290 period-wise attendance
   rows read in seconds, every night, no spreadsheets. Colleges without database access upload one Excel file instead."
7. **Close.** "Not just a dashboard: an early-warning system that tells each mentor what to do this week."
