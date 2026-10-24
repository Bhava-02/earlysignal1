import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import ai, ui
from src import config as C
from src.scoring import INDICATORS
from src.whatif import level, path_to_green, plevel, projected_attendance, simulate

LABELS = {k: lab for k, _, lab, *_ in INDICATORS}
SEG_NAME = {"Critical: Act This Week": "Act this week", "Silent Strugglers": "Hidden struggler",
            "Busy but Slipping": "Busy but slipping", "Academic Catch-up": "Academic catch-up",
            "Book-smart, Job-shy": "Good marks, not job-ready", "Placement-Ready Stars": "Ready and thriving",
            "Steady Middle": "Steady"}


FRIENDLY = {"cgpa": "CGPA", "cia1_pct": "Internal test marks (CIA-1)", "att_pct": "Attendance",
            "backlogs": "Standing arrears", "faculty_rating": "Faculty rating", "lms_avg": "LMS logins per week",
            "asg_rate": "Assignments submitted", "momentum": "Recent effort trend", "activities": "Events and clubs",
            "satisfaction": "Satisfaction survey", "best_aptitude": "Aptitude score", "best_coding": "Coding score",
            "mock_interviews": "Mock interviews done", "avg_mock_rating": "Mock interview rating",
            "technical_score": "Technical skills", "soft_skill_score": "Soft skills", "certifications": "Certifications",
            "eligible": "Eligible for placements"}


def fmt_value(k, v, row=None):
    if k in ("cia1_pct", "att_pct"):
        return f"{v:.0f}%"
    if k == "asg_rate":
        return f"{v * 100:.0f}%"
    if k == "cgpa":
        return f"{v:.2f}"
    if k in ("faculty_rating", "satisfaction", "avg_mock_rating"):
        return "none yet" if (k == "avg_mock_rating" and row is not None and row["mock_interviews"] == 0) else f"{v:.1f} / 5"
    if k == "lms_avg":
        return f"{v:.1f}"
    if k == "momentum":
        return "falling" if v < -0.15 else ("rising" if v > 0.15 else "steady")
    if k == "eligible":
        return "Yes" if v >= 0.5 else "No"
    if k in ("best_aptitude", "best_coding", "technical_score", "soft_skill_score"):
        return f"{v:.0f} / 100"
    return f"{v:.0f}"


def fmt_avg(k, cohort):
    if k == "eligible":
        return f"{cohort[k].mean():.0%} are eligible"
    if k == "momentum":
        return fmt_value(k, cohort[k].mean())
    if k in ("backlogs", "mock_interviews", "activities", "certifications"):
        return f"{cohort[k].mean():.1f}"
    return fmt_value(k, cohort[k].mean())


PART = {"academic": "Academics", "engagement": "Engagement", "placement": "Placement readiness"}


def marksheet(row, meta):
    """The Success Score as a marksheet: marks earned per item, out of that item's maximum."""
    from src.scoring import normalise
    wt = meta["weight_table"][str(int(row["year"]))]
    n = normalise(row.to_frame().T.astype({k: float for k in wt})).iloc[0]
    rows = []
    for k, sub, lab, lo, hi, inv, *_ in INDICATORS:
        if k not in wt:
            continue
        out = 100 * wt[k]
        rows.append({"Part": PART[sub], "Item": FRIENDLY.get(k, lab), "This student": fmt_value(k, row[k], row),
                     "Zero marks at": scale_text(k, hi if inv else lo, "zero"),
                     "Full marks at": scale_text(k, lo if inv else hi, "full"),
                     "Marks": round(out * float(n[k]), 2), "Out of": round(out, 2)})
    return pd.DataFrame(rows)


FLOOR = {"faculty_rating", "satisfaction", "avg_mock_rating", "lms_avg", "activities", "mock_interviews", "certifications"}
CEILING = {"att_pct", "faculty_rating", "satisfaction", "avg_mock_rating", "asg_rate"}


