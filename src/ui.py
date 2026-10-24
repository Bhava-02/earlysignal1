"""Shared look, data loading and building blocks used by every page."""
import hashlib
import json
import os
import pickle
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import config as C

# ---------------------------------------------------------------- design tokens
CRIMSON = "#b3163a"       # primary actions, active states
CRIMSON_DARK = "#8c1230"
TINT = "#fdeef1"          # light crimson wash
INK = "#1d2433"           # headings, numbers
TEXT = "#4a5263"          # body text
MUTED = "#8a90a0"         # captions, axes
LINE = "#eceef3"          # borders, gridlines
BG = "#f6f7fb"            # page background
BLUE = "#2a78d6"
GREEN = "#1a9e5c"
ORANGE = "#e8833a"
PURPLE = "#7c4ddb"
GREY = "#b9bdc7"
SERIES = {"Overall": CRIMSON, "Academic": BLUE, "Engagement": GREEN}
ICON_SCHOOL = ("<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='#b3163a' stroke-width='2' "
               "stroke-linecap='round' stroke-linejoin='round'><path d='M2 10l10-6 10 6-10 6z'/><path d='M6 12v5c3 2 9 2 12 0v-5'/>"
               "<path d='M22 10v6'/></svg>")
DEPT_COLORS = {"CSE": "#2a78d6", "IT": "#eb6834", "ECE": "#1baf7a", "MECH": "#eda100"}
EXTRA_COLORS = ["#7c4dcc", "#d6304a", "#0f8a8a", "#8a6d1f", "#5b6475", "#c2468f", "#3f7d20", "#1d5fb3"]


def dept_color(dept, i=0):
    """Fixed colours for the sample departments; any other department gets a colour by its position."""
    if dept in DEPT_COLORS:
        return DEPT_COLORS[dept]
    return list(DEPT_COLORS.values())[i % 4] if i < 4 else EXTRA_COLORS[(i - 4) % len(EXTRA_COLORS)]
RISK = {"High": "#d03b3b", "Medium": ORANGE, "Low": GREEN, "Pre-placement": MUTED}
RISK_WORD = {"High": "At Risk", "Medium": "Moderate", "Low": "Low Risk", "Pre-placement": "Pre-placement"}
FONT = "'Source Sans Pro', 'Source Sans 3', system-ui, -apple-system, 'Segoe UI', sans-serif"
AVATAR_BG = ["#fde2e7", "#e0ecfd", "#ddf3e8", "#fdecd8", "#ece4fb", "#fbe3f1", "#e2f2f7"]
AVATAR_FG = ["#a3133a", "#1d5fb3", "#167a48", "#b25a0e", "#5b36b8", "#a3266f", "#1f6e85"]

PAGES = {}  # filled in app.py: key -> st.Page

NAV = [  # (key, label, material icon, group)
    ("dashboard", "Dashboard", "dashboard", None),
    ("students", "Students", "group", None),
    ("analytics", "Analytics", "insights", None),
    ("segments", "Segments", "category", None),
    ("placement", "Placement", "work", None),
    ("interventions", "Interventions", "assignment_turned_in", None),
    ("assistant", "AI assistant", "forum", "Tools"),
    ("upload", "Data sources", "cloud_sync", "Tools"),
    ("quality", "Data quality", "database", "About the data"),
    ("fairness", "Fairness", "balance", "About the data"),
    ("method", "How it works", "help", "About the data"),
]


