import html as H

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import ui
from src.analytics import ALERT_RULE, _driver_family
from src.segments import SEG

STATUSES = ["Pending", "Planned", "In progress", "Done", "Could not reach"]
STATUS_PILL = {"Pending": "med", "Planned": "blue", "In progress": "blue", "Done": "low", "Could not reach": "high"}


def needs_action(V):
    m = (V["acad_risk"] == "High") | (V["segment"] == "Silent Strugglers") | (
        (V["year"] >= 3) & (V["segment"] == "Book-smart, Job-shy"))
    return V[m].sort_values("acad_prob", ascending=False)


def issue(r):
    if r["segment"] == "Book-smart, Job-shy":
        return "Placement readiness"
    if r["segment"] == "Silent Strugglers":
        return "Falling engagement"
    fams = [_driver_family(x) for x in r["acad_reasons"]]
    if r["acad_risk"] == "High" and r["placement_risk"] == "High":
        return "Academic and placement"
    return fams[0] if fams else "Academic risk"


def report_html(V, A, effects, meta):
    hi = V[V["acad_risk"] == "High"].sort_values("acad_prob", ascending=False).head(25)
    seg = V["segment"].value_counts()
    rows = "".join(f"<tr><td>{H.escape(r['name'])}</td><td>{k}</td><td>{r['dept']} Y{r['year']}</td>"
                   f"<td>{min(r['acad_prob'], .99):.0%}</td><td>{H.escape(r['acad_reasons'][0] if r['acad_reasons'] else '')}</td>"
                   f"<td>{H.escape(r['mentor'])}</td></tr>" for k, r in hi.iterrows())
    segs = "".join(f"<tr><td>{s}</td><td>{n}</td><td>{H.escape(SEG[s]['actions'][0])}</td></tr>" for s, n in seg.items())
    eff = "".join(f"<tr><td>{r['action']}</td><td>{r['students']}</td><td>{r['fail_rate']:.0%}</td>"
                  f"<td>{r['expected_without_action']:.0%}</td></tr>" for _, r in effects.iterrows())
    done = (A["status"] == "Done").sum() if len(A) else 0
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{C.APP_NAME} weekly report</title>
<style>body{{font-family:Inter,Segoe UI,Arial,sans-serif;color:#1d2433;max-width:960px;margin:32px auto;padding:0 20px}}
h1{{color:#b3163a;margin-bottom:0}} .m{{color:#8a90a0}} table{{border-collapse:collapse;width:100%;margin:10px 0 26px}}
td,th{{border-bottom:1px solid #eceef3;padding:7px 8px;text-align:left;font-size:13px}} th{{color:#8a90a0}}
.k{{display:inline-block;border:1px solid #eceef3;border-radius:10px;padding:10px 16px;margin:0 10px 10px 0}}
.k b{{font-size:22px;display:block}}</style></head><body>
<h1>{C.APP_NAME} weekly report</h1><div class="m">{meta.get('college_name', '')}, {C.CURRENT_SEM}, week {C.CURRENT_WEEK}.
Generated {ui.now().strftime('%d %b %Y, %H:%M')}.</div>
<p><span class="k"><b>{len(V)}</b>students</span><span class="k"><b>{int((V['acad_risk'] == 'High').sum())}</b>at high risk</span>
<span class="k"><b>{int(V['newly_flagged'].sum())}</b>new this week</span><span class="k"><b>{int(V['attendance_shortage'].sum())}</b>attendance shortage ahead</span>
<span class="k"><b>{len(A)}</b>actions logged ({done} done)</span></p>
<h2>Highest-risk students</h2><table><tr><th>Name</th><th>Roll no</th><th>Class</th><th>Chance of failing</th><th>Main reason</th><th>Mentor</th></tr>{rows}</table>
<h2>Student groups and first action</h2><table><tr><th>Group</th><th>Students</th><th>First action</th></tr>{segs}</table>
<h2>What worked in past semesters</h2><table><tr><th>Action</th><th>Students</th><th>Failed</th><th>Expected without action</th></tr>{eff}</table>
<p class="m">Scores support conversations with students; they never decide anything on their own.</p></body></html>"""


def render():
    D = ui.data()
    V = ui.scoped(D["S"])
    W = D["meta"]["current_week"]
    a, b = st.columns([3, 1], vertical_alignment="bottom")
    with a:
        ui.title("Interventions and reports", "Track suggested actions, follow-ups and what works. Generate the weekly report.")
    A_all = ui.read_actions()
    A = A_all[A_all["roll_no"].isin(V.index)]
    b.download_button("Generate report", report_html(V, A, D["effects"], D["meta"]).encode(),
                      f"weekly_report_week{W}.html", mime="text/html", type="primary", icon=":material/download:",
                      use_container_width=True)

    t1, t2, t3 = st.tabs(["Suggested actions", "Follow-ups", "What works"])
    latest = A.sort_values("logged_at").groupby("roll_no").tail(1).set_index("roll_no") if len(A) else pd.DataFrame()

    with t1:
        N = needs_action(V).copy()
        N["status"] = [latest.at[r, "status"] if r in latest.index else "Pending" for r in N.index]
        with st.container(border=True):
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown(f"**{len(N)} students need an action.** <span class='muted'>High risk, hidden strugglers, and "
                        f"final-year students with good marks who are not job-ready.</span>", unsafe_allow_html=True)
            f = c2.selectbox("Status", ["All"] + STATUSES, key="int_status", label_visibility="collapsed")
            if f != "All":
                N = N[N["status"] == f]
            ui.student_list(N, "int", [
                ("Student", 2.1, ui.col_name), ("Issue", 1.4, lambda r, x: issue(x)),
                ("Suggested action", 2.2, lambda r, x: f"<span style='font-size:.86rem'>{SEG[x['segment']]['actions'][0]}</span>"),
                ("Assigned to", 1.2, lambda r, x: SEG[x["segment"]]["owner"]),
                ("Status", 0.9, lambda r, x: ui.pill(x["status"], STATUS_PILL.get(x["status"], "grey")))], page_size=10)

    with t2:
        with st.container(border=True):
            if not len(A):
                st.info("No actions logged yet. Use 'Create action plan' on a student's profile, or plan an action for a "
                        "whole group on the Segments page.")
            else:
                c = st.columns(4)
                for col, s, tint, fg in zip(c, ["Planned", "In progress", "Done", "Could not reach"],
                                            ["#e6effc", "#fff1e3", "#e5f6ec", "#fde8e8"],
                                            [ui.BLUE, "#b65a0b", ui.GREEN, "#c22b2b"]):
                    col.markdown(ui.kpi("•", tint, fg, s, int((A["status"] == s).sum())), unsafe_allow_html=True)
                st.write("")
                view = A[["name", "dept", "action", "owner", "follow_up_week", "status", "note"]].rename(columns={
                    "name": "Student", "dept": "Dept", "action": "Action", "owner": "Owner",
                    "follow_up_week": "Follow-up week", "status": "Status", "note": "Note"})
                ed = st.data_editor(view, hide_index=True, key="tracker", height=380,
                                    disabled=[c for c in view.columns if c != "Status"],
                                    column_config={"Status": st.column_config.SelectboxColumn("Status", options=STATUSES[1:])})
                if st.button("Save status changes", type="primary"):
                    full = ui.read_actions()
                    full.loc[ed.index, "status"] = ed["Status"].values
                    full.to_csv(ui.ACTIONS_PATH, index=False)
                    st.success("Saved.")
                    st.rerun()
                st.caption("Change a status in the table, then press Save.")

    with t3:
        e = D["effects"]
        acted = e[e["action"] != "No action taken"]
        with st.container(border=True):
            if not len(acted):
                st.info("Not enough past actions to measure yet. As mentors log actions here, this chart fills in.")
            else:
                best = acted.iloc[0]
                st.markdown(f"### {best['action']} worked best")
                st.markdown(f"<div class='muted'>{best['fail_rate_reduction']:.0%} fewer failures than in similar students "
                            f"who got no help</div>", unsafe_allow_html=True)
                fig = go.Figure()
                fig.add_trace(go.Bar(y=acted["action"], x=acted["expected_without_action"] * 100, orientation="h",
                                     name="Similar students, no help", marker_color=ui.GREY,
                                     hovertemplate="%{y}: %{x:.0f}% failed without help<extra></extra>"))
                fig.add_trace(go.Bar(y=acted["action"], x=acted["fail_rate"] * 100, orientation="h",
                                     name="Students who got this help", marker_color=ui.CRIMSON,
                                     text=[f"{v:.0%} fewer failures" for v in acted["fail_rate_reduction"]],
                                     textposition="outside", textfont=dict(color=ui.TEXT), cliponaxis=False,
                                     hovertemplate="%{y}: %{x:.0f}% failed<extra></extra>"))
                fig.update_layout(barmode="group")
                fig.update_yaxes(autorange="reversed")
                fig.update_xaxes(title="% who failed at least one subject", range=[0, 60], ticksuffix="%")
                ui.chart(ui.style(fig, 360), key="int_eff")
                st.caption(f"Students flagged by the college's old alert ({ALERT_RULE}). Mentors followed up on about "
                           "60%, based on time available, so the rest are a fair comparison.")
