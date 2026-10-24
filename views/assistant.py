import streamlit as st

from src import ai, nlq, ui
from src.segments import ORDER

EXAMPLES = ["CSE 3rd years with attendance below 75",
            "Final years with CGPA above 8 and no mock interviews",
            "High risk day scholars in ECE",
            "Hidden strugglers in IT",
            "Students newly flagged this week",
            "Hostel students in IT with coding below 40"]


def render():
    D = ui.data()
    S = D["S"]
    V = ui.scoped(S)
    ui.title("AI assistant", "Ask in plain English. You get the matching students and a short answer. "
                             "Numbers always come from the data, never from the AI.")
    with st.container(border=True):
        st.markdown("**Try one of these**")
        cols = st.columns(3)
        for i, ex in enumerate(EXAMPLES):
            if cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state["ask_last"] = ex
    q = st.chat_input("Ask about your students, e.g. hostel students in IT with coding below 40")
    if q:
        st.session_state["ask_last"] = q
    q = st.session_state.get("ask_last")
    if not q:
        st.markdown("<div class='muted' style='margin-top:12px'>Type a question in the box at the bottom of the page.</div>",
                    unsafe_allow_html=True)
        return
    with st.chat_message("user"):
        st.markdown(q)
    spec, how = None, "built-in reader"
    if ui.ai_key():
        try:
            spec = ai.call_gemini(nlq.ai_prompt(q, ORDER), ui.ai_key(), ui.ai_model(), want_json=True)
            how = "AI"
        except (ai.AIError, ValueError):
            spec = None
    if spec is None:
        spec = nlq.rule_parse(q.replace("hidden strugglers", "silent strugglers").replace("Hidden strugglers", "silent strugglers"),
                              ORDER, sorted(S["mentor"].unique()))
    R, applied = nlq.apply(V.reset_index(), spec)
    R = R.set_index("roll_no")
    with st.chat_message("assistant"):
        if not applied:
            st.markdown("I couldn't match that to a filter, so here is everyone. Try a department, a year, attendance, "
                        "CGPA, risk or a student group.")
        if len(R):
            st.markdown(f"**{len(R)} students** match ({spec.get('explanation', '')}). Their average Success Score is "
                        f"**{R['success_score'].mean():.0f}** against {V['success_score'].mean():.0f} overall, and "
                        f"**{(R['acad_risk'] == 'High').mean():.0%}** are at high risk.")
        else:
            st.markdown(f"No students match ({spec.get('explanation', '')}). Try loosening one condition.")
        st.caption(f"Understood by the {how}.")
    if len(R):
        with st.container(border=True):
            ui.student_list(R, "ask", [("Name", 2.2, ui.col_name), ("Class", 1.0, ui.col_class),
                                       ("CGPA", 0.6, lambda r, x: f"{x['cgpa']:.1f}"), ("Score", 0.6, ui.col_score),
                                       ("Risk", 0.9, ui.col_risk), ("Main reason", 2.4, ui.col_reason)], page_size=10)
