import io
import json
import zipfile

import pandas as pd
import streamlit as st

from src import build
from src import config as C
from src import simple_upload as su
from src import ui
from src.sources import SOURCES, detect

EXAMPLE = C.ROOT / "assets" / "example_college_CSE.xlsx"
ICON = {"ok": "✅", "warn": "⚠️", "skip": "➖", "error": "❌"}
RANK = {"error": 3, "warn": 2, "ok": 1, "skip": 0}


# ---------------------------------------------------------------- shared
def finish():
    st.cache_data.clear()
    st.cache_resource.clear()
    import importlib
    importlib.reload(C)


def apply(files, settings):
    """Save the college's data, point the settings at it and rebuild. Puts everything back if it fails."""
    with st.spinner("Matching, scoring and training on your students. This takes about a minute..."):
        ok, log = build.install(files, settings)
    if ok:
        finish()
        st.success("Done. Every page now uses your college's data.")
        st.page_link(ui.PAGES["dashboard"], label="Open the dashboard", icon=":material/dashboard:")
        return True
    st.error("The data could not be processed, so nothing was changed. Details for whoever set this up:")
    st.code(log)
    return False


def reset_to_sample():
    with st.spinner("Switching back to the sample college..."):
        ok, log = build.reset_to_sample()
    finish()
    if ok:
        st.success("Back on the sample college data.")
    else:
        st.error("Rebuild failed:")
        st.code(log)


def show_checks(res):
    """The plain-English checklist, one line per sheet."""
    order = list(su.SHEETS) + ["Semesters"]
    by = {}
    for c in res["checks"]:
        by.setdefault(c["sheet"], []).append(c)
    html = ""
    for s in sorted(by, key=order.index):
        worst = max(by[s], key=lambda c: RANK[c["status"]])["status"]
        text = " ".join(c["text"] for c in by[s])
        html += f"<div class='chk'><span>{ICON[worst]}</span><b>{s}</b><span class='t'>{text}</span></div>"
    st.markdown(html, unsafe_allow_html=True)


def current_source(meta):
    if meta.get("using_sample", True):
        return ui.pill("Showing: sample college data", "blue")
    try:
        src = json.loads(C.SETTINGS_FILE.read_text()).get("source", {})
    except Exception:
        src = {}
    if src.get("type") == "server":
        return ui.pill(f"Showing: live server data ({meta.get('college_name', '')}), synced {src.get('synced_at', '')}",
                       "low")
    return ui.pill(f"Showing: your uploaded data ({meta.get('college_name', '')})", "low")


CSS = """<style>
.sheetrow {display:flex; gap:10px; align-items:center; padding:7px 0; border-bottom:1px solid #eef0f4; font-size:.9rem;}
.sheetrow b {min-width:120px; color:#1d2433;} .sheetrow .pill {min-width:70px; text-align:center;}
.sheetrow span:last-child {color:#5b6475;}
.rule {display:flex; gap:10px; align-items:flex-start; padding:6px 0; font-size:.9rem; color:#3b4252;}
.rule .n {background:#b3163a; color:#fff; border-radius:50%; width:22px; height:22px; flex:none; display:flex;
          align-items:center; justify-content:center; font-size:.75rem; font-weight:700;}
.chk {display:flex; gap:10px; padding:8px 2px; border-bottom:1px solid #eef0f4; font-size:.9rem; align-items:flex-start;}
.chk b {min-width:120px; color:#1d2433;} .chk .t {color:#3b4252;}
.flow {display:flex; gap:12px; flex-wrap:wrap; margin: 4px 0 6px 0;}
.flow > div {flex:1 1 220px; background:#fff; border:1px solid #eceef3; border-radius:14px; padding:14px 16px;}
.flow .h {font-weight:700; color:#1d2433; margin-bottom:4px;} .flow .h span {color:#b3163a; margin-right:6px;}
.flow .d {font-size:.86rem; color:#5b6475; line-height:1.45;}
</style>"""


@st.cache_data(show_spinner=False)
def template():
    return su.template_bytes()


@st.cache_data(show_spinner=False, max_entries=3)
def check(files):
    raw, notes = su.read_files(list(files))
    return su.prepare(raw), notes


