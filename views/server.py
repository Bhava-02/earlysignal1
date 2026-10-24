"""Data sources > College server: connect read-only to the college ERP and Moodle databases and sync."""
import json
import os
import re
import subprocess
import sys

import pandas as pd
import streamlit as st

from src import config as C
from src import connector as cn
from src import demo_server
from src import ui


def server_form(prefix, saved, label):
    """Connection fields for one server. Returns the config dict and the password typed this session."""
    names = list(cn.DIALECTS)
    dialect = st.selectbox("Database type", names, key=f"{prefix}_dialect",
                           index=names.index(saved.get("dialect", "MySQL / MariaDB"))
                           if saved.get("dialect") in names else 0)
    if dialect == "SQLite file":
        path = st.text_input("Database file", value=saved.get("database", ""), key=f"{prefix}_file")
        return dict(dialect=dialect, database=path), ""
    c = st.columns([2, 1])
    host = c[0].text_input("Server address", value=saved.get("host", ""), key=f"{prefix}_host",
                           placeholder="e.g. 10.0.4.12 or erp.college.edu.in")
    port = c[1].number_input("Port", value=int(saved.get("port") or cn.DIALECTS[dialect][1]), step=1,
                             key=f"{prefix}_port")
    db = st.text_input("Database name", value=saved.get("database", ""), key=f"{prefix}_db",
                       placeholder="e.g. college_erp" if prefix == "erp" else "e.g. moodle")
    c = st.columns(2)
    user = c[0].text_input("Read-only username", value=saved.get("username", ""), key=f"{prefix}_user")
    pw = c[1].text_input("Password", type="password", key=f"{prefix}_pw",
                         help="Used for this session only. EarlySignal never saves passwords.")
    return dict(dialect=dialect, host=host.strip(), port=int(port), database=db.strip(), username=user.strip()), pw


