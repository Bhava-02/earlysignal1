"""
EarlySignal: spots students who need help, weeks before their marks drop.
Run:  streamlit run app.py
"""
import streamlit as st

from src import ai, ui
from src import config as C
from views import (analytics, assistant, dashboard, fairness, interventions, login, method, placement, profile,
                   quality, segments, students, upload)

st.set_page_config(page_title=C.APP_NAME, page_icon="🎓", layout="wide", initial_sidebar_state="expanded")
ui.inject_css()


def hidden_nav(pages):
    try:
        return st.navigation(pages, position="hidden")
    except TypeError:  # older Streamlit
        return st.navigation(pages)


# ---------------------------------------------------------------- sign in
if not st.session_state.get("user"):
    # Every page address (e.g. a shared /students link) shows the sign-in page instead of "Page not found";
    # after signing in, the visitor lands on the page the link pointed to.
    gate = [st.Page(login.render, title="Sign in", icon="🎓", default=True)]
    gate += [st.Page(login.render, title="Sign in", icon="🎓", url_path=path)
             for path in [k for k, *_ in ui.NAV] + ["student"]]
    hidden_nav(gate).run()
    st.stop()

# ---------------------------------------------------------------- pages
RENDER = {"dashboard": dashboard.render, "students": students.render, "analytics": analytics.render,
          "segments": segments.render, "placement": placement.render, "interventions": interventions.render,
          "assistant": assistant.render, "upload": upload.render, "quality": quality.render,
          "fairness": fairness.render, "method": method.render}
PAGES = {}
for key, label, icon, _ in ui.NAV:
    PAGES[key] = st.Page(RENDER[key], title=label, icon=f":material/{icon}:", url_path=key,
                         default=(key == "dashboard"))
PAGES["profile"] = st.Page(profile.render, title="Student profile", icon=":material/person:", url_path="student")
ui.PAGES.update(PAGES)
nav = hidden_nav(list(PAGES.values()))
current = next((k for k, p in PAGES.items() if p is nav or p.url_path == getattr(nav, "url_path", None)), "dashboard")
if current == "profile":
    current = "students"  # keep "Students" highlighted while viewing a profile

# ---------------------------------------------------------------- sidebar menu
u = ui.user()
with st.sidebar:
    st.markdown(f"<div class='brand'><span style='font-size:28px'>🎓</span><div><div class='name'>{C.APP_NAME}</div>"
                f"<div class='tag'>{C.TAGLINE}</div></div></div>", unsafe_allow_html=True)
    group = None
    for key, label, icon, grp in ui.NAV:
        if grp != group:
            group = grp
            if grp:
                st.markdown(f"<div class='navgroup'>{grp}</div>", unsafe_allow_html=True)
        with st.container(key=f"nav_{key}"):
            st.page_link(PAGES[key], label=label, icon=f":material/{icon}:")
    st.markdown(f"""<style>.st-key-nav_{current} a[data-testid="stPageLink-NavLink"] {{background: rgba(255,255,255,.18);}}
.st-key-nav_{current} a[data-testid="stPageLink-NavLink"] p {{font-weight: 700 !important; color: #fff !important;}}</style>""",
                unsafe_allow_html=True)
    st.divider()
    st.markdown(f"<div class='usercard'><b>{u.get('name')}</b><br><span style='opacity:.75'>{u.get('role')}</span></div>",
                unsafe_allow_html=True)
    with st.expander("AI assistant key (optional)"):
        st.text_input("Gemini API key", type="password", key="gemini_key",
                      help="Free key from aistudio.google.com. Kept only for this browser session.")
        st.text_input("Model", value=ai.DEFAULT_MODEL, key="gemini_model")
        st.caption("Only anonymised numbers are sent. Names and roll numbers never leave this app.")

# ---------------------------------------------------------------- first visit on a fresh deployment
if not (C.PROC_DIR / "meta.json").exists():
    with st.spinner("Setting up the dashboard for the first time: cleaning, matching and scoring 1,080 students "
                    "(about 30 seconds)..."):
        ui.data()

# ---------------------------------------------------------------- top bar
D_ = ui.data()
S_ = ui.scoped(D_["S"])
n_new = int(S_["newly_flagged"].sum())
college = D_["meta"].get("college_name") or C.COLLEGE_NAME
sem = "" if C.CURRENT_SEM == "This semester" else f"{C.CURRENT_SEM} · "
done = 100 * C.CURRENT_WEEK / C.WEEKS_PER_SEM
src_ = ui.data_source() if not D_["meta"].get("using_sample", True) else {}
live = (f"<span class='tb-live' title='Read from the college server'>● Live, synced {src_.get('synced_at', '')}</span>"
        if src_.get("type") == "server" else "")
with st.container(key="topbar"):
    t1, t2, t3, t4, t5 = st.columns([2.6, 2.2, 1.25, 1.6, 0.6], vertical_alignment="center", gap="small")
    t1.markdown(f"""<div class='tb-ctx'><div class='tb-ic'>{ui.ICON_SCHOOL}</div><div style='min-width:0'>
<div class='tb-college' title='{college}'>{college}</div>
<div class='tb-sub'>{sem}Week {C.CURRENT_WEEK} of {C.WEEKS_PER_SEM}<span class='tb-week'><span style='width:{done:.0f}%'></span></span>{live}</div>
</div></div>""", unsafe_allow_html=True)
    q = t2.text_input("Search", placeholder="Search students", label_visibility="collapsed",
                      key="top_search")
    if t3.button(f"{n_new} new" if n_new else "All clear", key="tb_alerts",
                 icon=":material/notifications_active:" if n_new else ":material/notifications:",
                 help=f"{n_new} student(s) moved into high risk this week. Click to see them.", use_container_width=True):
        st.session_state.update(dir_q="", dir_dept="All", dir_year="All", dir_risk="All", pg_dir=1,
                                dir_quick="New this week")
        st.switch_page(PAGES["students"])
    t4.markdown(f"<div class='tb-user'>{ui.avatar(u.get('name', 'U'), 36)}<div style='min-width:0'>"
                f"<div class='n'>{u.get('name')}</div><div class='r'>{u.get('role', '')}</div></div></div>",
                unsafe_allow_html=True)
    if t5.button("Sign out", key="logout", icon=":material/logout:", type="tertiary", help="Sign out",
                 use_container_width=True):
        st.session_state.clear()
        st.rerun()
if q and q != st.session_state.get("top_search_done"):
    st.session_state["top_search_done"] = q
    st.session_state.update(dir_q=q, dir_dept="All", dir_year="All", dir_risk="All", pg_dir=1, dir_quick="Everyone")
    st.switch_page(PAGES["students"])

if not D_["meta"].get("using_sample", True) and current != "upload":
    b1, b2 = st.columns([4, 1.3], vertical_alignment="center")
    b1.markdown(f"<div class='muted'>ⓘ Showing <b>{college}</b> data loaded on the Data sources page. Everyone using "
                f"this link sees the same data.</div>", unsafe_allow_html=True)
    b2.page_link(PAGES["upload"], label="Back to the sample college", icon=":material/undo:")
nav.run()
src_note = "Prototype on realistic sample data." if D_["meta"].get("using_sample", True) else \
    f"Data: {C.COLLEGE_NAME}, {'' if C.CURRENT_SEM == 'This semester' else C.CURRENT_SEM + ', '}week {C.CURRENT_WEEK}."
st.markdown(f"<br><div class='muted'>{src_note} Scores support conversations with students; "
            "they never decide anything on their own.</div>", unsafe_allow_html=True)
