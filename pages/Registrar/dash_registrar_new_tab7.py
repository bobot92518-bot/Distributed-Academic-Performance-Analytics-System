import streamlit as st
import streamlit.components.v1 as components
### Ensure we scroll back to the teacher evaluation section if hash is present
components.html(
    '<script>window.addEventListener("load", function(){ if(location.hash=="#teacher-eval-anchor"){ setTimeout(function(){ try{ document.getElementById("teacher-eval-anchor").scrollIntoView({behavior:"instant", block:"start"}); }catch(e){} }, 0); }});</script>',
    height=0,
)
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.pdf_helper import generate_pdf
import time
import json

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

def get_pass_fail_distribution(data, filters):
    """Get pass/fail distribution by subject"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']

    if grades_df.empty:
        return pd.DataFrame()

    # Merge with students for course filtering
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            merged = merged[merged["SemesterID"] == sem_id_arr[0]]

    if filters.get("SchoolYear") != "All":
        try:
            school_year_value = int(filters["SchoolYear"])
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"] == school_year_value]["_id"].tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].isin(sem_ids_by_year)]
        except (ValueError, TypeError):
            pass

    if filters.get("Course") != "All" and not merged.empty:
        merged = merged[merged["Course"] == filters["Course"]]

    # Calculate pass/fail for each grade entry
    def process_grades(grades, subject_codes):
        results = []
        if isinstance(grades, list) and isinstance(subject_codes, list):
            for i, grade in enumerate(grades):
                if i < len(subject_codes) and isinstance(grade, (int, float)) and not pd.isna(grade):
                    subject_code = subject_codes[i] if i < len(subject_codes) else "Unknown"
                    status = "Pass" if grade >= 75 else "Fail"
                    results.append({
                        'SubjectCode': subject_code,
                        'Grade': grade,
                        'Status': status
                    })
        return results

    # Expand grades into individual records
    expanded_data = []
    for _, row in merged.iterrows():
        grade_results = process_grades(row['Grades'], row['SubjectCodes'])
        for result in grade_results:
            expanded_data.append({
                'StudentID': row['StudentID'],
                'StudentName': row['Name'],
                'Course': row['Course'],
                'SubjectCode': result['SubjectCode'],
                'Grade': result['Grade'],
                'Status': result['Status']
            })

    if not expanded_data:
        return pd.DataFrame()

    df = pd.DataFrame(expanded_data)
    
    # Map subject codes to descriptions
    if not subjects_df.empty:
        subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"]))
        df['Subject'] = df['SubjectCode'].map(subjects_dict).fillna(df['SubjectCode'])
    else:
        df['Subject'] = df['SubjectCode']

    return df

def show_registrar_new_tab7_info(data, students_df, semesters_df):
        st.subheader("📈 Subject Pass/Fail Distribution")
        st.markdown("Analyze pass/fail rates by subject with detailed breakdowns and visualizations")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="passfail_course")
        with col2:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("School Year", year_options, key="passfail_year")
        with col3:
            if year != "All" and not semesters_df.empty:
                sems_by_year = semesters_df[semesters_df["SchoolYear"] == year]["Semester"].unique().tolist()
                semester_options = ["All"] + sems_by_year
            else:
                semester_options = ["All"] + (list(semesters_df["Semester"].unique()) if not semesters_df.empty else [])
            semester = st.selectbox("Semester", semester_options, key="passfail_semester")

        if st.button("Apply Filters", key="passfail_apply"):
            with st.spinner("Loading pass/fail distribution data..."):
                df = get_pass_fail_distribution(data, {"Semester": semester, "Course": course, "SchoolYear": year})

                if not df.empty:
                    # === Summary statistics ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_records = len(df)
                        st.metric("Total Records", f"{total_records:,}")
                    with col2:
                        pass_count = len(df[df["Status"] == "Pass"])
                        st.metric("Pass Count", f"{pass_count:,}")
                    with col3:
                        fail_count = len(df[df["Status"] == "Fail"])
                        st.metric("Fail Count", f"{fail_count:,}")
                    with col4:
                        pass_rate = (pass_count / total_records * 100) if total_records > 0 else 0
                        st.metric("Pass Rate", f"{pass_rate:.1f}%")

                    # === Pass/Fail distribution by subject (calculated summary) ===
                    subject_summary = df.groupby(["Subject", "Status"]).size().unstack(fill_value=0).reset_index()
                    subject_summary["Total"] = subject_summary["Pass"] + subject_summary["Fail"]
                    subject_summary["Pass Rate (%)"] = (subject_summary["Pass"] / subject_summary["Total"] * 100).round(2)
                    subject_summary["Fail Rate (%)"] = (subject_summary["Fail"] / subject_summary["Total"] * 100).round(2)
                    summary_table = subject_summary[["Subject", "Pass Rate (%)", "Fail Rate (%)"]]

                    # === Pass/Fail Rate Table ===
                    st.subheader("📊 Pass/Fail Rates by Subject")
                    st.dataframe(summary_table, use_container_width=True)

                    # === Bar Chart ===
                    fig_bar = px.bar(
                        subject_summary,
                        x="Subject",
                        y=["Pass", "Fail"],
                        title="Pass/Fail Distribution by Subject",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"},
                        barmode="group"
                    )
                    fig_bar.update_layout(
                        xaxis_tickangle=-45,
                        yaxis_title="Number of Students",
                        xaxis_title="Subject"
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                    # === Pie Chart ===
                    status_counts = df["Status"].value_counts()
                    fig_pie = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Overall Pass/Fail Distribution",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load pass/fail distribution data")
