import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

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

def get_enrollment_trends(data, filters):
    """Get enrollment trends by semester and course"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if grades_df.empty or semesters_df.empty:
        return pd.DataFrame()

    # Merge grades with students and semesters
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")
    merged = merged.merge(semesters_df, left_on="SemesterID", right_on="_id", how="left")

    # Apply course filter
    if filters.get("Course") != "All":
        merged = merged[merged["Course"] == filters["Course"]]

    # Count students per semester and course
    enrollment = merged.groupby(['Semester', 'SchoolYear', 'Course']).size().reset_index(name='Count')
    enrollment = enrollment.sort_values(['SchoolYear', 'Semester'])

    return enrollment

def show_registrar_tab3_info(data, students_df, semesters_df):
    st.subheader("📉 Enrollment Trend Analysis")
    st.markdown("Track student enrollment patterns across semesters and courses")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
        course = st.selectbox("Course", course_options, key="enrollment_course")
    with col2:
        yoy = st.checkbox("Show Year-over-Year Analysis", value=False, key="enrollment_yoy")

    if st.button("Apply Filters", key="enrollment_apply"):
        with st.spinner("Loading enrollment trends data..."):
            # Get enrollment trends data
            students_df_local = data['students']
            grades_df_local = data['grades']
            semesters_df_local = data['semesters']

            if grades_df_local.empty or semesters_df_local.empty:
                df = pd.DataFrame()
            else:
                # Merge grades with students and semesters
                merged = grades_df_local.merge(students_df_local, left_on="StudentID", right_on="_id", how="left")
                merged = merged.merge(semesters_df_local, left_on="SemesterID", right_on="_id", how="left")

                # Apply course filter
                if course != "All":
                    merged = merged[merged["Course"] == course]

                # Count students per semester and course
                df = merged.groupby(['Semester', 'SchoolYear', 'Course']).size().reset_index(name='Count')
                df = df.sort_values(['SchoolYear', 'Semester'])

            if not df.empty:
                # === Summary statistics ===
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_enrollment = df["Count"].sum()
                    st.metric("Total Enrollment", f"{total_enrollment:,}")
                with col2:
                    avg_per_semester = df["Count"].mean()
                    st.metric("Avg per Semester", f"{avg_per_semester:.0f}")
                with col3:
                    max_enrollment = df["Count"].max()
                    st.metric("Peak Enrollment", f"{max_enrollment:,}")
                with col4:
                    unique_semesters = len(df["Semester"].unique())
                    st.metric("Semesters Tracked", unique_semesters)

                # === Charts and Tables ===
                if yoy:
                    # Year-over-year analysis
                    st.subheader("Year-over-Year Enrollment Data")
                    st.dataframe(df, use_container_width=True)

                    fig_line = px.line(
                        df,
                        x="Semester",
                        y="Count",
                        color="SchoolYear",
                        title="Enrollment Trends by School Year",
                        markers=True
                    )
                    fig_line.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    # Overall enrollment trend
                    overall_enrollment = df.groupby("Semester")["Count"].sum().reset_index()
                    overall_enrollment = overall_enrollment.sort_values("Semester")

                    # Data table
                    st.subheader("Enrollment Data by Semester")
                    st.dataframe(overall_enrollment, use_container_width=True)

                    fig_line = px.line(
                        overall_enrollment,
                        x="Semester",
                        y="Count",
                        title="Overall Enrollment Trends",
                        markers=True
                    )
                    fig_line.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_line, use_container_width=True)

                    # Area chart for cumulative enrollment
                    overall_enrollment["Cumulative"] = overall_enrollment["Count"].cumsum()
                    fig_area = px.area(
                        overall_enrollment,
                        x="Semester",
                        y="Cumulative",
                        title="Cumulative Enrollment Over Time"
                    )
                    st.plotly_chart(fig_area, use_container_width=True)

                    # Bar chart for semester comparison
                    fig_bar = px.bar(
                        overall_enrollment,
                        x="Semester",
                        y="Count",
                        title="Enrollment by Semester",
                        color="Count",
                        color_continuous_scale="Blues"
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)

                # Course breakdown
                if course == "All":
                    course_breakdown = df.groupby("Course")["Count"].sum().reset_index().sort_values("Count", ascending=False)

                    st.subheader("Enrollment by Course")
                    st.dataframe(course_breakdown, use_container_width=True)

                    fig_pie = px.pie(
                        course_breakdown,
                        values="Count",
                        names="Course",
                        title="Enrollment Distribution by Course"
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

            else:
                st.warning("No enrollment data available")
    else:
        st.info("👆 Click 'Apply Filters' to load enrollment trends data")
