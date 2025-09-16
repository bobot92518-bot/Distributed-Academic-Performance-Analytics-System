import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache

@st.cache_data(ttl=300)
def load_all_data_new():
    """Load all data using the new pickle files for students, grades, and subjects."""
    start_time = time.time()

    new_students_path = "pkl/new_students.pkl"
    new_grades_path = "pkl/new_grades.pkl"
    new_subjects_path = "pkl/new_subjects.pkl"
    new_teachers_path = "pkl/new_teachers.pkl"

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            'students': executor.submit(pkl_data_to_df, new_students_path),
            'grades': executor.submit(pkl_data_to_df, new_grades_path),
            'semesters': executor.submit(pkl_data_to_df, semesters_cache),
            'subjects': executor.submit(pkl_data_to_df, new_subjects_path),
            'teachers_new': executor.submit(pkl_data_to_df, new_teachers_path),
        }

        data = {}
        for key, future in futures.items():
            data[key] = future.result()

    # Choose teachers source: prefer new_teachers, else old, else infer
    teachers_new_df = data.get('teachers_new') if isinstance(data.get('teachers_new'), pd.DataFrame) else pd.DataFrame()
    teachers_old_df = data.get('teachers_old') if isinstance(data.get('teachers_old'), pd.DataFrame) else pd.DataFrame()
    teachers_df = pd.DataFrame()
    if not teachers_new_df.empty:
        teachers_df = teachers_new_df
    elif not teachers_old_df.empty:
        teachers_df = teachers_old_df
    else:
        # Infer from subjects or grades if possible
        subjects_df = data.get('subjects', pd.DataFrame())
        grades_df = data.get('grades', pd.DataFrame())
        inferred = pd.DataFrame()
        if 'Teacher' in subjects_df.columns:
            inferred = pd.DataFrame({
                'Teacher': subjects_df['Teacher'].dropna().unique().tolist()
            })
            inferred['_id'] = inferred['Teacher']
        elif 'Teachers' in grades_df.columns:
            # explode teachers from grades
            tmp = grades_df[['Teachers']].copy()
            tmp = tmp[tmp['Teachers'].notna()]
            tmp = tmp.explode('Teachers') if tmp['Teachers'].apply(lambda x: isinstance(x, list)).any() else tmp
            inferred = pd.DataFrame({'_id': tmp['Teachers'].dropna().astype(str).unique().tolist()})
            inferred['Teacher'] = inferred['_id']
        teachers_df = inferred

    data['teachers'] = teachers_df

    load_time = time.time() - start_time
    st.success(f"📊 Data (new) loaded in {load_time:.2f} seconds")

    # Log ingestion results
    log_data = {
        'timestamp': time.time(),
        'load_time_seconds': load_time,
        'records_loaded': {
            'students_new': len(data['students']),
            'grades_new': len(data['grades']),
            'semesters': len(data['semesters']),
            'subjects_new': len(data['subjects']),
            'teachers': len(data['teachers'])
        }
    }

    os.makedirs('cache', exist_ok=True)
    with open('cache/ingestion_log.json', 'w') as f:
        json.dump(log_data, f, indent=2)

    return data

@st.cache_data(ttl=300)
def load_curriculums_df():
    """Load curriculums from pickle and return a DataFrame with expected columns."""
    if not os.path.exists(curriculums_cache):
        return pd.DataFrame()
    data = pd.read_pickle(curriculums_cache)
    df = pd.DataFrame(data) if isinstance(data, list) else data
    for col in ["courseCode", "courseName", "curriculumYear", "subjects"]:
        if col not in df.columns:
            df[col] = None
    return df

