import streamlit as st
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

# Paths to Pickle Files
students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"
curriculums_cache = "pkl/curriculums.pkl"

def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

@st.cache_data(ttl=300)
def load_all_data():
    """Load all data with performance optimization"""
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Always coerce to DataFrame using pkl_data_to_df to avoid list objects
        futures = {
            'students': executor.submit(pkl_data_to_df, students_cache),
            'grades': executor.submit(pkl_data_to_df, grades_cache),
            'semesters': executor.submit(pkl_data_to_df, semesters_cache),
            'subjects': executor.submit(pkl_data_to_df, subjects_cache),
            'teachers': executor.submit(pkl_data_to_df, teachers_cache)
        }
        
        data = {}
        for key, future in futures.items():
            data[key] = future.result()
    
    load_time = time.time() - start_time
    st.success(f"📊 Data loaded in {load_time:.2f} seconds")
    
    # Log ingestion results
    log_data = {
        'timestamp': time.time(),
        'load_time_seconds': load_time,
        'records_loaded': {
            'students': len(data['students']),
            'grades': len(data['grades']),
            'semesters': len(data['semesters']),
            'subjects': len(data['subjects']),
            'teachers': len(data['teachers'])
        }
    }
    
    # Save log to cache directory
    os.makedirs('cache', exist_ok=True)
    with open('cache/ingestion_log.json', 'w') as f:
        json.dump(log_data, f, indent=2)
    
    return data

def get_incomplete_grades(data, filters):
    """Get students with incomplete grades (INC, Dropped, null)"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    teachers_df = data['teachers']

    if grades_df.empty:
        return pd.DataFrame()

    # Apply semester filter
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            grades_df = grades_df[grades_df["SemesterID"] == sem_id_arr[0]]

    # Apply faculty filter
    if filters.get("Faculty") != "All":
        teacher_id = teachers_df[teachers_df["Teacher"] == filters["Faculty"]]["_id"].values
        if len(teacher_id) > 0:
            grades_df = grades_df[grades_df["Teachers"].apply(lambda x: teacher_id[0] in x if isinstance(x, list) else x == teacher_id[0])]

    # Find incomplete grades
    def has_incomplete_grade(grades):
        if isinstance(grades, list):
            return any(g in ["INC", "Dropped", None] or pd.isna(g) for g in grades)
        return grades in ["INC", "Dropped", None] or pd.isna(grades)

    incomplete_df = grades_df[grades_df["Grades"].apply(has_incomplete_grade)].copy()

    if incomplete_df.empty:
        return pd.DataFrame()

    # Merge with students and other data
    result = incomplete_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")
    
    # Add semester info
    semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
    result["SemesterName"] = result["SemesterID"].map(semesters_dict)
    
    # Add teacher info
    teachers_dict = dict(zip(teachers_df["_id"], teachers_df["Teacher"]))
    result["TeacherName"] = result["Teachers"].apply(
        lambda x: teachers_dict.get(x[0] if isinstance(x, list) and x else x, "Unknown")
    )

    return result[["StudentID", "Name", "SubjectCodes", "Grades", "TeacherName", "SemesterName"]]

def show_registrar_tab4_info(data, students_df, semesters_df, teachers_df):
        st.subheader("⚠️ Incomplete Grades Report")
        st.markdown("Identify students with incomplete, dropped, or missing grades requiring attention")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
            semester = st.selectbox("Semester", semester_options, key="incomplete_semester")
        with col2:
            faculty_options = ["All"] + list(teachers_df["Teacher"].unique()) if not teachers_df.empty else ["All"]
            faculty = st.selectbox("Faculty", faculty_options, key="incomplete_faculty")
        
        if st.button("Apply Filters", key="incomplete_apply"):
            with st.spinner("Loading incomplete grades data..."):
                df = get_incomplete_grades(data, {"Semester": semester, "Faculty": faculty})
                
                if not df.empty:
                    # Summary statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_incomplete = len(df)
                        st.metric("Total Incomplete", f"{total_incomplete:,}")
                    with col2:
                        unique_students = df["StudentID"].nunique()
                        st.metric("Affected Students", f"{unique_students:,}")
                    with col3:
                        unique_subjects = df["SubjectCodes"].nunique()
                        st.metric("Affected Subjects", unique_subjects)
                    with col4:
                        unique_teachers = df["TeacherName"].nunique()
                        st.metric("Involved Faculty", unique_teachers)
                    
                    # Incomplete grades by type
                    def categorize_grade(grade):
                        if isinstance(grade, list):
                            for g in grade:
                                if g in ["INC", "Dropped", None] or pd.isna(g):
                                    return "Incomplete" if g == "INC" else "Dropped" if g == "Dropped" else "Missing"
                        elif grade in ["INC", "Dropped", None] or pd.isna(grade):
                            return "Incomplete" if grade == "INC" else "Dropped" if grade == "Dropped" else "Missing"
                        return "Other"
                    
                    df["GradeType"] = df["Grades"].apply(categorize_grade)
                    grade_type_counts = df["GradeType"].value_counts()
                    
                    # Pie chart for incomplete grade types
                    fig_pie = px.pie(
                        values=grade_type_counts.values,
                        names=grade_type_counts.index,
                        title="Distribution of Incomplete Grade Types",
                        color_discrete_map={
                            "Incomplete": "#FFA500",
                            "Dropped": "#DC143C",
                            "Missing": "#808080"
                        }
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Bar chart by faculty
                    faculty_counts = df["TeacherName"].value_counts().head(10)
                    fig_bar = px.bar(
                        x=faculty_counts.index,
                        y=faculty_counts.values,
                        title="Incomplete Grades by Faculty (Top 10)",
                        labels={"x": "Faculty", "y": "Number of Incomplete Grades"}
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                    # Detailed data table
                    st.subheader("Detailed Incomplete Grades Report")
                    display_df = df[["StudentID", "Name", "SubjectCodes", "Grades", "TeacherName", "SemesterName", "GradeType"]].copy()
                    st.dataframe(display_df, use_container_width=True)
                    
                    # Export options
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Export to Excel", key="export_incomplete_excel"):
                            filename = f"incomplete_grades_{semester}_{faculty}.xlsx"
                            export_to_excel(display_df, filename)
                            st.success(f"Exported to {filename}")
                    
                else:
                    st.success("✅ No incomplete grades found for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load incomplete grades data")
