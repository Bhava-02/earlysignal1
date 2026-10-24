import streamlit as st

from src import config as C
from src import ui
from src.segments import ORDER, SEG

LOOK = {  # display name, icon, card tint, short description
    "Book-smart, Job-shy": ("High academic, low placement", "🎓", "#e9f7ef", "Strong marks but not yet ready for placements."),
    "Critical: Act This Week": ("High risk: act this week", "⚠️", "#fdecec", "Several warning signs at once, in studies and attendance."),
    "Silent Strugglers": ("Hidden strugglers", "🕵️", "#fff4e5", "Marks look fine, but logins, assignments or attendance are falling."),
    "Academic Catch-up": ("Needs academic support", "📚", "#fff1e3", "Low CGPA, arrears or low internal marks."),
    "Busy but Slipping": ("High engagement, low academics", "🎭", "#f3edfc", "Very active in events while academics fall behind."),
    "Placement-Ready Stars": ("Placement ready", "🏆", "#e8f1fd", "Strong profile, ready for placements. Good peer mentors."),
    "Steady Middle": ("Steady", "🙂", "#f4f5f7", "No urgent flags. Regular check-ins keep them on track."),
}
SHOW = ["Book-smart, Job-shy", "Critical: Act This Week", "Silent Strugglers", "Academic Catch-up", "Busy but Slipping",
        "Placement-Ready Stars", "Steady Middle"]


def render():
    D = ui.data()
    V = ui.scoped(D["S"])
    W = D["meta"]["current_week"]
    ui.title("Student segmentation", "Meaningful groups of students, each with a plan, so you can act on many students at once.")
    counts = V["segment"].value_counts()
    if st.session_state.get("seg_pick") not in ORDER:
        st.session_state["seg_pick"] = "Book-smart, Job-shy"
    for chunk in (SHOW[:3], SHOW[3:6], SHOW[6:]):
        cols = st.columns(3, gap="medium")
        for col, name in zip(cols, chunk):
            label, icon, tint, desc = LOOK[name]
            n = int(counts.get(name, 0))
            sel = st.session_state["seg_pick"] == name
            border = f"border:2px solid {ui.CRIMSON};" if sel else ""
            col.markdown(f"<div class='segcard' style='background:{tint};{border}'><div class='ic'>{icon}</div>"
                         f"<div class='t'>{label}</div><div class='c'><b>{n}</b> students</div>"
                         f"<div class='d'>{desc}</div></div>", unsafe_allow_html=True)
            if col.button("View students", key=f"seg_{name}", type="primary" if sel else "secondary"):
                st.session_state["seg_pick"] = name
                st.session_state["pg_seg"] = 1
                st.rerun()

    name = st.session_state["seg_pick"]
    seg, (label, icon, tint, desc) = SEG[name], LOOK[name]
    G = V[V["segment"] == name].sort_values("acad_prob", ascending=False)
    st.write("")
    left, right = st.columns([1, 2], gap="medium")
    with left.container(border=True):
        st.markdown(f"### {icon} {label}")
        st.markdown(f"<div class='muted'>{len(G)} students</div>", unsafe_allow_html=True)
        st.markdown(f"**Why they are here:** {seg['rule']}.")
        st.markdown(f"**What to do** (led by {seg['owner']}):")
        st.markdown("\n".join(f"- {x}" for x in seg["actions"]))
        st.markdown(f"**It's working when:** {seg['kpi']}.")
        if len(G) and st.button(f"Plan the first action for all {len(G)}", type="primary", use_container_width=True):
            ui.log_actions([dict(week=W, roll_no=r, name=G.at[r, "name"], dept=G.at[r, "dept"], action=seg["actions"][0],
                                 owner=seg["owner"], note=f"Group plan: {label}", follow_up_week=min(W + 2, C.WEEKS_PER_SEM),
                                 status="Planned") for r in G.index])
            st.success(f"Added to Interventions for {len(G)} students.")
    with right.container(border=True):
        placement = name in ("Book-smart, Job-shy", "Placement-Ready Stars")
        cols = [("Name", 2.2, ui.col_name), ("Class", 1.0, ui.col_class)]
        if placement:
            cols += [("CGPA", 0.6, lambda r, x: f"{x['cgpa']:.1f}"),
                     ("Placement", 1.0, lambda r, x: ui.risk_pill(x["placement_risk"])),
                     ("Biggest gap", 2.2, lambda r, x: f"<span style='font-size:.84rem'>{x['placement_reasons'][0] if x['placement_reasons'] else '-'}</span>")]
        else:
            cols += [("Risk", 0.9, ui.col_risk), ("Main reason", 2.4, ui.col_reason)]
        ui.student_list(G, "seg", cols, page_size=8)