def inject_css():
    st.markdown(f"""
<style>
.stApp {{background: {BG};}}
header[data-testid="stHeader"] {{background: transparent;}}
.block-container {{max-width: 1240px; padding-top: 1.2rem; padding-bottom: 3rem;}}
h1 {{font-weight: 800 !important; color: {INK}; letter-spacing: -0.02em; font-size: 1.65rem !important; margin-bottom: 0 !important;}}
h2, h3, h4 {{font-weight: 700 !important; color: {INK}; letter-spacing: -0.01em;}}
h3 {{font-size: 1.05rem !important;}}
p, li {{color: {TEXT};}}
.sub {{color: {MUTED}; font-size: .92rem; margin: .1rem 0 1.1rem 0;}}
.muted {{color: {MUTED}; font-size: .86rem;}}

/* sidebar */
section[data-testid="stSidebar"] {{background: linear-gradient(180deg, #951838 0%, #6e0f27 100%);}}
section[data-testid="stSidebar"] * {{color: #fff;}}
section[data-testid="stSidebar"] hr {{border-color: rgba(255,255,255,.18);}}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {{border-radius: 10px; padding: .45rem .7rem; margin: 1px 0;}}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {{background: rgba(255,255,255,.10);}}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {{font-size: .95rem; font-weight: 500; color: rgba(255,255,255,.92) !important;}}
section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] * {{color: #fff;}}
.navgroup {{font-size: .78rem; color: rgba(255,255,255,.62) !important; margin: .9rem 0 .2rem .7rem;}}
.brand {{display: flex; align-items: center; gap: 10px; padding: .2rem .4rem 1rem .4rem;}}
.brand .name {{font-weight: 800; font-size: 1.2rem; letter-spacing: -0.01em;}}
.brand .tag {{font-size: .74rem; color: rgba(255,255,255,.7) !important;}}
.usercard {{background: rgba(255,255,255,.10); border-radius: 12px; padding: 10px 12px; font-size: .86rem;}}

/* cards: every bordered container */
div[data-testid="stVerticalBlockBorderWrapper"] {{background: #fff; border: 1px solid {LINE} !important; border-radius: 14px;
    box-shadow: 0 1px 2px rgba(16,24,40,.04);}}
.kpi {{display: flex; gap: 14px; align-items: flex-start; background: #fff; border: 1px solid {LINE}; border-radius: 14px;
       padding: 16px 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04); min-height: 118px;}}
.kpi .ic {{width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
          font-size: 22px; flex: none;}}
.kpi .l {{font-size: .84rem; color: {MUTED}; font-weight: 500;}}
.kpi .v {{font-size: 1.75rem; font-weight: 800; color: {INK}; line-height: 1.15; margin-top: 2px;}}
.kpi .v small {{font-size: .9rem; color: {MUTED}; font-weight: 600;}}
.kpi .d {{font-size: .8rem; margin-top: 4px; font-weight: 600;}}
.up {{color: {GREEN};}} .down {{color: #d03b3b;}} .flat {{color: {MUTED};}}

/* pills, avatars */
.pill {{display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .76rem; font-weight: 600; white-space: nowrap;}}
.p-high {{background: #fde8e8; color: #c22b2b;}} .p-med {{background: #fff1e3; color: #b65a0b;}}
.p-low {{background: #e5f6ec; color: #17834c;}} .p-grey {{background: #f0f1f4; color: #6a7080;}}
.p-purple {{background: #efe8fc; color: #6237c4;}} .p-blue {{background: #e6effc; color: #1d5fb3;}}
.av {{display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; font-weight: 700;
      width: 32px; height: 32px; font-size: .78rem; vertical-align: middle; margin-right: 8px; flex: none;}}
.cell {{display: flex; align-items: center; font-size: .9rem; color: {INK};}}
.th {{font-size: .78rem; color: {MUTED}; font-weight: 600;}}

/* lists of students */
div[class*="st-key-list_"] [data-testid="stHorizontalBlock"] {{border-bottom: 1px solid {LINE}; padding: 4px 2px; align-items: center;}}
div[class*="st-key-list_"] button {{min-height: 30px; padding: 2px 8px; border-color: #f2ccd4; color: {CRIMSON}; background: #fff; width: 100%;}}
div[class*="st-key-list_"] button p {{font-size: .82rem; font-weight: 600; color: {CRIMSON};}}

/* buttons */
button[kind="primary"], button[kind="primaryFormSubmit"] {{background: {CRIMSON} !important; border-color: {CRIMSON} !important;}}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p {{color: #fff !important; font-weight: 600;}}
button[data-baseweb="tab"] p {{font-size: .92rem !important; font-weight: 600 !important;}}
button[data-baseweb="tab"][aria-selected="true"] p {{color: {CRIMSON} !important;}}
div[data-baseweb="tab-highlight"] {{background-color: {CRIMSON} !important;}}

/* top bar */
.st-key-topbar {{background: #fff; border: 1px solid {LINE}; border-radius: 16px; padding: 10px 12px 10px 16px;
    box-shadow: 0 1px 3px rgba(16,24,40,.05); margin-bottom: .6rem;}}
.st-key-topbar [data-testid="stMarkdownContainer"] p {{margin: 0;}}
.tb-ctx {{display: flex; align-items: center; gap: 12px; min-width: 0;}}
.tb-ic {{width: 40px; height: 40px; border-radius: 12px; background: #fdecef; display: flex; align-items: center;
         justify-content: center; flex: none;}}
.tb-college {{font-weight: 700; color: {INK}; font-size: .95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.tb-sub {{font-size: .8rem; color: {MUTED}; display: flex; align-items: center; gap: 8px; white-space: nowrap;}}
.tb-live {{color: {GREEN}; font-weight: 600;}}
.tb-week {{display: inline-block; width: 56px; height: 5px; background: #eef0f4; border-radius: 4px; overflow: hidden;}}
.tb-week > span {{display: block; height: 100%; background: {CRIMSON}; border-radius: 4px;}}
.st-key-top_search [data-testid="stTextInputRootElement"], .st-key-top_search div[data-baseweb="input"] {{
    background: #f3f4f8 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238a90a0' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E") no-repeat 14px center !important;
    border: 1px solid transparent !important; border-radius: 12px !important; min-height: 42px;}}
.st-key-top_search [data-testid="stTextInputRootElement"]:focus-within, .st-key-top_search div[data-baseweb="input"]:focus-within {{
    border-color: {CRIMSON} !important; background-color: #fff !important;}}
.st-key-top_search [data-testid="stTextInputRootElement"] > div, .st-key-top_search div[data-baseweb="input"] > div {{background: transparent !important;}}
.st-key-top_search input {{padding-left: 40px !important; font-size: .9rem; color: {INK}; background: transparent !important;}}
.st-key-tb_alerts button {{border-radius: 12px; min-height: 42px; border: 1px solid #f6d5dc; background: #fff6f7; white-space: nowrap;}}
.st-key-tb_alerts button p, .st-key-tb_alerts button span {{color: {CRIMSON}; font-weight: 600; font-size: .86rem;}}
.st-key-tb_alerts button:hover {{background: #fdecef; border-color: {CRIMSON};}}
.tb-user {{display: flex; align-items: center; gap: 2px; padding-left: 14px; border-left: 1px solid {LINE}; min-width: 0;}}
.tb-user .n {{font-weight: 700; color: {INK}; font-size: .88rem; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.tb-user .r {{font-size: .76rem; color: {MUTED}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.st-key-logout button {{min-height: 42px; border-radius: 12px; padding: 0 6px;}}
.st-key-logout button [data-testid="stMarkdownContainer"] {{display: none;}}
.st-key-logout button span {{font-size: 1.25rem !important;}}
@media (max-width: 1320px) {{
  .tb-ic, .tb-user .r {{display: none;}}
  .tb-user {{padding-left: 10px;}}
}}
.st-key-logout button p, .st-key-logout button span {{color: {MUTED}; font-weight: 600; font-size: .86rem;}}
.st-key-logout button:hover {{background: #f3f4f8;}}
.st-key-logout button:hover p, .st-key-logout button:hover span {{color: {CRIMSON};}}

/* misc blocks */
.insight {{background: #fff6f7; border: 1px solid #f6d5dc; border-radius: 12px; padding: 14px 16px;}}
.insight .h {{color: {CRIMSON}; font-weight: 700; margin-bottom: 6px;}}
.reco {{background: linear-gradient(90deg, #fff4f6, #fff); border: 1px solid #f6d5dc; border-radius: 12px; padding: 14px 18px;}}
.reco .h {{color: {CRIMSON}; font-weight: 700;}}
.kv {{display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {LINE}; font-size: .9rem;}}
.kv span:first-child {{color: {TEXT};}} .kv span:last-child {{color: {INK}; font-weight: 600;}}
.bar {{height: 8px; background: #f0f1f4; border-radius: 6px; overflow: hidden; margin: 4px 0 10px 0;}}
.bar > div {{height: 100%; border-radius: 6px;}}
.step {{background: #fff; border: 1px solid {LINE}; border-left: 4px solid {CRIMSON}; border-radius: 10px; padding: 10px 14px;
        margin-bottom: 8px; color: {TEXT}; font-size: .92rem;}}
.ring {{width: 104px; height: 104px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-left: auto;}}
.ring > div {{width: 82px; height: 82px; border-radius: 50%; background: #fff; display: flex; flex-direction: column;
              align-items: center; justify-content: center;}}
.ring b {{font-size: 1.9rem; color: {INK}; line-height: 1;}} .ring span {{font-size: .72rem; color: {MUTED};}}
.segcard {{border-radius: 14px; padding: 16px 18px; border: 1px solid {LINE}; min-height: 186px; margin-bottom: 8px;}}
.segcard .ic {{width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
               font-size: 20px; background: #fff; margin-bottom: 8px;}}
.segcard .t {{font-weight: 700; color: {INK};}} .segcard .c {{font-size: .86rem; color: {TEXT}; margin: 2px 0 6px 0;}}
.segcard .d {{font-size: .84rem; color: {MUTED}; line-height: 1.4;}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
def data_version():
    """Changes whenever the data is rebuilt (by this app, another visitor, or the nightly sync)."""
    p = C.PROC_DIR / "meta.json"
    return p.stat().st_mtime if p.exists() else 0.0


_SETTINGS_SEEN = [None]


def _fresh_settings():
    """Reload the college settings if another process (e.g. the nightly sync) changed them."""
    import importlib
    m = C.SETTINGS_FILE.stat().st_mtime if C.SETTINGS_FILE.exists() else 0.0
    if _SETTINGS_SEEN[0] is None:
        _SETTINGS_SEEN[0] = m
    elif m != _SETTINGS_SEEN[0]:
        _SETTINGS_SEEN[0] = m
        importlib.reload(C)


@st.cache_data(show_spinner=False, max_entries=2)
def load(version=0.0):
    P = C.PROC_DIR
    if not (P / "meta.json").exists():
        import time
        busy = C.ROOT / "data" / "processed_backup"  # another process is rebuilding right now: wait for it
        for _ in range(360):
            if (P / "meta.json").exists() or not busy.exists():
                break
            time.sleep(0.5)
    if not (P / "meta.json").exists():
        from .pipeline import run
        run(verbose=False)
    S = pd.read_parquet(P / "students.parquet").set_index("roll_no")
    for c in ("acad_reasons", "placement_reasons"):
        S[c] = S[c].map(json.loads)
    R = pd.read_parquet(P / "risk_by_week.parquet").set_index("roll_no")
    S["risk_trend"] = R.loc[S.index].values.round(3).tolist()
    return dict(
        S=S, risk_week=R,
        contrib=pd.read_parquet(P / "score_contributions.parquet").set_index("roll_no"),
        panel=pd.read_parquet(P / "weekly_panel.parquet"),
        subj_att=pd.read_parquet(P / "subject_attendance.parquet"),
        exams=pd.read_parquet(P / "exam_results.parquet"),
        sgpa=pd.read_parquet(P / "sgpa_history.parquet"),
        events=pd.read_parquet(P / "events.parquet"),
        curve=pd.read_csv(P / "backtest_curve.csv"),
        trend=pd.read_csv(P / "score_trend.csv"),
        effects=pd.read_csv(P / "intervention_effects.csv"),
        meta=json.loads((P / "meta.json").read_text()),
    )


@st.cache_resource(show_spinner=False, max_entries=2)
def _models(version):
    with open(C.PROC_DIR / "models.pkl", "rb") as f:
        return pickle.load(f)


def load_models():
    return _models(data_version())


def data():
    _fresh_settings()
    with st.spinner("Preparing student data. The first start takes about 15 seconds."):
        return load(data_version())


def user():
    return st.session_state.get("user") or {}


def scoped(S):
    """Limit to the signed-in person's department, if they have one (for example an HOD)."""
    d = user().get("dept")
    return S[S["dept"] == d] if d else S


def data_source():
    """dict(type='server', synced_at=...) when the data came from the college server, else {}."""
    try:
        return json.loads(C.SETTINGS_FILE.read_text()).get("source", {}) if C.SETTINGS_FILE.exists() else {}
    except Exception:
        return {}


def scope_text():
    d = user().get("dept")
    return f"{d} department" if d else "the whole college"


# ---------------------------------------------------------------- actions log
ACTIONS_PATH = C.PROC_DIR / "actions_log.csv"
ACTION_COLS = ["logged_at", "week", "roll_no", "name", "dept", "action", "owner", "note", "follow_up_week", "status", "logged_by"]


def read_actions():
    if ACTIONS_PATH.exists():
        return pd.read_csv(ACTIONS_PATH)
    return pd.DataFrame(columns=ACTION_COLS)


def log_actions(rows):
    stamp = now().strftime("%Y-%m-%d %H:%M")
    for r in rows:
        r.setdefault("logged_at", stamp)
        r.setdefault("logged_by", user().get("name", "Dashboard"))
    pd.concat([read_actions(), pd.DataFrame(rows)], ignore_index=True).to_csv(ACTIONS_PATH, index=False)


# ---------------------------------------------------------------- small pieces
def now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))  # India time