def scale_text(k, v, end):
    """How an end of an item's marking scale reads, e.g. 'CGPA 5.0 or less' gets zero marks."""
    if k == "eligible":
        return "Yes" if v >= 0.5 else "No"
    if k == "momentum":
        return "falling fast" if v < 0 else "rising fast"
    if k == "backlogs":
        return "4 or more" if end == "zero" else "0"
    t = f"{v:.1f}" if k == "cgpa" else fmt_value(k, v)
    if end == "zero" and k not in FLOOR:
        return f"{t} or less"
    if end == "full" and k not in CEILING:
        return f"{t} or more"
    return t


def weekly_chart(cur, last, field, title, key, pct=False):
    fig = go.Figure()
    for p_, name, color, dash in [(last, "Last semester", ui.GREY, "dot"), (cur, "This semester", ui.CRIMSON, "solid")]:
        y = 100 * p_["classes_attended"] / p_["classes_held"] if field == "att" else p_[field]
        fig.add_trace(go.Scatter(x=p_["week"], y=y, name=name, mode="lines+markers",
                                 line=dict(color=color, width=2.5 if dash == "solid" else 2, dash=dash), marker=dict(size=6),
                                 hovertemplate=f"{name}, week %{{x}}: %{{y:.0f}}<extra></extra>"))
    fig.update_xaxes(tickprefix="Wk ", dtick=2, range=[0.5, 16.5])
    if pct:
        fig.update_yaxes(ticksuffix="%", range=[0, 105])
    st.markdown(f"**{title}**")
    ui.chart(ui.style(fig, 240), key=key)


