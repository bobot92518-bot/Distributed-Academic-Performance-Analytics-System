import streamlit as st
import pandas as pd
import plotly.express as px
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

def get_retention_dropout(data, filters):
    """Get retention and dropout rates by year level (safe version with missing column handling)"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if students_df.empty or grades_df.empty or semesters_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Get latest semester
    latest_sem = semesters_df.sort_values(by=["SchoolYear", "Semester"], ascending=False).iloc[0]
    
    # Get active students (those with grades in latest semester)
    active_student_ids = set(grades_df[grades_df["SemesterID"] == latest_sem["_id"]]["StudentID"])
    
    # Apply course filter
    filtered_students = students_df.copy()
    if filters.get("Course") != "All":
        filtered_students = filtered_students[filtered_students["Course"] == filters["Course"]]

    # Ensure YearLevel is scalar
    filtered_students["YearLevel"] = filtered_students["YearLevel"].apply(
        lambda x: x[0] if isinstance(x, list) and x else x
    )

    # Determine status
    filtered_students["Status"] = filtered_students["_id"].apply(
        lambda sid: "Retained" if sid in active_student_ids else "Dropped"
    )
    
    # Summary by status
    summary = filtered_students["Status"].value_counts().reset_index()
    summary.columns = ["Status", "Count"]
    
    # Summary by year level
    year_level_summary = filtered_students.groupby(["YearLevel", "Status"]).size().reset_index(name="Count")
    
    # ✅ Ensure that pivot always has Retained/Dropped columns
    if not year_level_summary.empty:
        pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
        for col in ["Retained", "Dropped"]:
            if col not in pivot.columns:
                pivot[col] = 0
        year_level_summary = pivot.reset_index().melt(id_vars="YearLevel", value_vars=["Retained", "Dropped"],
                                                     var_name="Status", value_name="Count")
    return summary, year_level_summary

def show_registrar_new_tab10_info(data, students_df, semesters_df):
    st.subheader("🔄 Retention and Dropout Rates")
    st.markdown("Analyze student retention and dropout patterns by year level and course")
    
    # Filters
    course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
    course = st.selectbox("Course", course_options, key="retention_course")
    
    if st.button("Apply Filters", key="retention_apply"):
        with st.spinner("Loading retention & dropout data..."):
            summary, year_level_summary = get_retention_dropout(data, {"Course": course})
            
            if not summary.empty:
                charts = []  # Collect charts for PDF
                
                # Calculate retention rate
                total_students = summary["Count"].sum()
                retained_count = summary[summary["Status"] == "Retained"]["Count"].iloc[0] if "Retained" in summary["Status"].values else 0
                dropped_count = summary[summary["Status"] == "Dropped"]["Count"].iloc[0] if "Dropped" in summary["Status"].values else 0
                retention_rate = (retained_count / total_students * 100) if total_students > 0 else 0
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Students", f"{total_students:,}")
                with col2:
                    st.metric("Retained", f"{retained_count:,}")
                with col3:
                    st.metric("Dropped", f"{dropped_count:,}")
                with col4:
                    st.metric("Retention Rate", f"{retention_rate:.1f}%")
                
                # Overall pie chart
                fig_pie = px.pie(
                    values=summary["Count"].values,
                    names=summary["Status"].values,
                    title="Overall Retention vs Dropout",
                    color_discrete_map={"Retained": "#2E8B57", "Dropped": "#DC143C"}
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                charts.append(("Overall Retention vs Dropout", fig_pie))
                
                # Year level analysis
                if not year_level_summary.empty:
                    year_level_pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
                    for col in ["Retained", "Dropped"]:
                        if col not in year_level_pivot.columns:
                            year_level_pivot[col] = 0
                    year_level_pivot = year_level_pivot[["Retained", "Dropped"]]
                    
                    # Bar chart
                    fig_bar = px.bar(
                        year_level_pivot.reset_index(),
                        x="YearLevel",
                        y=["Retained", "Dropped"],
                        title="Retention by Year Level",
                        color_discrete_map={"Retained": "#2E8B57", "Dropped": "#DC143C"},
                        barmode="group"
                    )
                    fig_bar.update_layout(xaxis_title="Year Level", yaxis_title="Number of Students")
                    st.plotly_chart(fig_bar, use_container_width=True)
                    charts.append(("Retention by Year Level", fig_bar))
                    
                    # Retention Rate
                    year_level_pivot["Total"] = year_level_pivot["Retained"] + year_level_pivot["Dropped"]
                    year_level_pivot["Retention_Rate"] = np.where(
                        year_level_pivot["Total"] > 0,
                        (year_level_pivot["Retained"] / year_level_pivot["Total"] * 100).round(1),
                        0
                    )
                    
                    fig_line = px.line(
                        year_level_pivot.reset_index(),
                        x="YearLevel",
                        y="Retention_Rate",
                        title="Retention Rate by Year Level",
                        markers=True
                    )
                    fig_line.update_layout(
                        xaxis_title="Year Level",
                        yaxis_title="Retention Rate (%)",
                        yaxis=dict(range=[0, 100])
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
                    charts.append(("Retention Rate by Year Level", fig_line))
                    
                    # Data table
                    st.subheader("Retention Analysis by Year Level")
                    display_df = year_level_pivot[["Retained", "Dropped", "Total", "Retention_Rate"]].copy()
                    display_df.columns = ["Retained", "Dropped", "Total", "Retention Rate (%)"]
                    st.dataframe(display_df, use_container_width=True)
                
                # Overall summary table
                st.subheader("Overall Retention Summary")
                summary_display = summary.copy()
                summary_display["Percentage"] = (summary_display["Count"] / total_students * 100).round(1)
                summary_display.columns = ["Status", "Count", "Percentage (%)"]
                st.dataframe(summary_display, use_container_width=True)
                
            else:
                st.warning("No retention data available")
    else:
        st.info("👆 Click 'Apply Filters' to load retention & dropout data")