def title(text, sub=None):
    st.title(text)
    st.markdown(f"<div class='sub'>{sub or ''}</div>", unsafe_allow_html=True)


def kpi(icon, tint, fg, label, value, unit="", delta="", tone="flat"):
    arrow = {"up": "↑ ", "down": "↓ ", "flat": ""}[tone]
    return (f"<div class='kpi'><div class='ic' style='background:{tint};color:{fg}'>{icon}</div><div>"
            f"<div class='l'>{label}</div><div class='v'>{value} <small>{unit}</small></div>"
            f"<div class='d {tone}'>{arrow}{delta}</div></div></div>")


def pill(text, kind="grey"):
    return f"<span class='pill p-{kind}'>{text}</span>"


def risk_pill(level):
    kind = {"High": "high", "Medium": "med", "Low": "low"}.get(level, "grey")
    return pill(RISK_WORD.get(level, level), kind)


def initials(name):
    parts = [p for p in str(name).replace(".", " ").split() if p]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def avatar(name, size=32):
    i = int(hashlib.md5(str(name).encode()).hexdigest(), 16) % len(AVATAR_BG)
    fs = max(11, size // 2.6)
    return (f"<span class='av' style='background:{AVATAR_BG[i]};color:{AVATAR_FG[i]};width:{size}px;height:{size}px;"
            f"font-size:{fs:.0f}px'>{initials(name)}</span>")


def bar(pct, color=CRIMSON):
    return f"<div class='bar'><div style='width:{max(0, min(100, pct)):.0f}%;background:{color}'></div></div>"


def ring(score, label="Success Score"):
    color = CRIMSON if score < 40 else (ORANGE if score < 55 else (BLUE if score < 70 else GREEN))
    return (f"<div class='ring' style='background:conic-gradient({color} {score * 3.6:.0f}deg, #f0f1f4 0)'>"
            f"<div><b>{score:.0f}</b><span>{label}</span></div></div>")


def style(fig, h=300, legend=True):
    fig.update_layout(height=h, margin=dict(l=4, r=12, t=30 if legend else 8, b=4),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family=FONT, size=12, color=TEXT),
                      hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(color=INK, size=12)),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right", title=None,
                                  traceorder="normal", font=dict(size=12)),
                      showlegend=legend)
    fig.update_xaxes(gridcolor=LINE, linecolor=LINE, zerolinecolor=LINE, tickfont=dict(color=MUTED), showgrid=False)
    fig.update_yaxes(gridcolor=LINE, linecolor="rgba(0,0,0,0)", zerolinecolor=LINE, tickfont=dict(color=MUTED))
    try:
        fig.update_layout(barcornerradius=4)
    except Exception:
        pass
    return fig


