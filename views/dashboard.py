import plotly.graph_objects as go
import streamlit as st

from src import ai, ui


def greeting():
    h = ui.now().hour
    return "Good morning" if h < 12 else ("Good afternoon" if h < 17 else "Good evening")


def render():
    D = ui.data()
    M = D["meta"]
    V = ui.scoped(D["S"])
    W = M["current_week"]
    u = ui.user()

    ui.title(f"{greeting()}, {u.get('name', 'there')}!",
             f"Here's what is happening with {ui.scope_text()} this week.")

    tr = D["trend"]
    tr = tr[tr["dept"] == (u.get("dept") or "All")]
    score_now = V["success_score"].mean()
    score_then = tr[tr["week"] == W - 3]["success"].mean() if len(tr) else score_now
    hi = int((V["acad_risk"] == "High").sum())
    new = int(V["newly_flagged"].sum())
    y34 = V[V["year"] >= 3]
    ready = (y34["placement_risk"] == "Low").mean() if len(y34) else 0
    d = score_now - score_then
    cols = st.columns(4)
    cards = [
        ui.kpi("👥", "#e6effc", ui.BLUE, "Total students", f"{len(V):,}", "",
               f"{V['dept'].nunique()} departments", "flat"),
        ui.kpi("⚠️", "#fde8e8", "#c22b2b", "At-risk students", f"{hi}", "", f"{new} new this week", "down" if new else "flat"),
        ui.kpi("⭐", "#efe8fc", ui.PURPLE, "Average Success Score", f"{score_now:.1f}", "/ 100",
               f"{abs(d):.1f} since week {W - 3}", "up" if d > 0.05 else ("down" if d < -0.05 else "flat")),
        ui.kpi("🎯", "#fdeef1", ui.CRIMSON, "Placement-ready", f"{ready:.0%}", "", f"of {len(y34)} 3rd and 4th years", "flat"),
    ]
    for c, h in zip(cols, cards):
        c.markdown(h, unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1.7, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("### Student Success trend")
            st.markdown("<div class='muted'>Average score this semester, week by week</div>", unsafe_allow_html=True)
            fig = go.Figure()
            for col, name in [("success", "Overall"), ("academic", "Academic"), ("engagement", "Engagement")]:
                fig.add_trace(go.Scatter(x=tr["week"], y=tr[col], name=name, mode="lines+markers",
                                         line=dict(color=ui.SERIES[name], width=2.5), marker=dict(size=7),
                                         hovertemplate=f"{name}, week %{{x}}: %{{y:.1f}}<extra></extra>"))
            fig.update_xaxes(title=None, tickprefix="Wk ", dtick=1)
            vals = tr[["success", "academic", "engagement"]].values
            lo, hi_ = (vals.min(), vals.max()) if len(tr) else (0, 100)
            fig.update_yaxes(range=[max(0, lo - 12), min(100, hi_ + 8)])
            ui.chart(ui.style(fig, 270), key="d_trend")
    with right:
        with st.container(border=True):
            st.markdown("### Risk distribution")
            acad = V["acad_risk"] == "High"
            plc = V["placement_risk"] == "High"
            parts = [("Academic risk only", int((acad & ~plc).sum()), "#d6304a"),
                     ("Placement risk only", int((plc & ~acad).sum()), ui.ORANGE),
                     ("Both", int((acad & plc).sum()), ui.PURPLE)]
            total = sum(p[1] for p in parts)
            fig = go.Figure(go.Pie(labels=[p[0] for p in parts], values=[p[1] for p in parts], hole=.68, sort=False,
                                   marker=dict(colors=[p[2] for p in parts], line=dict(color="#fff", width=3)),
                                   textinfo="none", hovertemplate="%{label}: %{value} students<extra></extra>"))
            fig.add_annotation(text=f"<b style='font-size:24px'>{total}</b><br><span style='font-size:11px'>with a "
                                    f"high risk</span>", showarrow=False, font=dict(color=ui.INK))
            fig.update_layout(height=200, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                              paper_bgcolor="rgba(0,0,0,0)")
            ui.chart(fig, key="d_donut")
            for name, n, color in parts:
                st.markdown(f"<div class='kv'><span><span style='color:{color}'>●</span> {name}</span>"
                            f"<span>{n} ({n / max(total, 1):.0%})</span></div>", unsafe_allow_html=True)

    left, right = st.columns([1.7, 1], gap="medium")
    with left:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1], vertical_alignment="center")
            h1.markdown("### Students needing attention")
            h2.page_link(ui.PAGES["students"], label="View all", icon=":material/arrow_forward:")
            top = V[V["acad_risk"] == "High"].sort_values(["newly_flagged", "acad_prob"], ascending=False).head(6)

            def who(roll, r):
                reason = r["acad_reasons"][0] if r["acad_reasons"] else ""
                return (f"{ui.avatar(r['name'])}<div><div style='font-weight:600'>{r['name']} "
                        f"<span class='muted' style='font-weight:400'>{r['dept']} Y{r['year']}</span></div>"
                        f"<div class='muted'>{reason}</div></div>")

            def risk_kind(roll, r):
                tag = ui.pill("Both", "purple") if r["placement_risk"] == "High" else ui.pill("Academic", "high")
                return tag + ("&nbsp;" + ui.pill("New", "blue") if r["newly_flagged"] else "")

            ui.student_list(top, "dash", [("Student", 3.6, who), ("Risk", 1.5, risk_kind),
                                          ("Score", 0.7, ui.col_score)], page_size=6)
    with right:
        with st.container(border=True):
            st.markdown("### This week's priorities")
            crit = int((V["segment"] == "Critical: Act This Week").sum())
            hidden = int((V["segment"] == "Silent Strugglers").sum())
            short = int(V["attendance_shortage"].sum())
            rec = int((V["attendance_shortage"] & (V["required_rate_for_75"] <= 95)).sum())
            for n, (t, d_) in enumerate([
                (f"Meet {crit} students who need action this week", "Several warning signs at once."),
                (f"Check in with {hidden} hidden strugglers", "Marks look fine, but effort is dropping."),
                (f"Warn {short} students about attendance", f"{rec} can still reach 75% if they attend almost every class."),
            ], 1):
                st.markdown(f"<div class='step'><b style='color:{ui.INK}'>{n}. {t}</b><br>"
                            f"<span class='muted'>{d_}</span></div>", unsafe_allow_html=True)
            st.page_link(ui.PAGES["segments"], label="See all groups and plans", icon=":material/category:")
            if ui.ai_key() and st.button("Write this as a note for my team", icon="✨"):
                stats = dict(students=len(V), high_risk=hi, newly_flagged=new, critical=crit, silent=hidden,
                             shortage=short, recoverable=rec)
                try:
                    st.markdown(ai.call_gemini(ai.weekly_brief_prompt(stats), ui.ai_key(), ui.ai_model()))
                except ai.AIError as e:
                    st.info(f"The AI could not be reached. ({e})")
