import pandas as pd
import streamlit as st

from src import ui


def pct(x):
    return "-" if pd.isna(x) else f"{100 * x:.0f}%"


def render():
    D = ui.data()
    fair = D["meta"]["fairness"]
    ui.title("Fairness check",
              "Gender, hostel or day scholar, and first-graduate status are never used to flag anyone. "
              "We still check that flags don't fall unfairly on any group.")
    cols = st.columns(3, gap="large")
    for col, (label, d) in zip(cols, fair.items()):
        rows = pd.DataFrame(d["rows"])
        ok_risk = d["risk_ratio"] >= 0.8
        ok_acc = d["recall_gap"] <= 0.1
        ok_short = d["shortage_ratio"] >= 0.8
        with col.container(border=True):
            st.markdown(f"### {label}")
            st.markdown(f"{'✅' if ok_risk else '⚠️'} **High-risk flags:** "
                        + ", ".join(f"{g} {pct(v)}" for g, v in zip(rows["group"], rows["high_academic_risk"])))
            st.markdown(f"{'✅' if ok_acc else '⚠️'} **Accuracy:** the model catches failing students about equally "
                        f"well in each group (gap {d['recall_gap'] * 100:.0f} points).")
            st.markdown(f"{'✅' if ok_short else '⚠️'} **Attendance shortage:** "
                        + ", ".join(f"{g} {pct(v)}" for g, v in zip(rows["group"], rows["attendance_shortage"])))
    st.write("")
    res = fair.get("Residence", {})
    if res and res.get("shortage_ratio", 1) < 0.8 and res.get("recall_gap", 1) <= 0.1:
        st.info("**Finding:** day scholars head for attendance shortage noticeably more often than hostellers, while the "
                "model is equally accurate for both. That points to travel (bus timings, first-hour classes), so the fix "
                "is a timetable or transport change, not stricter attendance warnings.")
    with st.expander("See the full numbers"):
        for label, d in fair.items():
            rows = pd.DataFrame(d["rows"])
            st.markdown(f"**{label}**")
            st.dataframe(pd.DataFrame({
                "Group": rows["group"], "Students": rows["students"], "Average score": rows["avg_success_score"].round(1),
                "High academic risk": rows["high_academic_risk"].map(pct),
                "Attendance shortage": rows["attendance_shortage"].map(pct),
                "Not placement-ready (Y3-4)": rows["high_placement_risk"].map(pct),
                "Failing students caught (past test)": rows["backtest_recall"].map(pct),
                "False alarms (past test)": rows["backtest_false_alarm"].map(pct)}), hide_index=True)