# ---------------------------------------------------------------- page
def render():
    from views import server
    meta = ui.data()["meta"]
    ui.title("Data sources", "Connect EarlySignal to the college's own servers, or upload an Excel file.")
    st.markdown(current_source(meta), unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)
    st.write("")
    t1, t2 = st.tabs(["College server (automatic)", "Excel upload (manual)"])
    with t1:
        server.render(meta)
    with t2:
        excel(meta)


def excel(meta):
    using_sample = meta.get("using_sample", True)
    # 1. template
    with st.container(border=True):
        st.markdown("### 1. Download the template")
        a, b = st.columns([1, 1.25], gap="large")
        with a:
            st.markdown("<div class='muted'>One Excel file with a sheet for each kind of record. "
                        "Only the first three sheets are needed.</div>", unsafe_allow_html=True)
            st.write("")
            st.download_button("Download the template (Excel)", template(), "EarlySignal_template.xlsx",
                               type="primary", icon=":material/download:", use_container_width=True)
            if EXAMPLE.exists():
                st.download_button("Download a filled example", EXAMPLE.read_bytes(), "EarlySignal_example_CSE.xlsx",
                                   icon=":material/table_view:", use_container_width=True)
                st.caption("360 sample CSE students, to see what goes where. You can upload it to try the steps.")
            st.write("")
            for i, t in enumerate(["Use the <b>same Roll No</b> in every sheet.",
                                   "<b>Semester</b> means the semester number, 1 to 8.",
                                   "Include <b>this semester and the two before it</b>. The early warning learns "
                                   "from the two past semesters."], start=1):
                st.markdown(f"<div class='rule'><span class='n'>{i}</span><span>{t}</span></div>",
                            unsafe_allow_html=True)
        with b:
            rows = "".join(
                f"<div class='sheetrow'><b>{s}</b>{ui.pill('Needed', 'high') if v['required'] else ui.pill('Optional')}"
                f"<span>{v['per']}</span></div>" for s, v in su.SHEETS.items())
            st.markdown(rows, unsafe_allow_html=True)
            st.caption("Column names can differ a little (CIA 1, Internal 1 and Test 1 all work). Example rows are "
                       "ignored. Separate CSV files, one per sheet, also work.")

    # 2. upload + checks
    ready = None
    with st.container(border=True):
        st.markdown("### 2. Upload the filled file")
        up = st.file_uploader("Excel workbook, or one CSV per sheet", type=["xlsx", "csv"], accept_multiple_files=True,
                              key="simple_files", label_visibility="collapsed")
        if up:
            with st.spinner("Reading and checking your file..."):
                res, notes = check(tuple((f.name, f.getvalue()) for f in up))
            show_checks(res)
            for n in notes:
                st.caption("⚠️ " + n)
            st.write("")
            if res["ok"]:
                f = res["facts"]
                st.success(f"Ready: {f['students']:,} students in {f['depts']} department(s). Week {f['week']} of "
                           f"{f['weeks_per_sem']} this semester.")
                ready = res
            else:
                st.error("Fix the items marked ❌ in your file and upload it again.")

    # 3. build
    with st.container(border=True):
        st.markdown("### 3. Build your dashboard")
        c = st.columns([1.6, 1.2, 1.2], vertical_alignment="bottom")
        name = c[0].text_input("College name", value=meta.get("college_name") if not using_sample else "",
                               placeholder="e.g. Sri Venkateswara College of Engineering")
        build_btn = c[1].button("Build my dashboard", type="primary", use_container_width=True,
                                disabled=ready is None, icon=":material/rocket_launch:")
        reset = c[2].button("Switch back to the sample college", use_container_width=True, disabled=using_sample,
                            key="reset_excel")
        st.caption("Takes about a minute. If anything goes wrong, nothing changes. Only the college name is typed; "
                   "semesters, current week and departments are read from your file.")
    if build_btn and ready:
        apply(ready["files"], dict(college_name=name.strip() or "My College", **ready["settings"]))
    if reset:
        reset_to_sample()

    with st.expander("Advanced: upload raw exports from each campus system (12 separate files)"):
        advanced(using_sample)


