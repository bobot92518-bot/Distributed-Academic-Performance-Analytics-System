import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
import time
import json
from datetime import datetime
from pages.Registrar.dash_registrar_new_tab3_pdf import create_curriculum_pdf

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

def show_registrar_new_tab3_info(data, students_df, semesters_df, grades_df):
        st.subheader("📚 Curriculum Viewer")
        st.markdown("Browse curriculum details by program and year. Subjects are grouped by Year Level and Semester.")

        curr_df = load_curriculums_df()
        if curr_df.empty:
            st.warning("No curriculum data available.")
        else:
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                course_display = curr_df[["courseCode", "courseName"]].drop_duplicates()
                course_display["display"] = course_display["courseCode"].astype(str) + " - " + course_display["courseName"].astype(str)
                course_options = ["All"] + course_display["display"].tolist()
                selected_course = st.selectbox("Program", course_options, key="curr_prog")
            with col2:
                year_options = ["All"] + sorted(curr_df["curriculumYear"].dropna().astype(str).unique().tolist())
                selected_year = st.selectbox("Curriculum Year", year_options, key="curr_year")
            with col3:
                group_by_sem = st.checkbox("Group by Semester", value=True, key="curr_group_sem")

            # Apply filters
            filtered = curr_df.copy()
            if selected_course != "All":
                cc, cn = selected_course.split(" - ", 1)
                filtered = filtered[(filtered["courseCode"].astype(str) == cc) & (filtered["courseName"].astype(str) == cn)]
            if selected_year != "All":
                filtered = filtered[filtered["curriculumYear"].astype(str) == selected_year]

            if filtered.empty:
                st.info("No curriculum matched the selected filters.")
            else:
                # Iterate through matching curriculums
                for _, row in filtered.iterrows():
                    st.markdown(f"### {row.get('courseCode', '')} - {row.get('courseName', '')} ({row.get('curriculumYear', '')})")
                    subjects = row.get("subjects", []) or []
                    if not subjects:
                        st.info("No subjects found in this curriculum.")
                        st.markdown("---")
                        continue

                    subj_df = pd.DataFrame(subjects)
                    # Normalize expected columns
                    expected_cols = [
                        "subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"
                    ]
                    for c in expected_cols:
                        if c not in subj_df.columns:
                            subj_df[c] = None

                    # Display grouped by YearLevel (and Semester optionally)
                    if group_by_sem and "semester" in subj_df.columns:
                        group_cols = ["yearLevel", "semester"]
                    else:
                        group_cols = ["yearLevel"]

                    try:
                        grouped = subj_df.groupby(group_cols)
                    except Exception:
                        # Fallback if grouping fails due to types
                        subj_df["yearLevel"] = subj_df["yearLevel"].astype(str)
                        if "semester" in subj_df.columns:
                            subj_df["semester"] = subj_df["semester"].astype(str)
                        grouped = subj_df.groupby(group_cols)

                    total_units_overall = 0
                    for grp_key, grp in grouped:
                        if isinstance(grp_key, tuple):
                            title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                        else:
                            title = f"Year {grp_key}"
                        st.subheader(f"📘 {title}")

                        display_cols = [
                            "subjectCode", "subjectName", "lec", "lab", "units", "prerequisite"
                        ]
                        show_df = grp[display_cols].rename(columns={
                            "subjectCode": "Subject Code",
                            "subjectName": "Subject Name",
                            "lec": "Lec",
                            "lab": "Lab",
                            "units": "Units",
                            "prerequisite": "Prerequisite"
                        })
                        st.dataframe(show_df, use_container_width=True, hide_index=True)

                        # Totals
                        units_sum = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                        lec_sum = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                        lab_sum = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                        total_units_overall += units_sum

                        c1, c2, c3 = st.columns(3)
                        c1.metric("Total Units", f"{int(units_sum)}")
                        c2.metric("Total Lec Hours", f"{int(lec_sum)}")
                        c3.metric("Total Lab Hours", f"{int(lab_sum)}")
                        st.markdown("---")

                    st.success(f"Overall Units in Curriculum: {int(total_units_overall)}")
                    st.markdown("---")

                # PDF Download Button
                if st.button("📥 Generate Curriculum PDF", key="curriculum_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_buffer = create_curriculum_pdf(filtered, selected_course, selected_year, group_by_sem)
                        st.download_button(
                            label="📥 Download Curriculum PDF",
                            data=pdf_buffer,
                            file_name=f"curriculum_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    st.success("PDF generated successfully!")
