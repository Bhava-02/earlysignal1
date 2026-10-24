import streamlit as st

from src import config as C
from src import ui

CAMPUS_SVG = """
<svg viewBox="0 0 520 300" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px">
  <g fill="rgba(255,255,255,.10)"><circle cx="70" cy="215" r="46"/><circle cx="455" cy="210" r="52"/>
    <circle cx="30" cy="240" r="30"/><circle cx="495" cy="245" r="30"/></g>
  <g fill="rgba(255,255,255,.92)">
    <rect x="120" y="150" width="280" height="110" rx="4"/>
    <polygon points="110,152 260,92 410,152"/>
    <rect x="236" y="48" width="48" height="52" rx="3"/>
    <path d="M232 52 Q260 18 288 52 Z"/>
    <rect x="257" y="8" width="6" height="26" rx="2"/>
  </g>
  <g fill="#8c1230">
    <rect x="148" y="168" width="20" height="34" rx="3"/><rect x="186" y="168" width="20" height="34" rx="3"/>
    <rect x="314" y="168" width="20" height="34" rx="3"/><rect x="352" y="168" width="20" height="34" rx="3"/>
    <rect x="148" y="214" width="20" height="30" rx="3"/><rect x="186" y="214" width="20" height="30" rx="3"/>
    <rect x="314" y="214" width="20" height="30" rx="3"/><rect x="352" y="214" width="20" height="30" rx="3"/>
    <path d="M240 260 V206 Q260 182 280 206 V260 Z"/>
    <circle cx="260" cy="128" r="12"/><rect x="250" y="62" width="20" height="26" rx="3"/>
  </g>
  <rect x="80" y="260" width="360" height="8" rx="4" fill="rgba(255,255,255,.55)"/>
  <rect x="200" y="268" width="120" height="30" fill="rgba(255,255,255,.18)"/>
</svg>"""


def render():
    st.markdown("""<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header[data-testid="stHeader"] {display: none;}
.block-container {max-width: 1100px; padding-top: 4vh;}
.loginpanel {background: linear-gradient(160deg, #a5183d 0%, #6e0f27 100%); border-radius: 18px; padding: 44px 40px;
             min-height: 560px; display: flex; flex-direction: column; justify-content: space-between;}
.loginpanel h2 {color: #fff !important; font-size: 2rem !important; line-height: 1.25; font-weight: 800 !important; margin: 0;}
.loginpanel p {color: rgba(255,255,255,.82); margin-top: 10px;}
</style>""", unsafe_allow_html=True)
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        with st.container(border=True):
            st.markdown(f"<div style='display:flex;align-items:center;gap:10px;margin:8px 0 26px 0'>"
                        f"<span style='font-size:26px'>🎓</span><div><div style='font-weight:800;font-size:1.25rem;"
                        f"color:{ui.INK}'>{C.APP_NAME}</div><div class='muted'>{C.TAGLINE}</div></div></div>",
                        unsafe_allow_html=True)
            st.markdown(f"<h2 style='margin:0;color:{ui.INK};font-size:1.6rem'>Faculty and admin login</h2>"
                        "<div class='sub'>See which students need help, why, and what to do next.</div>",
                        unsafe_allow_html=True)
            with st.form("login"):
                email = st.text_input("Email", value="admin@college.edu.in")
                pw = st.text_input("Password", type="password", placeholder="Your password")
                ok = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if ok:
                u = C.DEMO_USERS.get(email.strip().lower())
                if u and pw == u[0]:
                    st.session_state["user"] = dict(email=email, name=u[1], role=u[2], dept=u[3])
                    st.rerun()
                else:
                    st.error("That email and password don't match. Use one of the demo sign-ins below.")
            st.markdown("<div class='muted' style='margin:6px 0 4px 0'>Trying the demo? Sign in with one click:</div>",
                        unsafe_allow_html=True)
            a, b = st.columns(2)
            for col, email_ in ((a, "admin@college.edu.in"), (b, "hod.cse@college.edu.in")):
                u = C.DEMO_USERS[email_]
                if col.button(f"{u[2]}", key=f"demo_{email_}", icon=":material/login:", use_container_width=True,
                              help=f"{email_} / {u[0]}"):
                    st.session_state["user"] = dict(email=email_, name=u[1], role=u[2], dept=u[3])
                    st.rerun()
            with st.expander("Demo sign-ins"):
                st.markdown("- **Admin (whole college):** admin@college.edu.in, password `admin123`\n"
                            "- **HOD, CSE (one department):** hod.cse@college.edu.in, password `hod123`")
    with right:
        st.markdown(f"<div class='loginpanel'><div><h2>Better data.<br>Better decisions.<br>Brighter student futures.</h2>"
                    f"<p>Attendance, marks, the LMS and placement training in one place, with a weekly early warning "
                    f"for every student.</p></div>{CAMPUS_SVG}</div>", unsafe_allow_html=True)
