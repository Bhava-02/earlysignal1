import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import ui


def render():
    D = ui.data()
    M = D["meta"]
    Y = ui.scoped(D["S"])
    Y = Y[Y["year"] >= 3]
    ui.title("Placement readiness", "How ready 3rd and 4th years are for campus placements, and what makes the biggest "
                                    "difference, learned from last year's graduates.")
    if not len(Y):
        st.info("No 3rd or 4th year students in your view.")
        return
    pm = M["placement"]
    bsjs = Y[Y["segment"] == "Book-smart, Job-shy"]
    cols = st.columns(4)
    cards = [ui.kpi("✅", "#e5f6ec", ui.GREEN, "Placement-ready", f"{(Y['placement_risk'] == 'Low').mean():.0%}", "",
                    f"of {len(Y)} 3rd and 4th years"),
             ui.kpi("⚠️", "#fde8e8", "#c22b2b", "Not ready yet", f"{int((Y['placement_risk'] == 'High').sum())}", "students",
                    "need a placement plan"),
             ui.kpi("🎓", "#fff4e5", "#b65a0b", "Good marks, not job-ready", f"{len(bsjs)}", "students", "CGPA fine, skills not"),
             ui.kpi("🚫", "#f0f1f4", ui.MUTED, "Not eligible today", f"{(Y['eligible'] == 0).mean():.0%}", "",
                    f"CGPA below {C.PLACEMENT_CGPA_MIN} or arrears")]
    for c, h in zip(cols, cards):
        c.markdown(h, unsafe_allow_html=True)
    st.write("")
    a, b = st.columns([1.2, 1], gap="medium")
    with a.container(border=True):
        st.markdown("### What gets students placed here")
        st.markdown("<div class='muted'>How much each change raised the odds of getting placed, last year</div>",
                    unsafe_allow_html=True)
        o = pm["odds_per_unit"]
        units = [("One more mock interview", o["mock_interviews"]), ("+10 coding score", o["best_coding"] ** 10),
                 ("+10 aptitude score", o["best_aptitude"] ** 10), ("+10 soft-skills score", o["soft_skill_score"] ** 10),
                 ("One more certification", o["certifications"])]
        units = sorted(units, key=lambda x: x[1])
        fig = go.Figure(go.Bar(y=[u for u, _ in units], x=[(v - 1) * 100 for _, v in units], orientation="h",
                               marker_color=ui.CRIMSON, text=[f"+{(v - 1) * 100:.0f}%" for _, v in units],
                               textposition="outside", textfont=dict(color=ui.TEXT), cliponaxis=False,
                               hovertemplate="%{y}: odds +%{x:.0f}%<extra></extra>"))
        fig.update_xaxes(showticklabels=False, range=[0, max((v - 1) * 100 for _, v in units) * 1.25])
        ui.chart(ui.style(fig, 260, legend=False), key="pl_drv")
        st.markdown(f"**Takeaway:** mock interviews matter far more than certificates, yet "
                    f"{(Y['mock_interviews'] == 0).mean():.0%} of these students have not done one.")
    with b.container(border=True):
        st.markdown("### Readiness by department")
        depts = [d for d in C.DEPTS if d in Y["dept"].unique()]
        fig = go.Figure()
        for lvl, color, name in [("High", "#d6304a", "Not ready"), ("Medium", ui.ORANGE, "Almost"), ("Low", ui.GREEN, "Ready")]:
            vals = [(Y[Y["dept"] == d]["placement_risk"] == lvl).mean() * 100 for d in depts]
            fig.add_trace(go.Bar(y=depts, x=vals, name=name, orientation="h", marker_color=color,
                                 marker_line=dict(color="#fff", width=2), text=[f"{v:.0f}%" if v >= 8 else "" for v in vals],
                                 textposition="inside", insidetextfont=dict(color="#fff"),
                                 hovertemplate=f"%{{y}}: {name} %{{x:.0f}}%<extra></extra>"))
        fig.update_layout(barmode="stack")
        fig.update_xaxes(range=[0, 100], ticksuffix="%")
        ui.chart(ui.style(fig, 260), key="pl_dept")
        st.caption(f"Last year {pm['placement_rate']:.0%} were placed: {pm['placed_rate_eligible']:.0%} of eligible "
                   f"students, {pm['placed_rate_ineligible']:.0%} of the rest.")
    with st.container(border=True):
        h, t = st.columns([3, 1.3], vertical_alignment="center")
        h.markdown("### Students who need a placement plan")
        only = t.toggle("Only good marks, not job-ready", key="pl_only")
        show = Y[Y["placement_risk"].isin(["High", "Medium"])].sort_values("placement_prob")
        if only:
            show = show[show["segment"] == "Book-smart, Job-shy"]
        ui.student_list(show, "pl", [
            ("Name", 2.2, ui.col_name), ("Class", 1.0, ui.col_class), ("CGPA", 0.6, lambda r, x: f"{x['cgpa']:.1f}"),
            ("Placement", 0.9, lambda r, x: ui.risk_pill(x["placement_risk"])),
            ("Chance", 0.7, lambda r, x: f"<b>{x['placement_prob']:.0%}</b>"),
            ("Mock interviews", 0.9, lambda r, x: str(int(x["mock_interviews"]))),
            ("Biggest gap", 2.3, lambda r, x: f"<span style='font-size:.84rem'>{x['placement_reasons'][0] if x['placement_reasons'] else '-'}</span>")],
            page_size=10)