def render(meta):
    conn = cn.load_conn()
    st.markdown("""<div class='flow'>
<div><div class='h'><span>1</span>Connect read-only</div><div class='d'>The college's IT team creates a <b>read-only
login</b> on the ERP database (and on Moodle, if used). EarlySignal can look, never change.</div></div>
<div><div class='h'><span>2</span>Map once</div><div class='d'>A few <b>SELECT queries</b> tell EarlySignal where
students, marks and attendance live. Defaults fit common ERPs; IT adjusts table names once.</div></div>
<div><div class='h'><span>3</span>Sync every night</div><div class='d'>New attendance, marks and LMS activity flow in
<b>automatically</b> and every page rebuilds. No more spreadsheets.</div></div></div>""", unsafe_allow_html=True)

    # 1. connect ------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 1. Connect")
        modes = ["Demo college server", "My college's server"]
        mode = st.radio("Server", modes, horizontal=True, key="srv_mode", label_visibility="collapsed",
                        index=1 if conn.get("mode") == "server" else 0)
        passwords = {}
        if mode == modes[0]:
            st.markdown("<div class='muted'>A demo college ERP and a Moodle LMS, laid out the way colleges really "
                        "store data: attendance is one row per student per class hour, Moodle uses its own table "
                        "names. Built from the sample college, so you can try every step.</div>",
                        unsafe_allow_html=True)
            if not demo_server.exists():
                if st.button("Start the demo server", icon=":material/dns:", type="primary"):
                    rc, _ = run_job([sys.executable, "-m", "src.demo_server"],
                                    "Creating the demo ERP and Moodle databases (about 15 seconds)...")
                    if rc == 0 and demo_server.exists():
                        demo_server_tables.clear()
                        st.rerun()
                cfgs = {}
            else:
                cfgs = cn.demo_cfgs()
                T = demo_server_tables()
                c = st.columns(3)
                c[0].markdown(ui.kpi("🗄️", "#e6effc", ui.BLUE, "ERP database", f"{(T['Database'] == 'ERP').sum()}",
                                     " tables", "students, marks, attendance"), unsafe_allow_html=True)
                att = int(T.loc[T["Table"] == "attendance", "Rows"].sum())
                c[1].markdown(ui.kpi("🕘", "#efe8fc", ui.PURPLE, "Attendance rows", f"{att:,}", "",
                                     "one per student per class hour"), unsafe_allow_html=True)
                c[2].markdown(ui.kpi("💻", "#e5f6ec", ui.GREEN, "Moodle database", f"{(T['Database'] == 'Moodle').sum()}",
                                     " tables", "logins and assignments"), unsafe_allow_html=True)
                look_inside(cfgs, {}, [("erp" if r.Database == "ERP" else "lms", r.Table, r.Rows)
                                       for r in T.itertuples()])
        else:
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown("**College ERP database** (needed)")
                erp, pw_erp = server_form("erp", conn.get("erp", {}), "ERP")
            with b:
                use_lms = st.toggle("We use Moodle (optional)", value=bool(conn.get("lms")), key="use_lms")
                lms, pw_lms = server_form("lms", conn.get("lms", {}), "Moodle") if use_lms else (None, "")
            passwords = {"erp": pw_erp or os.environ.get("EARLYSIGNAL_ERP_PASSWORD", ""),
                         "lms": pw_lms or os.environ.get("EARLYSIGNAL_LMS_PASSWORD", "")}
            cfgs = {"erp": erp} | ({"lms": lms} if lms else {})
            if st.button("Test connection", icon=":material/lan:"):
                for k, cfg in cfgs.items():
                    ok, msg, tables = cn.test(cfg, passwords.get(k, ""))
                    (st.success if ok else st.error)(f"{'ERP' if k == 'erp' else 'Moodle'}: {msg}")
                    if ok:
                        st.session_state.setdefault("srv_tables", {})[k] = tables
                cn.save_conn(dict(conn, mode="server", erp=erp, lms=lms))
            found = st.session_state.get("srv_tables", {})
            if found:
                look_inside(cfgs, passwords, [(k, t, None) for k in ("erp", "lms") if k in cfgs
                                              for t in found.get(k, [])])
            st.caption("EarlySignal must be able to reach the server: run it inside the campus network or over the "
                       "college VPN. Ask IT for a login that can only SELECT. Supported: MySQL / MariaDB, "
                       "PostgreSQL, SQL Server, Oracle.")

    # 2. map ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 2. Map your tables")
        st.markdown("<div class='muted'>EarlySignal reads with these SELECT queries. They match the demo server and a "
                    "typical ERP; for a real college the IT team changes table and column names once. Anything that "
                    "is not a single SELECT is refused.</div>", unsafe_allow_html=True)
        queries = dict(conn.get("queries") or {})
        last = st.session_state.get("srv_report", {})
        rows = []
        for slot, (server, sheet, need, label, _) in cn.SLOTS.items():
            r = last.get(slot)
            rows.append({"What it reads": label, "From": "ERP" if server == "erp" else "Moodle",
                         "Needed?": "Needed" if need else "Optional",
                         "Query": "Edited" if slot in queries else "Default",
                         "Last run": "-" if r is None else (f"Error: {r['error'][:60]}" if r["error"]
                                                            else f"{r['rows']:,} rows in {r['secs']} s")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=300)
        slots = list(cn.SLOTS)
        pick = st.selectbox("See or edit a query", slots, format_func=lambda s: cn.SLOTS[s][3], key="srv_pick")
        sql = st.text_area("SQL", value=queries.get(pick, cn.DEFAULT_SQL[pick]), height=190, key=f"sql_{pick}",
                           label_visibility="collapsed")
        c = st.columns([1, 1, 1.2, 1.8])
        if c[0].button("Save query", icon=":material/save:", use_container_width=True):
            try:
                cn.check_sql(sql)
                if sql.strip() == cn.DEFAULT_SQL[pick]:
                    queries.pop(pick, None)
                else:
                    queries[pick] = sql.strip()
                cn.save_conn(dict(conn, queries=queries))
                st.success("Saved.")
            except ValueError as e:
                st.error(str(e))
        run_it = c[2].button("Run on the server", icon=":material/play_arrow:",
                             disabled=not cfgs.get(cn.SLOTS[pick][0]))
        if c[1].button("Reset to default", use_container_width=True, disabled=pick not in queries):
            queries.pop(pick, None)
            cn.save_conn(dict(conn, queries=queries))
            st.session_state.pop(f"sql_{pick}", None)
            st.rerun()
        if run_it:
            server = cn.SLOTS[pick][0]
            df, secs, err = cn.preview(cfgs[server], passwords.get(server, ""), sql)
            if err:
                st.error(err)
            else:
                st.caption(f"First {len(df)} rows, straight from the {'ERP' if server == 'erp' else 'Moodle'} "
                           f"database ({secs} s, read-only).")
                st.dataframe(df, hide_index=True)

    # 3. sync ---------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 3. Sync and build")
        demo = mode == modes[0]
        c = st.columns([1.6, 1.3, 1.2], vertical_alignment="bottom")
        name = c[0].text_input("College name", key="srv_name",
                               value=conn.get("college_name") or ("Demo College" if demo else ""))
        go = c[1].button("Sync now and build", type="primary", icon=":material/sync:", use_container_width=True,
                         disabled=not cfgs or not (cfgs.get("erp") or {}).get("database"))
        reset = c[2].button("Switch back to the sample college", use_container_width=True,
                            disabled=meta.get("using_sample", True), key="reset_srv")
        st.caption("Reads the latest data, checks it, and rebuilds every page in about a minute. If anything fails, "
                   "the dashboard keeps the previous data.")
        if go:
            from views.upload import finish, show_checks
            cn.save_conn(dict(conn, mode="demo" if demo else "server", college_name=name.strip() or "My College",
                              **({} if demo else {"erp": cfgs.get("erp"), "lms": cfgs.get("lms")})))
            out_json = C.ROOT / "data" / "last_sync.json"
            out_json.unlink(missing_ok=True)
            env = {"EARLYSIGNAL_ERP_PASSWORD": passwords.get("erp", ""),
                   "EARLYSIGNAL_LMS_PASSWORD": passwords.get("lms", "")}
            rc, _ = run_job([sys.executable, "-m", "src.sync", "--json", str(out_json)] + (["--demo"] if demo else []),
                            "Syncing from the college server (read-only)...", env)
            try:
                out = json.loads(out_json.read_text())
            except Exception:
                out = None
            if out is None:
                st.error("The sync stopped before it finished. " + KILLED_HINT if rc and rc < 0 else
                         "The sync stopped before it finished. The dashboard still shows the previous data.")
            else:
                st.session_state["srv_report"] = {r["slot"]: r for r in out["report"]}
                R = pd.DataFrame([{"What it reads": r["label"], "Rows": "-" if r["rows"] is None else f"{r['rows']:,}",
                                   "Seconds": r["secs"], "Problem": r["error"] or ""} for r in out["report"]])
                st.dataframe(R, hide_index=True, height=260)
                for n in out["notes"]:
                    st.caption(n)
                for e in out["errors"]:
                    st.error(e)
                if out["checks"]:
                    show_checks(out)
                if out.get("built"):
                    sim = demo_server.load_sim() if demo else None
                    if sim:
                        demo_server.save_sim(dict(sim, synced=True))
                    finish()
                    st.success("Done. Every page now uses the data from the college server.")
                    st.page_link(ui.PAGES["dashboard"], label="Open the dashboard", icon=":material/dashboard:")
                elif out["ok"]:
                    st.error("The data was read and checked, but the rebuild did not finish, so the previous data is "
                             "kept. " + (KILLED_HINT if rc and rc < 0 else ""))
                    if out.get("log"):
                        st.code(out["log"])
                elif out["checks"]:
                    st.error("The data was read, but some checks failed (marked ❌). Adjust the queries in step 2.")
        if reset:
            from views.upload import reset_to_sample
            reset_to_sample()

    if mode == modes[0] and demo_server.exists():
        prove_live()

    with st.expander("Automatic nightly sync"):
        st.markdown("Run EarlySignal on a computer **inside the campus network** (or connected over the college VPN), "
                    "connect once on this page, then add one line to the scheduler. Every night it reads the new "
                    "attendance, marks and Moodle activity and rebuilds every page. If the server is down, the "
                    "previous day's data stays.")
        st.markdown("**Linux (cron):**")
        st.code(f"0 2 * * *  cd {C.ROOT} && EARLYSIGNAL_ERP_PASSWORD='...' EARLYSIGNAL_LMS_PASSWORD='...' "
                "python -m src.sync >> sync.log 2>&1", language="bash")
        st.markdown("**Windows (Task Scheduler):** run `python -m src.sync` in this folder every night, with the "
                    "two passwords set as environment variables. To try it on the demo server: `python -m src.sync --demo`.")
    with st.expander("How colleges store this data, and how EarlySignal reaches it"):
        st.markdown("""
| Data | Where it usually lives | How EarlySignal reads it |
|---|---|---|
| Students, attendance, internal marks, results | College ERP database (MySQL, PostgreSQL, SQL Server or Oracle) on a campus server or the vendor's cloud | Read-only SQL login (or the vendor's report API) |
| Online activity, assignments | Moodle database (MySQL or PostgreSQL) | Read-only SQL login on Moodle's own tables |
| University exam results | Excel / PDF from the university portal, often imported into the ERP | From the ERP once imported, or the Excel upload |
| Placement training, events, feedback | Excel sheets and Google Forms kept by each office | The Excel upload tab, until they move into the ERP |

**What the college needs to provide:** a read-only database login, network access from the EarlySignal machine
(same campus network or VPN), and approval under its data policy. Under India's Digital Personal Data Protection
Act, 2023 the college stays responsible for its students' data, so EarlySignal reads only the columns it needs,
never writes, never stores passwords, and keeps the data on the college's own machine.

**If the ERP is a vendor's cloud product** without database access, use the vendor's scheduled report export
(saved nightly to a shared folder) with the Excel tab, or ask the vendor for an API.
""")


def look_inside(cfgs, passwords, tables):
    """tables: [(server, table, rows or None)]. Shows raw rows of any table, read live from the server."""
    with st.expander("Look inside the server: raw tables, read live"):
        st.caption("This is the data exactly as the college systems keep it. Pick a table to read its first rows "
                   "straight from the database (read-only).")
        if tables and tables[0][2] is not None:
            st.dataframe(pd.DataFrame([{"Database": "ERP" if k == "erp" else "Moodle", "Table": t, "Rows": n}
                                       for k, t, n in tables]), hide_index=True, height=240)
        opts = [f"{'ERP' if k == 'erp' else 'Moodle'} · {t}" for k, t, _ in tables]
        if not opts:
            return
        c = st.columns([2, 1], vertical_alignment="bottom")
        pick = c[0].selectbox("Table", opts, key="peek_table",
                              index=opts.index("ERP · attendance") if "ERP · attendance" in opts else 0)
        if c[1].button("Show the first rows", icon=":material/table_rows:", use_container_width=True):
            k, t = tables[opts.index(pick)][:2]
            if not re.fullmatch(r"[A-Za-z0-9_$.]+", t):
                st.error("Unusual table name; open it with a query in step 2 instead.")
                return
            df, secs, err = cn.preview(cfgs[k], passwords.get(k, ""), f"SELECT * FROM {t}")
            if err:
                st.error(err)
            else:
                st.caption(f"`SELECT * FROM {t}`: first {len(df)} rows in {secs} s.")
                st.dataframe(df, hide_index=True)


@st.cache_data(show_spinner=False)
def demo_rolls():
    return demo_server.rolls()


def _snap(r):
    reasons = list(r["acad_reasons"]) if isinstance(r["acad_reasons"], (list, tuple)) else []
    return dict(att=float(r["att_pct"]), lms=float(r["lms_avg"]), asg=100 * float(r["asg_rate"]),
                proj=float(r["projected_attendance"]), risk=r["acad_risk"], score=float(r["success_score"]),
                segment=r["segment"], reason=reasons[0] if reasons else "No warning signs")


def prove_live():
    """Change something on the demo server, sync, and watch the dashboard react."""
    with st.container(border=True):
        st.markdown("### Prove it's live: change the server, then sync")
        st.markdown("<div class='muted'>Play the college's own systems for a moment. Pick a student who is doing "
                    "well and record on the server that, from week 7, they stopped coming to class, logging in to "
                    "Moodle and submitting work. The dashboard does not change until EarlySignal syncs. "
                    "(EarlySignal itself never writes: this button acts as the college's attendance system and "
                    "Moodle.)</div>", unsafe_allow_html=True)
        S = ui.data()["S"]
        sim = demo_server.load_sim()
        on_server = S.index.isin(list(demo_rolls()))
        cand = S[on_server & (S["acad_risk"] == "Low") & (S["att_pct"] >= 88)].sort_values("success_score",
                                                                                            ascending=False)
        if not len(cand) and not sim:
            st.info("Sync from the demo server first (step 3), then come back here.")
            return
        if not sim:
            cand = cand.head(15)
            pick = st.selectbox("Student", list(cand.index), key="sim_pick", format_func=lambda r: (
                f"{cand.at[r, 'name']} ({r}, {cand.at[r, 'dept']} year {cand.at[r, 'year']}): score "
                f"{cand.at[r, 'success_score']:.0f}, attendance {cand.at[r, 'att_pct']:.0f}%"))
            if st.button("Record it on the college server", icon=":material/edit_note:", type="primary"):
                ch = demo_server.simulate_dropout(pick)
                demo_server_tables.clear()
                demo_server.save_sim(dict(roll=pick, name=S.at[pick, "name"], before=_snap(S.loc[pick]),
                                          change=dict(ch, from_date=f"{ch['from_date']:%d %b}"), synced=False))
                st.rerun()
            return
        ch = sim["change"]
        st.success(f"The server now says {sim['name']} ({sim['roll']}) was absent for {ch['attendance']} class hours "
                   f"since {ch['from_date']}, with {ch['logins']} Moodle log-ins and {ch['submissions']} "
                   "assignment submissions removed.")
        if not sim.get("synced"):
            st.markdown("**Now press \"Sync now and build\" in step 3.** EarlySignal will read the changed records "
                        "from the server and every page will update.")
        else:
            now = _snap(S.loc[sim["roll"]]) if sim["roll"] in S.index else None
            if now:
                b = sim["before"]
                rows = [("Attendance this semester", f"{b['att']:.0f}%", f"{now['att']:.0f}%"),
                        ("Moodle log-ins per week", f"{b['lms']:.1f}", f"{now['lms']:.1f}"),
                        ("Assignments submitted", f"{b['asg']:.0f}%", f"{now['asg']:.0f}%"),
                        ("Attendance by semester end (75% needed)",
                         f"{b['proj']:.0f}%" if "proj" in b else "-", f"{now['proj']:.0f}%"),
                        ("Risk level", ui.RISK_WORD.get(b["risk"], b["risk"]), ui.RISK_WORD.get(now["risk"], now["risk"])),
                        ("Main reason shown to the mentor", b.get("reason", "-"), now["reason"]),
                        ("Success Score", f"{b['score']:.0f}", f"{now['score']:.0f}"),
                        ("Group", b["segment"], now["segment"])]
                st.markdown(f"**What EarlySignal shows for {sim['name']} after reading the server:**")
                st.dataframe(pd.DataFrame(rows, columns=["", "Before", "After sync"]), hide_index=True)
                if st.button(f"Open {sim['name']}'s profile", icon=":material/person:"):
                    ui.open_student(sim["roll"])
        if st.button("Undo: rebuild the demo server", icon=":material/restart_alt:"):
            rc, _ = run_job([sys.executable, "-m", "src.demo_server"], "Rebuilding the demo server...")
            demo_server.save_sim(None)
            demo_server_tables.clear()
            demo_rolls.clear()
            if rc == 0:
                st.success("Demo server restored. Sync again to bring the dashboard back too.")


KILLED_HINT = ("The system stopped it, most likely because the workspace ran out of memory. Close other apps or "
               "browser tabs in the workspace and try again.")


def run_job(cmd, label, env=None):
    """Run a heavy job in its own process (so the app itself stays light) and show its progress live."""
    full_env = dict(os.environ, PYTHONUNBUFFERED="1", **(env or {}))
    lines = []
    with st.status(label, expanded=True) as box:
        proc = subprocess.Popen(cmd, cwd=str(C.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=full_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line and not line.startswith(("Traceback", "  File", "    ")):
                lines.append(line)
                box.write(line)
        rc = proc.wait()
        if rc == 0:
            box.update(label=label.replace("...", ": done"), state="complete", expanded=False)
        else:
            box.update(label=label.replace("...", ": stopped"), state="error", expanded=True)
            if rc < 0:
                st.error(KILLED_HINT)
    return rc, lines


@st.cache_data(show_spinner=False)
def demo_server_tables():
    t = demo_server.tables()
    return pd.DataFrame([{"Database": db, "Table": tb, "Rows": n} for (db, tb), n in t.items()])
