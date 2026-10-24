import streamlit as st

from src import config as C
from src import ui

STATUS = {"All": None, "At risk (high)": ["High"], "Moderate": ["Medium"], "Low risk": ["Low"]}
QUICK = {"Everyone": None, "New this week": "new", "Attendance shortage": "short", "Hidden strugglers": "hidden"}


def render():
    D = ui.data()
    S = ui.scoped(D["S"])
    ui.title("Student directory", "Search and filter every student. Open anyone to see their full profile.")

    with st.container(border=True):
        with st.form("dir_filters", border=False):
            c = st.columns([2.4, 1, 1, 1.1, 0.8], vertical_alignment="bottom")
            q = c[0].text_input("Search", value=st.session_state.get("dir_q", ""),
                                placeholder="Search by name, roll number or department")
            depts = ["All"] + sorted(S["dept"].unique())
            dept = c[1].selectbox("Department", depts, index=depts.index(st.session_state.get("dir_dept", "All"))
                                  if st.session_state.get("dir_dept", "All") in depts else 0)
            years = ["All"] + [str(int(y)) for y in sorted(S["year"].dropna().unique())]
            year = c[2].selectbox("Year", years, index=years.index(st.session_state.get("dir_year", "All"))
                                  if st.session_state.get("dir_year", "All") in years else 0)
            stat = c[3].selectbox("Risk status", list(STATUS), index=list(STATUS).index(st.session_state.get("dir_risk", "All")))
            go_ = c[4].form_submit_button("Search", type="primary", use_container_width=True, icon=":material/search:")
        if go_:
            st.session_state.update(dir_q=q, dir_dept=dept, dir_year=year, dir_risk=stat, pg_dir=1)
        quick = st.radio("Quick view", list(QUICK), horizontal=True, key="dir_quick", label_visibility="collapsed")

    L = S
    q, dept = st.session_state.get("dir_q", ""), st.session_state.get("dir_dept", "All")
    year, stat = st.session_state.get("dir_year", "All"), st.session_state.get("dir_risk", "All")
    if q:
        ql = q.lower()
        L = L[L["name"].str.lower().str.contains(ql, regex=False) | L.index.str.lower().str.contains(ql, regex=False)
              | L["dept"].str.lower().eq(ql)]
    if dept != "All":
        L = L[L["dept"] == dept]
    if year != "All":
        L = L[L["year"] == int(year)]
    if STATUS[stat]:
        L = L[L["acad_risk"].isin(STATUS[stat])]
    k = QUICK[quick]
    if k == "new":
        L = L[L["newly_flagged"]]
    elif k == "short":
        L = L[L["attendance_shortage"]]
    elif k == "hidden":
        L = L[L["segment"] == "Silent Strugglers"]
    L = L.sort_values("acad_prob", ascending=False)

    st.write("")
    with st.container(border=True):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown(f"**{len(L):,} students** <span class='muted'>sorted by risk, highest first</span>", unsafe_allow_html=True)
        if len(L):
            b.download_button("Download list", L.drop(columns=["acad_reasons", "placement_reasons", "risk_trend"]).to_csv()
                              .encode(), f"students_week{C.CURRENT_WEEK}.csv", icon=":material/download:",
                              use_container_width=True)
        ui.student_list(L, "dir", [
            ("Name", 2.3, ui.col_name), ("Department", 1.0, lambda r, x: x["dept"]),
            ("Year", 0.6, lambda r, x: str(x["year"])), ("CGPA", 0.7, lambda r, x: f"{x['cgpa']:.1f}"),
            ("Success Score", 1.0, ui.col_score), ("Risk status", 1.0, ui.col_risk),
            ("Main reason", 2.4, ui.col_reason)], page_size=12)
