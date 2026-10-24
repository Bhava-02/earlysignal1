import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import ui
from src.analytics import _driver_family


def render():
    D = ui.data()
    M = D["meta"]
    V = ui.scoped(D["S"])
    W = M["current_week"]
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    with a:
        ui.title("Analytics and insights", f"Deeper trends for {ui.scope_text()}, and how this semester compares with last.")
    depts = ["All departments"] + sorted(V["dept"].unique())
    dsel = b.selectbox("Department", depts, key="an_dept", label_visibility="collapsed")
    if dsel != "All departments":
        V = V[V["dept"] == dsel]

    pnl = D["panel"]
    pnl = pnl[pnl["roll_no"].isin(V.index) & (pnl["week"] <= W)]
    now_, before = pnl[pnl["semester"] == C.CURRENT_SEM], pnl[pnl["semester"] == C.TEST_SEM]
    att = lambda p: 100 * p["classes_attended"].sum() / max(p["classes_held"].sum(), 1)
    lms = lambda p: p["logins"].mean()
    d_att, d_lms = att(now_) - att(before), lms(now_) - lms(before)
    y34 = V[V["year"] >= 3]
    cols = st.columns(4)
    cards = [
        ui.kpi("🎓", "#e6effc", ui.BLUE, "Academic performance", f"{V['cgpa'].mean():.2f}", "avg CGPA",
               f"{(V['backlogs'] > 0).mean():.0%} have standing arrears", "flat"),
        ui.kpi("📅", "#e5f6ec", ui.GREEN, "Attendance", f"{att(now_):.0f}%", "this semester",
               f"{abs(d_att):.1f} pts vs last semester", "up" if d_att > 0 else "down"),
        ui.kpi("💻", "#fdeef1", ui.CRIMSON, "Engagement", f"{lms(now_):.1f}", "LMS logins / week",
               f"{abs(d_lms):.1f} vs last semester", "up" if d_lms > 0 else "down"),
        ui.kpi("🎯", "#efe8fc", ui.PURPLE, "Placement", f"{y34['mock_interviews'].mean():.1f}" if len(y34) else "–",
               "mock interviews / student", f"{(y34['placement_risk'] == 'Low').mean():.0%} placement-ready" if len(y34) else "",
               "flat"),
    ]
    for c, h in zip(cols, cards):
        c.markdown(h, unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1.5, 1], gap="medium")
    with left.container(border=True):
        st.markdown("### Students at risk, week by week")
        R = D["risk_week"].loc[V.index]
        fig = go.Figure()
        for i, dept in enumerate([d for d in C.DEPTS if d in V["dept"].unique()]):
            idx = V.index[V["dept"] == dept]
            y = (R.loc[idx] >= C.RISK_MEDIUM).mean() * 100
            fig.add_trace(go.Scatter(x=[int(c) for c in y.index], y=y.values, name=dept, mode="lines+markers",
                                     line=dict(color=ui.dept_color(dept, i), width=2.5), marker=dict(size=7),
                                     hovertemplate=f"{dept}, week %{{x}}: %{{y:.0f}}% at risk<extra></extra>"))
        fig.update_xaxes(tickprefix="Wk ", dtick=1)
        fig.update_yaxes(ticksuffix="%", rangemode="tozero")
        ui.chart(ui.style(fig, 290), key="an_risk")
    with right.container(border=True):
        st.markdown("### Risk factors")
        st.markdown("<div class='muted'>Share of high-risk students showing each warning sign</div>", unsafe_allow_html=True)
        hi = V[V["acad_risk"] == "High"]
        fam = {}
        for rs in hi["acad_reasons"]:
            for f in {_driver_family(r) for r in rs}:
                fam[f] = fam.get(f, 0) + 1
        html = ""
        for f, n in sorted(fam.items(), key=lambda x: -x[1])[:6]:
            share = n / max(len(hi), 1)
            html += (f"<div style='display:flex;justify-content:space-between;font-size:.88rem;margin-top:6px'>"
                     f"<span>{f}</span><b>{share:.0%}</b></div>{ui.bar(share * 100, ui.CRIMSON)}")
        st.markdown(html or "<div class='muted'>No high-risk students.</div>", unsafe_allow_html=True)

    left, right = st.columns([1.5, 1], gap="medium")
    with left.container(border=True):
        st.markdown("### This semester compared with last")
        metric = st.radio("Measure", ["Attendance", "LMS logins", "Assignments submitted"], horizontal=True,
                          key="an_metric", label_visibility="collapsed")
        fn = {"Attendance": att, "LMS logins": lms,
              "Assignments submitted": lambda g: 100 * g["assignments_submitted"].sum() / max(g["assignments_due"].sum(), 1)}[metric]
        fig = go.Figure()
        for p_, color, name, dash in [(before, ui.GREY, "Last semester", "dot"), (now_, ui.CRIMSON, "This semester", "solid")]:
            s = p_.groupby("week").apply(fn)
            if metric == "Assignments submitted":
                s = s[[w for w in s.index if w not in (6, 12, 16)]]
            fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines+markers",
                                     line=dict(color=color, width=2.5 if dash == "solid" else 2, dash=dash), marker=dict(size=7),
                                     hovertemplate=f"{name}, week %{{x}}: %{{y:.1f}}<extra></extra>"))
        fig.update_xaxes(tickprefix="Wk ", dtick=1)
        ui.chart(ui.style(fig, 270), key="an_cmp")
    with right.container(border=True):
        st.markdown("### Success Score bands")
        bands = ["At Risk", "Needs Attention", "On Track", "Thriving"]
        colors = ["#d6304a", "#f2a3a2", "#86b6ef", ui.BLUE]
        counts = [int((V["band"] == b_).sum()) for b_ in bands]
        fig = go.Figure(go.Bar(x=bands, y=counts, marker_color=colors, text=counts, textposition="outside",
                               textfont=dict(color=ui.TEXT), cliponaxis=False,
                               hovertemplate="%{x}: %{y} students<extra></extra>"))
        fig.update_yaxes(showticklabels=False, showgrid=False, range=[0, max(counts) * 1.2 if counts else 1])
        ui.chart(ui.style(fig, 270, legend=False), key="an_bands")

    with st.container(border=True):
        st.markdown("### Does the early warning work?")
        bt = M["backtest"]
        st.markdown(f"<div class='muted'>Tested on {bt['test_semester']}, a semester the model never saw. By week 6 it had "
                    f"flagged <b>{bt['recall_by_week6']:.0%}</b> of the students who went on to fail; the usual attendance "
                    f"and marks lists had flagged <b>{bt['rule_recall_by_week6']:.0%}</b>.</div>", unsafe_allow_html=True)
        c = D["curve"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=c["week"], y=c["rule_recall"] * 100, name="Usual lists", mode="lines+markers",
                                 line=dict(color=ui.GREY, width=2, dash="dot"), marker=dict(size=7),
                                 hovertemplate="Usual lists, week %{x}: %{y:.0f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=c["week"], y=c["recall"] * 100, name=C.APP_NAME, mode="lines+markers",
                                 line=dict(color=ui.CRIMSON, width=3), marker=dict(size=8),
                                 hovertemplate=f"{C.APP_NAME}, week %{{x}}: %{{y:.0f}}%<extra></extra>"))
        fig.add_vline(x=C.CIA1_RESULTS_WEEK, line=dict(color="#c7ccd5", dash="dash", width=1))
        fig.add_annotation(x=C.CIA1_RESULTS_WEEK, y=10, text="Internal marks published", showarrow=False, xanchor="left",
                           font=dict(color=ui.MUTED, size=11))
        fig.update_xaxes(tickprefix="Wk ", dtick=1)
        fig.update_yaxes(ticksuffix="%", range=[0, 100], title="failing students already flagged")
        ui.chart(ui.style(fig, 280), key="an_proof")
