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

def get_top_performers(data, filters):
    """Get top performers per program"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if grades_df.empty or students_df.empty:
        return pd.DataFrame()

    # Apply semester filter
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            grades_df = grades_df[grades_df["SemesterID"] == sem_id_arr[0]]

    # Calculate GPA for each student
    gpa_data = {}
    for _, grade_row in grades_df.iterrows():
        student_id = grade_row["StudentID"]
        grades = grade_row.get("Grades", [])
        
        if isinstance(grades, list) and grades:
            # Filter numeric grades
            numeric_grades = [g for g in grades if isinstance(g, (int, float)) and not pd.isna(g)]
            if numeric_grades:
                avg_gpa = sum(numeric_grades) / len(numeric_grades)
                if student_id in gpa_data:
                    gpa_data[student_id].append(avg_gpa)
                else:
                    gpa_data[student_id] = [avg_gpa]

    # Create results dataframe
    results = []
    for student_id, gpa_list in gpa_data.items():
        student_info = students_df[students_df["_id"] == student_id]
        if not student_info.empty:
            student = student_info.iloc[0]
            final_gpa = sum(gpa_list) / len(gpa_list)
            year_level = student["YearLevel"]
            if isinstance(year_level, list):
                year_level = year_level[0] if year_level else 0
            results.append({
                "Name": student["Name"],
                "Course": student["Course"],
                "YearLevel": year_level,
                "GPA": round(final_gpa, 2)
            })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    
    # Get top 10 per program
    top_performers = df.sort_values(by="GPA", ascending=False).groupby("Course").head(10)
    
    return top_performers


def show_registrar_new_tab11_info(data, students_df, semesters_df):
        st.subheader("🏆 Top Performers per Program")
        st.markdown("Identify and celebrate the highest achieving students across all programs")
        
        # Filters
        semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
        top_semester = st.selectbox("Semester (optional)", semester_options, key="top_semester_tab6")
        
        if st.button("Load Top Performers", key="top_apply_tab6"):
            with st.spinner("Loading top performers data..."):
                df = get_top_performers(data, {"Semester": top_semester})
                
                if not df.empty:
                    # === Summary statistics ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_performers = len(df)
                        st.metric("Total Top Performers", f"{total_performers:,}")
                    with col2:
                        avg_gpa = df["GPA"].mean()
                        st.metric("Average GPA", f"{avg_gpa:.2f}")
                    with col3:
                        max_gpa = df["GPA"].max()
                        st.metric("Highest GPA", f"{max_gpa:.2f}")
                    with col4:
                        unique_courses = df["Course"].nunique()
                        st.metric("Programs Represented", unique_courses)
                    
                    # === Leaderboard ===
                    st.subheader("🏅 Top Performers Leaderboard")
                    df_ranked = df.copy()
                    df_ranked["Rank"] = df_ranked.groupby("Course")["GPA"].rank(method="dense", ascending=False).astype(int)
                    df_ranked = df_ranked.sort_values(["Course", "Rank"])
                    
                    for course in df_ranked["Course"].unique():
                        course_data = df_ranked[df_ranked["Course"] == course].head(10)
                        st.subheader(f"📚 {course}")
                        display_data = course_data[["Rank", "Name", "YearLevel", "GPA"]].copy()
                        display_data.columns = ["Rank", "Student Name", "Year Level", "GPA"]
                        st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # === Charts ===
                    fig_box = px.box(
                        df, 
                        x="Course", 
                        y="GPA",
                        title="GPA Distribution by Program",
                        color="Course"
                    )
                    fig_box.update_layout(
                        xaxis_tickangle=-45,
                        xaxis_title="Program",
                        yaxis_title="GPA"
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
                    
                    fig_scatter = px.scatter(
                        df, 
                        x="YearLevel", 
                        y="GPA",
                        color="Course",
                        size="GPA",
                        title="Top Performers by Year Level and GPA",
                        hover_data=["Name", "Course", "GPA"]
                    )
                    fig_scatter.update_layout(
                        xaxis_title="Year Level",
                        yaxis_title="GPA"
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    # === Program comparison ===
                    program_stats = df.groupby("Course").agg({
                        "GPA": ["mean", "max", "count"]
                    }).round(2)
                    program_stats.columns = ["Average GPA", "Highest GPA", "Top Performers Count"]
                    program_stats = program_stats.sort_values("Average GPA", ascending=False)
                    
                    st.subheader("Program Performance Comparison")
                    st.dataframe(program_stats, use_container_width=True)

                else:
                    st.warning("No top performers data available")
        else:
            st.info("👆 Click 'Load Top Performers' to view top performing students")