def show_registrar_new_tab5_info(data, students_df, semesters_df, teachers_df):
        subjects_df = data['subjects']
        grades_df = data['grades']

        st.subheader("👨‍🏫 Teacher Evaluation (Pass/Fail per Teacher)")
        # Anchor to retain scroll position on this tab after re-runs
        st.markdown('<div id="teacher-eval-anchor"></div>', unsafe_allow_html=True)

        # Expand per-grade rows to include teacher association
        def _expand_teacher_rows(grade_row):
            rows = []
            grades_list = grade_row.get("Grades", [])
            subjects_list = grade_row.get("SubjectCodes", [])
            teachers_list = grade_row.get("Teachers", [])
            grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
            subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
            teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
            n = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
            for i in range(n):
                rows.append({
                    "StudentID": grade_row.get("StudentID"),
                    "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
                    "Grade": grades_list[i] if i < len(grades_list) else None,
                    "TeacherRaw": teachers_list[i] if i < len(teachers_list) else None,
                })
            return rows

        # Resolve teacher names whether TeacherRaw holds id or name
        teacher_id_to_name = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
        known_teacher_names = set(teachers_df["Teacher"].dropna().astype(str).tolist()) if not teachers_df.empty else set()

        def resolve_teacher_name(value):
            if pd.isna(value):
                return "Unknown"
            if value in teacher_id_to_name:
                return teacher_id_to_name[value]
            s = str(value)
            return s

        # Build expanded dataframe
        exp_rows = []
        for _, gr in grades_df.iterrows():
            exp_rows.extend(_expand_teacher_rows(gr))

        if not exp_rows:
            st.info("No grade records available.")
        else:
            df = pd.DataFrame(exp_rows)
            df["Teacher"] = df["TeacherRaw"].apply(resolve_teacher_name)
            df = df[pd.to_numeric(df["Grade"], errors="coerce").notna()].copy()
            df["Grade"] = pd.to_numeric(df["Grade"], errors="coerce")
            df["Status"] = df["Grade"].apply(lambda g: "Pass" if g >= 75 else "Fail")

            # Aggregate counts
            agg = df.groupby("Teacher")["Status"].value_counts().unstack(fill_value=0)
            if "Pass" not in agg.columns:
                agg["Pass"] = 0
            if "Fail" not in agg.columns:
                agg["Fail"] = 0
            agg["Total"] = agg["Pass"] + agg["Fail"]
            agg["Pass Rate (%)"] = (agg["Pass"] / agg["Total"].replace(0, pd.NA) * 100).round(1)
            summary = agg.reset_index().sort_values(["Pass Rate (%)", "Total", "Pass"], ascending=[False, False, False])

            st.subheader("Summary Table")
            st.dataframe(summary, use_container_width=True, hide_index=True)
            # Ensure we remain scrolled to this section after interactions
            components.html('<script>location.hash = "#teacher-eval-anchor";</script>', height=0)

            # Filter by teacher for detailed pass/fail analysis (no "All")
            teacher_filter_options = summary["Teacher"].astype(str).tolist()
            sel_teacher_for_detail = st.selectbox("Filter by Teacher for detailed analysis", teacher_filter_options, key="teacher_eval_filter")

            if sel_teacher_for_detail:
                df_t = df[df["Teacher"].astype(str) == sel_teacher_for_detail]
                if df_t.empty:
                    st.info("No records for the selected teacher.")
                else:
                    st.subheader(f"Detailed Pass/Fail for {sel_teacher_for_detail}")

                    # Overall metrics for this teacher
                    pass_count = int((df_t["Status"] == "Pass").sum())
                    fail_count = int((df_t["Status"] == "Fail").sum())
                    total_count = pass_count + fail_count
                    pass_rate = round(pass_count / total_count * 100, 1) if total_count > 0 else 0.0

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.metric("Pass", pass_count)
                    with c2:
                        st.metric("Fail", fail_count)
                    with c3:
                        st.metric("Total", total_count)
                    with c4:
                        st.metric("Pass Rate (%)", pass_rate)

                    # Per subject breakdown for this teacher
                    subj_break = df_t.groupby("SubjectCode")["Status"].value_counts().unstack(fill_value=0)
                    if "Pass" not in subj_break.columns:
                        subj_break["Pass"] = 0
                    if "Fail" not in subj_break.columns:
                        subj_break["Fail"] = 0
                    subj_break["Total"] = subj_break["Pass"] + subj_break["Fail"]
                    subj_break["Pass Rate (%)"] = (subj_break["Pass"] / subj_break["Total"].replace(0, pd.NA) * 100).round(1)
                    subj_break = subj_break.reset_index().sort_values(["Pass Rate (%)", "Total", "Pass"], ascending=[False, False, False])

                    st.markdown("### Per-Subject Breakdown")
                    st.dataframe(subj_break, use_container_width=True, hide_index=True)

                    # Chart for this teacher's per-subject pass rate (top 15 by volume)
                    plot_t = subj_break.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(15)
                    fig_t = px.bar(plot_t, x="SubjectCode", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title=f"Pass Rate by Subject - {sel_teacher_for_detail}")
                    fig_t.update_layout(xaxis_title="Subject", yaxis_title="Pass Rate (%)")
                    st.plotly_chart(fig_t, use_container_width=True)

            # Bar chart
            plot_df = summary.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(20)
            fig = px.bar(plot_df, x="Teacher", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title="Pass Rate by Teacher (Top 20 by Volume)")
            fig.update_layout(xaxis_title="Teacher", yaxis_title="Pass Rate (%)")
            st.plotly_chart(fig, use_container_width=True)
        