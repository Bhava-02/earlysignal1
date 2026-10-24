import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import ui
from src.integrate import norm_dept, norm_year


@st.cache_data(show_spinner=False)
def identity_example(_S, raw_dir):
    """One real student as they appear in each raw system (sample data only)."""
    S, raw = _S, C.RAW_DIR
    try:
        ex = pd.read_csv(raw / "02_exam_cell_results.csv", dtype={"register_no": str})
        users = pd.read_csv(raw / "04a_lms_users.csv")
        ev = pd.read_csv(raw / "05_student_affairs_events.csv")
        att = pd.read_csv(raw / "03_attendance_weekly.csv")
        pl = pd.read_csv(raw / "06_placement_training_scores.csv", dtype={"candidate_id": str})
    except FileNotFoundError:
        return None
    damaged = ex[ex["register_no"].str.contains("E", na=False)]
    E = pd.read_parquet(C.PROC_DIR / "exam_results.parquet")
    att_norm = att["RollNo"].astype(str).str.strip().str.upper().str.replace(r"^(\d\d[A-Z]{2})0*", r"\1", regex=True)
    ev_norm = ev["participant_name"].str.lower().str.replace(r"[^a-z ]", " ", regex=True).str.split().map(sorted).map(" ".join)
    ev_dept, ev_year = ev["department"].map(norm_dept), ev["year_of_study"].map(norm_year)
    for name in damaged["student_name"].unique()[:200]:
        rolls = E[(E["student_name"] == name) & E["register_no"].astype(str).str.contains("E", na=False)]["roll_no"].unique()
        if len(rolls) != 1 or rolls[0] not in S.index:
            continue
        r = rolls[0]
        s = S.loc[r]
        u = users[users["login_email"].str.lower() == s["email"]]
        e_rows = ev[(ev_norm == " ".join(sorted(s["name"].lower().split()))) & (ev_dept == s["dept"]) & (ev_year == s["year"])]
        a_rows = att[(att_norm == r[:4] + str(int(r[4:]))) & (att["RollNo"] != r)]
        if not len(e_rows) or not len(a_rows) or not len(u):
            continue
        reg = f"{C.COLLEGE_CODE}{r[:2]}{C.DEPTS[s['dept']][1]}{r[4:]}"
        p_rows = pl[pl["candidate_id"].isin([reg, s["email"]])]
        rows = [("Student records (SIS)", r, "Master record"),
                ("Exam cell", damaged[damaged["student_name"] == name]["register_no"].iloc[0],
                 "Number damaged by Excel; matched on name, department and batch"),
                ("Attendance system", a_rows["RollNo"].iloc[0], "Capitals, spaces and zeros fixed"),
                ("Online learning portal", u["login_email"].iloc[0], "Email turned into roll number"),
                ("Events and clubs office", f"{e_rows['participant_name'].iloc[0]} ({e_rows['department'].iloc[0]}, "
                                            f"{e_rows['year_of_study'].iloc[0]})", "Name matched within the same class"),
                ("Placement training", p_rows["candidate_id"].iloc[0] if len(p_rows) else "-", "Register number or email"),
                ("Skills tests", f"{r[:2]}-{r[2:4]}-{r[4:]}", "ID format converted")]
        return r, s["name"], pd.DataFrame(rows, columns=["System", "How this student appears", "How we linked it"])
    return None


def render():
    D = ui.data()
    q = D["meta"]["quality"]
    s = q["summary"]
    ui.title("Data quality", "Student data comes from many systems, each naming students differently. "
                             "This is how it was cleaned and joined into one record per student.")
    cols = st.columns(4)
    for c, k in zip(cols, [("🗂️", "#e6effc", ui.BLUE, "Files joined", s["source_files"], "", "from the college's systems"),
                           ("🧾", "#efe8fc", ui.PURPLE, "Records read", f"{s['rows_in']:,}", "", "attendance, marks, LMS and more"),
                           ("🔗", "#e5f6ec", ui.GREEN, "Matched to a student", f"{s['overall_link_rate']}%", "", "5 matching methods"),
                           ("🔎", "#fff1e3", "#b65a0b", "Manual check needed", q["review_queue_size"], "records", "never guessed")]):
        c.markdown(ui.kpi(*k), unsafe_allow_html=True)
    st.write("")
    ex = identity_example(D["S"], str(C.RAW_DIR)) if D["meta"].get("using_sample", True) else None
    if ex:
        with st.container(border=True):
            r, name, T = ex
            st.markdown(f"### One student, seven different IDs: {name}")
            st.dataframe(T, hide_index=True)
    a, b = st.columns([1.3, 1], gap="medium")
    with a.container(border=True):
        st.markdown("### How well each source matched")
        src = pd.DataFrame(q["sources"])
        src = src[src["rows_in"] > 0]  # leave out sources the college did not upload
        fig = go.Figure(go.Bar(y=src["source"], x=src["link_rate"], orientation="h", marker_color=ui.CRIMSON,
                               text=[f"{v}%" for v in src["link_rate"]], textposition="outside",
                               textfont=dict(color=ui.TEXT), cliponaxis=False,
                               hovertemplate="%{y}: %{x}% matched<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(range=[0, 118], showticklabels=False)
        ui.chart(ui.style(fig, 330, legend=False), key="q_bar")
    with b.container(border=True):
        st.markdown("### Data confidence per student")
        cl = D["S"]["confidence_label"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0).astype(int)
        for lab, n, color in zip(cl.index, cl.values, [ui.GREEN, ui.ORANGE, "#d6304a"]):
            st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.9rem;margin-top:6px'>"
                        f"<span>{lab}</span><b>{n}</b></div>{ui.bar(100 * n / max(cl.sum(), 1), color)}",
                        unsafe_allow_html=True)
        st.caption("Confidence is the share of a student's score backed by real data, not filled-in values. "
                   "Low usually means no survey response, no skills test, or a source the college hasn't uploaded.")
    with st.expander("Cleaning done, source by source"):
        T = pd.DataFrame({"Source": src["source"], "System": src["system"], "Student ID used": src["identifier"],
                          "Rows": src["rows_in"], "Matched %": src["link_rate"],
                          "What was fixed": src["issues"].map(lambda m: "; ".join(f"{k}: {v:,}" for k, v in m.items()))})
        st.dataframe(T, hide_index=True)
    with st.expander(f"Records waiting for a manual check ({q['review_queue_size']})"):
        RQ = pd.DataFrame(q["review_queue"])
        if len(RQ):
            RQ = RQ.rename(columns={"source": "Source", "record": "Record", "reason": "Why"})
            st.dataframe(RQ, hide_index=True, height=300)
            st.download_button("Download the list", RQ.to_csv(index=False).encode(), "manual_check.csv")
        else:
            st.success("Nothing waiting.")
