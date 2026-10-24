import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import ui
from src.scoring import INDICATORS, SUB_LABEL


def render():
    D = ui.data()
    M = D["meta"]
    bt = M["backtest"]
    ui.title("How scores work",
              "Two numbers appear everywhere in EarlySignal: the Success Score (how a student is doing now) and the "
              "risk level (how likely things are to go wrong this semester).")

    a, b = st.columns(2, gap="large")
    with a:
        with st.container(border=True):
            st.markdown("### Success Score, 0 to 100")
            st.markdown("A mix of three parts, each built from things the college already records:\n"
                        "- **Academic health:** CGPA, internal test marks, attendance, arrears, faculty rating\n"
                        "- **Engagement:** LMS logins, assignments, whether these are rising or falling, events and "
                        "clubs, satisfaction survey\n"
                        "- **Placement readiness:** aptitude, coding, mock interviews, skills tests, certifications, "
                        "recruiter eligibility")
            st.markdown("**It works like a marksheet out of 100.** Each item has maximum marks (CGPA is worth about 10 "
                        "of the 100 for a final-year student). A student gets full marks at a top level (CGPA 9.5 or "
                        "more), zero at a bottom level (CGPA 5.0 or less), and part marks in between. Add up the marks "
                        "and you get the Success Score. Every student's profile shows their full marksheet.")
            st.markdown("**70 and above** thriving, **55 to 70** on track, **40 to 55** needs attention, "
                        "**below 40** at risk.")
    with b:
        with st.container(border=True):
            st.markdown("### Risk level")
            st.markdown(f"Each week a model estimates the chance that a student fails at least one subject this "
                        f"semester. **High** is {C.RISK_HIGH:.0%} or more, **Medium** {C.RISK_MEDIUM:.0%} to "
                        f"{C.RISK_HIGH:.0%}, **Low** below that.")
            st.markdown(f"**Does it work?** We tested it on a past semester it had never seen. By week 6 it had "
                        f"flagged **{bt['recall_by_week6']:.0%}** of the students who went on to fail. The usual "
                        f"attendance and marks lists had flagged **{bt['rule_recall_by_week6']:.0%}**.")

    st.subheader("Proof: the model warns earlier than the usual lists")
    c = D["curve"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=c["week"], y=c["rule_recall"] * 100, name="Usual lists (attendance shortage and low marks)",
                             mode="lines+markers", line=dict(color=ui.GREY, width=2, dash="dot"), marker=dict(size=7),
                             hovertemplate="Usual lists, week %{x}: %{y:.0f}% caught<extra></extra>"))
    fig.add_trace(go.Scatter(x=c["week"], y=c["recall"] * 100, name="EarlySignal", mode="lines+markers",
                             line=dict(color=ui.CRIMSON, width=3), marker=dict(size=8),
                             hovertemplate="EarlySignal, week %{x}: %{y:.0f}% caught<extra></extra>"))
    fig.add_vline(x=C.CIA1_RESULTS_WEEK, line=dict(color="#c7ccd5", dash="dash", width=1))
    fig.add_annotation(x=C.CIA1_RESULTS_WEEK, y=10, text="Internal test marks come out", showarrow=False,
                       xanchor="left", font=dict(color=ui.MUTED, size=12))
    fig.update_xaxes(title="Week of semester", dtick=1)
    fig.update_yaxes(title="% of failing students already flagged", range=[0, 100], ticksuffix="%")
    ui.chart(ui.style(fig, 300), key="m_curve")
    st.caption(f"Trained on {bt['train_semester']}, tested on {bt['test_semester']}. The gap before week 7 is the "
               "point: attendance, LMS and assignment signals show up weeks before marks do.")

    st.subheader("How much each part counts")
    st.markdown("<div class='muted'>Placement counts more as students get closer to placement season.</div>",
                unsafe_allow_html=True)
    fig = go.Figure()
    years = [f"Year {y}" for y in C.SCORE_WEIGHTS]
    for sub, color in zip(SUB_LABEL, ["#1c5cab", "#6da7ec", "#b7d3f6"]):
        vals = [C.SCORE_WEIGHTS[y][sub] * 100 for y in C.SCORE_WEIGHTS]
        fig.add_trace(go.Bar(y=years, x=vals, name=SUB_LABEL[sub], orientation="h", marker_color=color,
                             marker_line=dict(color="#fff", width=2), text=[f"{v:.0f}%" for v in vals],
                             textposition="inside", insidetextfont=dict(color=ui.INK if sub == "placement" else "#fff"),
                             hovertemplate=f"%{{y}}, {SUB_LABEL[sub]}: %{{x:.0f}}%<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[0, 100], showticklabels=False, showgrid=False)
    fig.update_yaxes(autorange="reversed")
    ui.chart(ui.style(fig, 210), key="m_weights")

    with st.expander("Every indicator and its weight"):
        wt = M["weight_table"]
        rows = []
        for k, sub, lab, lo, hi, inv, w, yrs in INDICATORS:
            rows.append({"Indicator": lab, "Part": SUB_LABEL[sub],
                         "Scored from 0 to 1 between": f"{hi} and {lo}" if inv else f"{lo} and {hi}",
                         **{f"Year {y}": (f"{100 * wt[str(y)][k]:.1f}%" if k in wt[str(y)] else "-") for y in C.SCORE_WEIGHTS}})
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=660)
    with st.expander("Limits and safeguards"):
        st.markdown("- This prototype uses realistic made-up data that mimics real campus systems, including their "
                    "mistakes. Real data will be noisier, so the model should be re-checked every semester.\n"
                    "- Scores start a conversation with a student. They never decide anything about a student on their own.\n"
                    "- Placement weights were learned from last year's graduates and who got placed.\n"
                    "- The simple model was chosen on purpose: every flag can be explained in plain words.")
    note = C.ROOT / "docs" / "SUCCESS_SCORE_NOTE.md"
    if note.exists():
        with st.expander("Read the full Success Score note"):
            st.markdown(note.read_text())