# ---------------------------------------------------------------- advanced: raw system exports
@st.cache_data(show_spinner=False)
def templates_zip():
    """Every raw source file's columns plus 5 example rows from the sample college."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, s in SOURCES.items():
            p = C.SAMPLE_RAW_DIR / fname
            df = pd.read_csv(p, nrows=5) if p.exists() else pd.DataFrame(columns=s["cols"])
            z.writestr(fname, df.to_csv(index=False))
        z.writestr("README.txt", "Fill one file per system. Keep the column names exactly as in each template.\n"
                                 "Required: 01 (student list), 02 (exam results), 03 (weekly attendance). Others are optional.\n")
    return buf.getvalue()


def advanced(using_sample):
    st.markdown("<div class='muted'>For IT teams who want EarlySignal to match students across systems that use "
                "different IDs (register numbers, LMS emails, names only). This is how the sample college was "
                "built. Most colleges should use the simple template above.</div>", unsafe_allow_html=True)
    st.download_button("Download raw-export templates (zip)", templates_zip(), "earlysignal_raw_templates.zip",
                       icon=":material/download:")
    T = pd.DataFrame([{"File": k, "What it is": v["label"], "From": v["system"],
                       "Needed?": "Required" if v["required"] else "Optional"} for k, v in SOURCES.items()])
    st.dataframe(T, hide_index=True, height=250)
    files = st.file_uploader("Raw export files (CSV or Excel)", type=["csv", "xlsx"], accept_multiple_files=True,
                             key="up_files")
    found, rows = {}, []
    for f in files or []:
        try:
            df = pd.read_excel(f) if f.name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(f)
        except Exception as e:  # unreadable file
            rows.append({"Your file": f.name, "Recognised as": "-", "Rows": 0, "Check": f"Could not read: {e}"})
            continue
        fname, missing = detect(df)
        if fname is None:
            rows.append({"Your file": f.name, "Recognised as": "Not recognised", "Rows": len(df),
                         "Check": "Columns don't match any template"})
            continue
        rows.append({"Your file": f.name, "Recognised as": SOURCES[fname]["label"], "Rows": len(df),
                     "Check": "OK" if not missing else "Missing columns: " + ", ".join(missing)})
        if not missing:
            found[fname] = df
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    need = [SOURCES[k]["label"] for k, v in SOURCES.items() if v["required"] and k not in found]
    if files and need:
        st.warning("Still needed: " + ", ".join(need) + ".")
    sems = sorted(found["03_attendance_weekly.csv"]["semester"].astype(str).unique()) \
        if "03_attendance_weekly.csv" in found else C.SEMESTERS
    c = st.columns(3)
    name = c[0].text_input("College name", value=C.COLLEGE_NAME, key="adv_name")
    code = c[1].text_input("College code (first 4 digits of register numbers)", value=C.COLLEGE_CODE)
    domain = c[2].text_input("Official email domain", value=C.EMAIL_DOMAIN)
    c = st.columns(4)
    opts = list(sems)
    pick = lambda col, label, i: col.selectbox(label, opts, index=min(max(i, 0), len(opts) - 1))  # noqa: E731
    s_train = pick(c[0], "Older past semester (to learn from)", len(opts) - 3)
    s_test = pick(c[1], "Last semester (to test on)", len(opts) - 2)
    s_cur = pick(c[2], "Current semester", len(opts) - 1)
    week = c[3].number_input("Current week", min_value=6, max_value=C.WEEKS_PER_SEM, value=int(C.CURRENT_WEEK))
    dep_txt = st.text_area("Departments: short name: [full name, university code, roll-number code, students per batch]",
                           json.dumps({k: list(v) for k, v in C.DEPTS.items()}, indent=1), height=140)
    if st.button("Build from raw exports", disabled=bool(need) or not files):
        if len({s_train, s_test, s_cur}) < 3:
            st.error("Choose three different semesters: one to learn from, one to test on, and the current one.")
            return
        try:
            depts = {k: list(v) for k, v in json.loads(dep_txt).items()}
        except Exception:
            st.error("The departments box is not valid. Keep the same format as the example.")
            return
        apply(found, dict(college_name=name, college_code=code, email_domain=domain,
                          semesters=[s_train, s_test, s_cur], current_week=int(week), depts=depts))