def chart(fig, key=None):
    st.plotly_chart(fig, config={"displayModeBar": False}, key=key)


def open_student(roll):
    st.session_state["student"] = roll
    st.session_state["profile_pick"] = roll
    st.switch_page(PAGES["profile"])


def student_list(df, key, columns, page_size=10, button="View"):
    """Rows of students with a View button, like a directory. columns: list of (header, width, fn(roll,row)->html)."""
    if not len(df):
        st.info("No students match these filters.")
        return
    pages = max(1, -(-len(df) // page_size))
    pkey = f"pg_{key}"
    p = min(st.session_state.get(pkey, 1), pages)
    chunk = df.iloc[(p - 1) * page_size: p * page_size]
    widths = [w for _, w, _ in columns] + [0.85]
    with st.container(key=f"list_{key}"):
        hdr = st.columns(widths, vertical_alignment="center")
        for c, (h, _, _) in zip(hdr, columns):
            c.markdown(f"<div class='th'>{h}</div>", unsafe_allow_html=True)
        hdr[-1].markdown("<div class='th'>Action</div>", unsafe_allow_html=True)
        for roll, row in chunk.iterrows():
            cols = st.columns(widths, vertical_alignment="center")
            for c, (_, _, fn) in zip(cols, columns):
                c.markdown(f"<div class='cell'>{fn(roll, row)}</div>", unsafe_allow_html=True)
            if cols[-1].button(button, key=f"{key}_{roll}"):
                open_student(roll)
    if pages > 1:
        a, b, c = st.columns([1, 2, 1])
        if a.button("Previous", key=f"{key}_prev", disabled=p <= 1):
            st.session_state[pkey] = p - 1
            st.rerun()
        b.markdown(f"<div class='muted' style='text-align:center;padding-top:6px'>Page {p} of {pages} "
                   f"({len(df)} students)</div>", unsafe_allow_html=True)
        if c.button("Next", key=f"{key}_next", disabled=p >= pages):
            st.session_state[pkey] = p + 1
            st.rerun()


# common column builders
def col_name(roll, r):
    return f"{avatar(r['name'])}<div><div style='font-weight:600'>{r['name']}</div><div class='muted'>{roll}</div></div>"


def col_class(roll, r):
    return f"{r['dept']}, year {r['year']}"


def col_risk(roll, r):
    return risk_pill(r["acad_risk"])


def col_score(roll, r):
    return f"<b>{r['success_score']:.0f}</b>"


def col_reason(roll, r):
    return f"<span style='font-size:.84rem;color:{TEXT}'>{r['acad_reasons'][0] if r['acad_reasons'] else 'No strong warning signs'}</span>"


# ---------------------------------------------------------------- optional AI
def ai_key():
    k = st.session_state.get("gemini_key") or os.environ.get("GEMINI_API_KEY", "")
    if not k:
        try:
            k = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            k = ""
    return k


def ai_model():
    from .ai import DEFAULT_MODEL
    return st.session_state.get("gemini_model") or DEFAULT_MODEL
