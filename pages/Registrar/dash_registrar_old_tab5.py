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

def get_retention_dropout(data, filters):
    """Get retention and dropout rates by year level"""
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
    filtered_students["YearLevel"] = filtered_students["YearLevel"].apply(lambda x: x[0] if isinstance(x, list) and x else x)

    # Determine status
    filtered_students["Status"] = filtered_students["_id"].apply(
        lambda sid: "Retained" if sid in active_student_ids else "Dropped"
    )
    
    # Summary by status
    summary = filtered_students["Status"].value_counts().reset_index()
    summary.columns = ["Status", "Count"]
    
    # Summary by year level
    year_level_summary = filtered_students.groupby(["YearLevel", "Status"]).size().reset_index(name="Count")
    
    return summary, year_level_summary


def show_registrar_tab5_info(data, students_df, semesters_df):
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
                    
                    # Summary statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Students", f"{total_students:,}")
                    with col2:
                        st.metric("Retained", f"{retained_count:,}")
                    with col3:
                        st.metric("Dropped", f"{dropped_count:,}")
                    with col4:
                        st.metric("Retention Rate", f"{retention_rate:.1f}%")
                    
                    # Overall retention pie chart
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
                        
                        # Stacked bar chart
                        fig_bar = px.bar(
                            year_level_pivot.reset_index(),
                            x="YearLevel",
                            y=["Retained", "Dropped"],
                            title="Retention by Year Level",
                            color_discrete_map={"Retained": "#2E8B57", "Dropped": "#DC143C"},
                            barmode="group"
                        )
                        fig_bar.update_layout(
                            xaxis_title="Year Level",
                            yaxis_title="Number of Students"
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                        charts.append(("Retention by Year Level", fig_bar))
                        
                        # Retention rate by year level
                        year_level_pivot["Total"] = year_level_pivot["Retained"] + year_level_pivot["Dropped"]
                        year_level_pivot["Retention_Rate"] = (year_level_pivot["Retained"] / year_level_pivot["Total"] * 100).round(1)
                        
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
                        
                        # Year level data table
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