def render():
    D = ui.data()
    S = ui.scoped(D["S"])
    M = ui.load_models()
    W = D["meta"]["current_week"]

    st.page_link(ui.PAGES["students"], label="Back to directory", icon=":material/arrow_back:")
    opts = list(S.sort_values("acad_prob", ascending=False).index)
    if st.session_state.get("profile_pick") not in opts:
        last = st.session_state.get("student")
        if last in opts:
            st.session_state["profile_pick"] = last
        else:
            silent = S[S["segment"] == "Silent Strugglers"].sort_values("acad_prob", ascending=False)
            st.session_state["profile_pick"] = silent.index[0] if len(silent) else opts[0]
    roll = st.selectbox("Find a student", opts, key="profile_pick", label_visibility="collapsed",
                        format_func=lambda r: f"{S.at[r, 'name']}  ({r}, {S.at[r, 'dept']} year {S.at[r, 'year']})")
    st.session_state["student"] = roll
    row = S.loc[roll].copy()

    # ------------------------------------------------------------ header card
    with st.container(border=True):
        a, b = st.columns([4, 1], vertical_alignment="center")
        pills = ui.risk_pill(row["acad_risk"]) + " " + ui.pill(SEG_NAME.get(row["segment"], row["segment"]), "grey")
        if row["year"] >= 3:
            pills += " " + ui.pill(f"Placement: {ui.RISK_WORD[row['placement_risk']]}",
                                   {"High": "high", "Medium": "med", "Low": "low"}.get(row["placement_risk"], "grey"))
        sec = "" if pd.isna(row["section"]) or str(row["section"]).strip() in ("", "-", "nan") \
            else f" • Section {row['section']}"
        a.markdown(f"<div style='display:flex;align-items:center;gap:16px'>{ui.avatar(row['name'], 72)}<div>"
                   f"<div style='font-size:1.5rem;font-weight:800;color:{ui.INK}'>{row['name']}</div>"
                   f"<div class='muted'>{roll} • {row['dept']} • Year {row['year']}{sec} • "
                   f"Mentor: {row['mentor']}</div><div style='margin-top:6px'>{pills}</div></div></div>",
                   unsafe_allow_html=True)
        b.markdown(ui.ring(row["success_score"]), unsafe_allow_html=True)

    tabs = st.tabs(["Overview", "Academic", "Attendance", "LMS", "Engagement", "Placement", "Skills", "Feedback",
                    "Action plan"])
    pnl = D["panel"][D["panel"]["roll_no"] == roll]
    cur, last = pnl[pnl["semester"] == C.CURRENT_SEM], pnl[pnl["semester"] == C.TEST_SEM]
    res = path_to_green(row, M)

    # ------------------------------------------------------------ overview
    with tabs[0]:
        c1, c2, c3 = st.columns([1, 1.15, 1.05], gap="medium")
        with c1.container(border=True):
            st.markdown("### Key information")
            items = [("🎓 CGPA", f"{row['cgpa']:.2f}"), ("📅 Attendance", f"{row['att_pct']:.0f}%"),
                     ("📚 Standing arrears", f"{row['backlogs']:.0f}"), ("💻 LMS logins / week", f"{row['lms_avg']:.1f}"),
                     ("📝 Assignments submitted", f"{row['asg_rate']:.0%}"),
                     ("🎯 Placement readiness", f"{row['placement']:.0f} / 100"),
                     ("📈 Chance of failing a subject", f"{min(row['acad_prob'], .99):.0%}")]
            st.markdown("".join(f"<div class='kv'><span>{k}</span><span>{v}</span></div>" for k, v in items),
                        unsafe_allow_html=True)
        with c2.container(border=True):
            sheet = marksheet(row, D["meta"])
            total = sheet["Marks"].sum()
            st.markdown(f"### How the score of {row['success_score']:.0f} is made")
            st.markdown("<div class='muted'>Like a marksheet out of 100. Each item has maximum marks; the student "
                        "earns marks depending on how good that item is.</div>", unsafe_allow_html=True)
            html = ""
            for part in ["Academics", "Engagement", "Placement readiness"]:
                g = sheet[sheet["Part"] == part]
                got, out = g["Marks"].sum(), g["Out of"].sum()
                html += (f"<div style='display:flex;justify-content:space-between;font-size:.92rem;margin-top:10px'>"
                         f"<b style='color:{ui.INK}'>{part}</b><span><b>{got:.1f}</b> / {out:.0f}</span></div>"
                         f"{ui.bar(100 * got / out if out else 0, ui.CRIMSON)}")
            html += (f"<div style='display:flex;justify-content:space-between;font-size:1rem;padding-top:8px;"
                     f"border-top:1px solid {ui.LINE}'><b style='color:{ui.INK}'>Success Score</b>"
                     f"<b style='color:{ui.CRIMSON}'>{total:.0f} / 100</b></div>")
            st.markdown(html, unsafe_allow_html=True)
            lost = sheet.assign(lost=sheet["Out of"] - sheet["Marks"]).sort_values("lost", ascending=False).head(3)
            st.markdown("<div style='margin-top:12px;font-weight:700;color:#c22b2b'>Most marks lost on</div>"
                        + "".join(f"<div class='kv'><span>{r['Item']} <span class='muted'>({r['This student']})</span></span>"
                                  f"<span>{r['Marks']:.1f} of {r['Out of']:.1f}</span></div>" for _, r in lost.iterrows()),
                        unsafe_allow_html=True)
            with st.expander("See the full marksheet"):
                st.dataframe(sheet[["Part", "Item", "This student", "Zero marks at", "Full marks at", "Marks", "Out of"]],
                             hide_index=True, height=420,
                             column_config={"Marks": st.column_config.NumberColumn(format="%.1f"),
                                            "Out of": st.column_config.NumberColumn(format="%.1f")})
                st.caption("Between 'zero marks' and 'full marks' the marks go up evenly. Example: CGPA 5.0 gets 0, "
                           "CGPA 9.5 gets full marks, and CGPA 7.25 (halfway) gets half.")
        with c3:
            reasons = row["acad_reasons"] or ["No strong academic warning signs this week."]
            steps = res["steps"][:2]
            st.markdown(f"<div class='insight'><div class='h'>⚠️ Why this student is flagged</div>"
                        + "".join(f"<div style='font-size:.9rem;margin:4px 0'>• {r}</div>" for r in reasons)
                        + (f"<div class='h' style='margin-top:10px'>Suggested first steps</div>"
                           + "".join(f"<div style='font-size:.88rem;margin:4px 0'>{i}. {s}</div>"
                                     for i, s in enumerate(steps, 1)) if steps else "")
                        + "</div>", unsafe_allow_html=True)
            if row["year"] >= 3 and row["placement_reasons"]:
                st.markdown("<div class='insight' style='margin-top:10px;background:#fff;border-color:#eceef3'>"
                            "<div class='h' style='color:#b65a0b'>Placement gaps</div>"
                            + "".join(f"<div style='font-size:.88rem;margin:4px 0'>• {r}</div>" for r in row["placement_reasons"])
                            + "</div>", unsafe_allow_html=True)
        st.write("")
        r1, r2 = st.columns([4, 1], vertical_alignment="center")
        first = res["steps"][0] if res["steps"] else "Keep doing what works; consider them as a peer mentor."
        r1.markdown(f"<div class='reco'><div class='h'>🎯 Recommended action</div>"
                    f"<div style='font-size:.92rem;color:{ui.TEXT}'>Mentor meeting this week. {first}</div></div>",
                    unsafe_allow_html=True)
        if r2.button("Create action plan", type="primary", use_container_width=True, key=f"cap_{roll}"):
            ui.log_actions([dict(week=W, roll_no=roll, name=row["name"], dept=row["dept"], action="Mentor meeting",
                                 owner=row["mentor"], note="; ".join(res["steps"][:3]), follow_up_week=min(W + 2, 16),
                                 status="Planned")])
            st.success("Action plan saved. Follow it up on the Interventions page; see the full plan in the Action plan tab.")

    # ------------------------------------------------------------ academic
    with tabs[1]:
        a, b = st.columns([1.4, 1], gap="medium")
        with a.container(border=True):
            st.markdown("### This semester's subjects")
            ex = D["exams"]
            ex = ex[(ex["roll_no"] == roll) & ex["grade"].isna()][["subject_code", "subject_name", "cia1", "cia1_absent"]]
            sa = D["subj_att"][D["subj_att"]["roll_no"] == roll][["subject_code", "attendance_pct"]]
            t = ex.merge(sa, on="subject_code", how="left")
            t["Internal test (CIA-1, out of 50)"] = np.where(t["cia1_absent"], "Absent",
                                                            t["cia1"].map(lambda x: "" if pd.isna(x) else f"{x:.0f}"))
            st.dataframe(t.rename(columns={"subject_name": "Subject", "attendance_pct": "Attendance"})
                         [["Subject", "Internal test (CIA-1, out of 50)", "Attendance"]], hide_index=True,
                         column_config={"Attendance": st.column_config.ProgressColumn("Attendance", min_value=0,
                                                                                      max_value=100, format="%d%%")})
        with b.container(border=True):
            st.markdown("### GPA by semester")
            sg = D["sgpa"][D["sgpa"]["roll_no"] == roll].sort_values("semester_no")
            fig = go.Figure(go.Bar(x=[f"Sem {int(s)}" for s in sg["semester_no"]], y=sg["sgpa"], marker_color=ui.CRIMSON,
                                   text=[f"{v:.1f}" + (f" ({int(a_)} RA)" if a_ else "") for v, a_ in zip(sg["sgpa"], sg["arrears"])],
                                   textposition="outside", textfont=dict(color=ui.TEXT), cliponaxis=False,
                                   hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
            fig.update_yaxes(range=[0, 10.5])
            ui.chart(ui.style(fig, 250, legend=False), key="p_gpa")
            st.caption(f"CGPA {row['cgpa']:.2f}, standing arrears {row['backlogs']:.0f}. RA = re-appear (failed).")

    # ------------------------------------------------------------ attendance
    with tabs[2]:
        a, b = st.columns([1.4, 1], gap="medium")
        with a.container(border=True):
            weekly_chart(cur, last, "att", "Attendance week by week", "p_att", pct=True)
        with b.container(border=True):
            st.markdown("### Exam eligibility")
            st.markdown("".join(f"<div class='kv'><span>{k}</span><span>{v}</span></div>" for k, v in [
                ("Attendance so far", f"{row['att_pct']:.0f}%"), ("Last 4 weeks", f"{row['att_recent']:.0f}%"),
                ("Projected at semester end", f"{row['projected_attendance']:.0f}%"),
                ("Needed to write exams", f"{C.ATTENDANCE_MIN:.0f}%")]), unsafe_allow_html=True)
            need = row["required_rate_for_75"]
            if row["projected_attendance"] >= C.ATTENDANCE_MIN:
                st.success("On track to stay eligible.")
            elif need <= 100:
                st.warning(f"Must attend at least {max(need, 0):.0f}% of the remaining classes to stay eligible.")
            else:
                st.error(f"Cannot reach 75% even with full attendance (best case {projected_attendance(row, 1.0):.0f}%). "
                         "Start the condonation or medical-leave process now.")

    # ------------------------------------------------------------ LMS
    with tabs[3]:
        a, b = st.columns(2, gap="medium")
        with a.container(border=True):
            weekly_chart(cur, last, "logins", "LMS logins per week", "p_lms")
        with b.container(border=True):
            weekly_chart(cur, last, "assignments_submitted", "Assignments submitted (of 2 a week)", "p_asg")
        st.caption(f"LMS activity changed {row['lms_change']:+.0%} over the last 3 weeks; assignment completion "
                   f"{row['asg_change'] * 100:+.0f} points.")

    # ------------------------------------------------------------ engagement
    with tabs[4]:
        a, b = st.columns([1, 1.4], gap="medium")
        with a.container(border=True):
            st.markdown("### Activity this year")
            st.markdown("".join(f"<div class='kv'><span>{k}</span><span>{v}</span></div>" for k, v in [
                ("Events and clubs", int(row["activities"])), ("Hackathons", int(row["hackathons"])),
                ("Certifications", int(row["certifications"])),
                ("Satisfaction (survey, 1 to 5)", "No response" if row["satisfaction_missing"] else f"{row['satisfaction']:.1f}"),
                ("Engagement score", f"{row['engagement']:.0f} / 100")]), unsafe_allow_html=True)
        with b.container(border=True):
            st.markdown("### Events attended")
            ev = D["events"][D["events"]["roll_no"] == roll].sort_values("event_month", ascending=False)
            if len(ev):
                st.dataframe(ev[["event_month", "event_type", "event_name"]].rename(columns={
                    "event_month": "Month", "event_type": "Type", "event_name": "Event"}), hide_index=True, height=240)
            else:
                st.info("No events recorded in the last 12 months.")

    # ------------------------------------------------------------ placement
    with tabs[5]:
        if row["year"] < 3:
            st.info("Placement readiness is tracked from 3rd year. Early indicators: "
                    f"aptitude {row['best_aptitude']:.0f}, technical skills {row['technical_score']:.0f}.")
        else:
            pa = D["meta"]["placement"]["placed_avg"]
            a, b = st.columns([1.3, 1], gap="medium")
            with a.container(border=True):
                st.markdown("### Compared with seniors who got placed")
                items = [("Aptitude", row["best_aptitude"], pa["best_aptitude"], 100),
                         ("Coding", row["best_coding"], pa["best_coding"], 100),
                         ("Soft skills", row["soft_skill_score"], pa["soft_skill_score"], 100),
                         ("Mock interviews", row["mock_interviews"], pa["mock_interviews"], 5)]
                fig = go.Figure()
                fig.add_trace(go.Bar(y=[i[0] for i in items], x=[100 * i[2] / i[3] for i in items], orientation="h",
                                     name="Placed seniors (average)", marker_color=ui.GREY,
                                     customdata=[i[2] for i in items], hovertemplate="%{y}: %{customdata:.1f}<extra></extra>"))
                fig.add_trace(go.Bar(y=[i[0] for i in items], x=[100 * i[1] / i[3] for i in items], orientation="h",
                                     name="This student", marker_color=ui.CRIMSON,
                                     customdata=[i[1] for i in items], hovertemplate="%{y}: %{customdata:.1f}<extra></extra>"))
                fig.update_layout(barmode="group")
                fig.update_xaxes(showticklabels=False, range=[0, 105])
                fig.update_yaxes(autorange="reversed")
                ui.chart(ui.style(fig, 260), key="p_place")
            with b.container(border=True):
                st.markdown("### Readiness")
                st.markdown("".join(f"<div class='kv'><span>{k}</span><span>{v}</span></div>" for k, v in [
                    ("Chance of getting placed", f"{row['placement_prob']:.0%}"),
                    ("Eligible for most recruiters", "Yes" if row["eligible"] else "No (CGPA or arrears)"),
                    ("Mock interviews done", int(row["mock_interviews"])),
                    ("Placement readiness score", f"{row['placement']:.0f} / 100")]), unsafe_allow_html=True)

    # ------------------------------------------------------------ skills
    with tabs[6]:
        with st.container(border=True):
            st.markdown("### Skills test results")
            for k, label in [("technical_score", "Technical skills"), ("soft_skill_score", "Soft skills"),
                             ("best_aptitude", "Aptitude"), ("best_coding", "Coding")]:
                if k == "best_coding" and row["year"] < 3:
                    continue
                v = row[k]
                missing = row.get(f"{k}_missing", False)
                st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:.9rem'><span>{label}</span>"
                            f"<b>{'Not tested' if missing else f'{v:.0f} / 100'}</b></div>"
                            f"{ui.bar(0 if missing else v, ui.BLUE)}", unsafe_allow_html=True)

    # ------------------------------------------------------------ feedback
    with tabs[7]:
        with st.container(border=True):
            st.markdown("### Faculty and student feedback")
            st.markdown("".join(f"<div class='kv'><span>{k}</span><span>{v}</span></div>" for k, v in [
                ("Faculty participation rating (1 to 5)", f"{row['faculty_rating']:.1f}"),
                ("Subjects rated 2 or below", int(row["low_rating_subjects"]) if not pd.isna(row["low_rating_subjects"]) else 0),
                ("Lowest faculty remark", row["faculty_remark"]),
                ("Student satisfaction (1 to 5)", "No response" if row["satisfaction_missing"] else f"{row['satisfaction']:.1f}"),
                ("Workload stress (1 to 5)", "No response" if pd.isna(row["stress"]) else f"{row['stress']:.0f}")]),
                unsafe_allow_html=True)

    # ------------------------------------------------------------ action plan
    with tabs[8]:
        s0, s1 = res["start"], res["end"]
        a, b = st.columns([1.5, 1], gap="medium")
        with a.container(border=True):
            st.markdown("### Path back on track")
            st.markdown("<div class='muted'>The smallest set of realistic changes, worked out with the same model "
                        "that flagged this student.</div>", unsafe_allow_html=True)
            st.write("")
            if row["projected_attendance"] < C.ATTENDANCE_MIN and row["required_rate_for_75"] > 100:
                st.error("Attendance cannot reach 75% this semester. Start the condonation process with the HOD now.")
            if not res["steps"]:
                st.success("Already on track. No changes needed.")
            for i, s in enumerate(res["steps"], 1):
                st.markdown(f"<div class='step'><b>Step {i}.</b> {s}</div>", unsafe_allow_html=True)
            if res["steps"] and res["reached"]:
                st.success("This plan brings the student back on track.")
            elif res["steps"] and s1["prob"] < C.RISK_MEDIUM:
                st.info("This plan removes the risk of failing. Placement goals need more time.")
            elif res["steps"]:
                st.warning("Even this plan does not remove the risk fully. Add counselling and remedial classes.")
        with b:
            st.markdown(ui.kpi("⭐", "#efe8fc", ui.PURPLE, "Success Score with the plan", f"{s0['score']:.0f} → {s1['score']:.0f}"),
                        unsafe_allow_html=True)
            st.write("")
            st.markdown(ui.kpi("🛡️", "#fde8e8", "#c22b2b", "Academic risk with the plan",
                               f"{level(s0['prob'])} → {level(s1['prob'])}", "",
                               f"chance of failing {min(s0['prob'], .99):.0%} → {min(s1['prob'], .99):.0%}",
                               "up" if s1["prob"] < s0["prob"] else "flat"), unsafe_allow_html=True)

        with st.expander("Try your own changes"):
            c = st.columns(3)
            rate = c[0].slider("Attend this % of remaining classes", 50, 100, int(min(100, max(50, row["att_recent"]))),
                               key=f"wi_att_{roll}")
            asg = c[1].slider("Assignments submitted (%)", 0, 100, int(row["asg_rate"] * 100), key=f"wi_asg_{roll}")
            lms = c[2].slider("LMS logins per week", 0.0, 10.0, float(min(10.0, round(row["lms_avg"] * 2) / 2)), 0.5,
                              key=f"wi_lms_{roll}")
            c = st.columns(3)
            arr = c[0].slider("Arrears cleared", 0, int(row["backlogs"]), 0, key=f"wi_arr_{roll}") if row["backlogs"] > 0 else 0
            mock = c[1].slider("Extra mock interviews", 0, 5, 0, key=f"wi_mock_{roll}") if row["year"] >= 3 else 0
            apt = c[2].slider("Aptitude score gain", 0, 30, 0, 5, key=f"wi_apt_{roll}")
            r2 = simulate(row, M, dict(attend_rate=rate / 100, asg_rate=asg / 100, lms_avg=lms, arrears_cleared=arr,
                                       mock_add=mock, aptitude_add=apt))
            k = st.columns(3 if row["year"] >= 3 else 2)
            k[0].metric("Success Score", f"{r2['score']:.0f}", f"{r2['score'] - s0['score']:+.0f}")
            k[1].metric("Chance of failing a subject", f"{min(r2['prob'], .99):.0%}",
                        f"{(r2['prob'] - s0['prob']) * 100:+.0f} pts", delta_color="inverse")
            if row["year"] >= 3:
                k[2].metric("Chance of getting placed", f"{r2['pprob']:.0%}", f"{(r2['pprob'] - s0['pprob']) * 100:+.0f} pts")

        with st.container(border=True):
            st.markdown("### Conversation guide for the mentor")
            facts = dict(department=row["dept"], year_of_study=int(row["year"]),
                         success_score=round(float(row["success_score"]), 1), band=row["band"],
                         academic_risk=row["acad_risk"], placement_risk=row["placement_risk"], segment=row["segment"],
                         risk_reasons=row["acad_reasons"], placement_reasons=row["placement_reasons"],
                         attendance_now=round(float(row["att_pct"]), 1),
                         projected_attendance=round(float(row["projected_attendance"]), 1),
                         declining=bool(row["lms_change"] <= -0.25 or row["asg_change"] <= -0.2),
                         faculty_remark=row["faculty_remark"], path_to_green=res["steps"])
            guide = st.session_state.get(f"brief_{roll}", ai.template_mentor_brief(facts))
            if ui.ai_key() and st.button("Write it with AI", icon="✨", key=f"mb_{roll}"):
                try:
                    guide = ai.call_gemini(ai.mentor_brief_prompt(facts), ui.ai_key(), ui.ai_model())
                    st.session_state[f"brief_{roll}"] = guide
                except ai.AIError as e:
                    st.info(f"The AI could not be reached, so this is the standard guide. ({e})")
            st.markdown(guide)

        with st.container(border=True):
            st.markdown("### Record what was done")
            with st.form(f"act_{roll}", clear_on_submit=True, border=False):
                f = st.columns([1.3, 1, 0.8])
                act = f[0].selectbox("Action", ["Mentor meeting", "Remedial classes", "Peer tutoring", "Counselling referral",
                                                "Parent call", "Mock interview drive", "Coding practice track", "Other"])
                owner = f[1].text_input("Who will do it", value=row["mentor"])
                fu = f[2].number_input("Follow up in week", min_value=W, max_value=C.WEEKS_PER_SEM,
                                       value=min(W + 2, C.WEEKS_PER_SEM))
                note = st.text_input("Note (optional)")
                if st.form_submit_button("Save action", type="primary"):
                    ui.log_actions([dict(week=W, roll_no=roll, name=row["name"], dept=row["dept"], action=act, owner=owner,
                                         note=note, follow_up_week=int(fu), status="Planned")])
                    st.success("Saved. Follow it up on the Interventions page.")
            hist = ui.read_actions()
            hist = hist[hist["roll_no"] == roll]
            if len(hist):
                st.dataframe(hist[["logged_at", "action", "owner", "status", "follow_up_week", "note"]].rename(columns={
                    "logged_at": "When", "action": "Action", "owner": "Owner", "status": "Status",
                    "follow_up_week": "Follow-up week", "note": "Note"}), hide_index=True)
