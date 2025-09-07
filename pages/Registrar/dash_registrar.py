import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import time
import json

# Paths to Pickle Files
students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"
curriculums_cache = "pkl/curriculums.pkl"

# Helper functions
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_pkl_data(cache_path):
    """Load data from pickle file if exists, else return empty DataFrame"""
    if os.path.exists(cache_path):
        try:
            data = pd.read_pickle(cache_path)
            # Convert list to DataFrame if needed
            if isinstance(data, list):
                return pd.DataFrame(data)
            return data
        except Exception as e:
            st.error(f"Error loading {cache_path}: {str(e)}")
            return pd.DataFrame()
    else:
        st.warning(f"⚠️ Cache file {cache_path} not found.")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_all_data():
    """Load all data with performance optimization"""
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            'students': executor.submit(load_pkl_data, students_cache),
            'grades': executor.submit(load_pkl_data, grades_cache),
            'semesters': executor.submit(load_pkl_data, semesters_cache),
            'subjects': executor.submit(load_pkl_data, subjects_cache),
            'teachers': executor.submit(load_pkl_data, teachers_cache)
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

# -------- Curriculum helpers --------
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

def get_academic_standing(data, filters):
    """Get academic standing data based on filters with proper GPA calculation"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']

    if students_df.empty or grades_df.empty:
        return pd.DataFrame()

    # Merge grades with students to get course information
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            sem_id_val = str(sem_id_arr[0])
            merged = merged[merged["SemesterID"].astype(str) == sem_id_val]

    if filters.get("SchoolYear") != "All":
        try:
            school_year_value = int(filters["SchoolYear"]) if isinstance(filters["SchoolYear"], str) else filters["SchoolYear"]
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"] == school_year_value]["_id"].astype(str).tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]
        except (ValueError, TypeError):
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"].astype(str) == str(filters["SchoolYear"])]["_id"].astype(str).tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]

    # Filter by Course
    if filters.get("Course") != "All" and not merged.empty:
        merged = merged[merged["Course"] == filters["Course"]]

    # Calculate GPA properly - handle both list and single values
    def calculate_gpa(grades):
        if isinstance(grades, list) and grades:
            # Filter out non-numeric values and calculate average
            numeric_grades = [g for g in grades if isinstance(g, (int, float)) and not pd.isna(g)]
            return sum(numeric_grades) / len(numeric_grades) if numeric_grades else 0
        elif isinstance(grades, (int, float)) and not pd.isna(grades):
            return grades
        return 0

    merged["GPA"] = merged["Grades"].apply(calculate_gpa)

    # Compute total units
    def count_units(grades):
        if isinstance(grades, list):
            return len([g for g in grades if isinstance(g, (int, float)) and not pd.isna(g)])
        return 1 if isinstance(grades, (int, float)) and not pd.isna(grades) else 0

    merged["TotalUnits"] = merged["Grades"].apply(count_units)

    # Add semester and school year information
    if not merged.empty:
        unique_sem_ids = merged["SemesterID"].unique()
        filtered_semesters = semesters_df[semesters_df["_id"].isin(unique_sem_ids)]
        
        semesters_dict = dict(zip(filtered_semesters["_id"], filtered_semesters["Semester"]))
        years_dict = dict(zip(filtered_semesters["_id"], filtered_semesters["SchoolYear"]))
        
        merged["Semester"] = merged["SemesterID"].map(semesters_dict)
        merged["SchoolYear"] = merged["SemesterID"].map(years_dict)
        
        # Add subject information
        if not subjects_df.empty:
            subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"]))
            merged["Subject"] = merged["SubjectCodes"].apply(
                lambda x: subjects_dict.get(x[0] if isinstance(x, list) and x else x, str(x))
            )
        else:
            merged["Subject"] = merged["SubjectCodes"].apply(
                lambda x: str(x[0] if isinstance(x, list) and x else x)
            )
    else:
        merged["Semester"] = ""
        merged["SchoolYear"] = ""
        merged["Subject"] = ""

    # Determine academic status with proper thresholds
    def get_academic_status(gpa: float) -> str:
        if gpa >= 90:
            return "Dean's List"
        elif gpa >= 75:
            return "Good Standing"
        else:
            return "Probation"

    merged["Status"] = merged["GPA"].apply(get_academic_status)

    # Ensure all required columns exist
    required_columns = ["Name", "Course", "GPA", "TotalUnits", "Status", "Semester", "SchoolYear", "Subject"]
    for col in required_columns:
        if col not in merged.columns:
            merged[col] = ""

    return merged[required_columns].drop_duplicates()

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
            results.append({
                "Name": student["Name"],
                "Course": student["Course"],
                "YearLevel": student["YearLevel"],
                "GPA": round(final_gpa, 2)
            })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    
    # Get top 10 per program
    top_performers = df.sort_values(by="GPA", ascending=False).groupby("Course").head(10)
    
    return top_performers

def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def export_to_pdf(df, filename):
    """Export DataFrame to PDF (placeholder)"""
    print(f"PDF export not implemented. Data: {df.head()}")

def show_registrar_dashboard_old():
    """Original dashboard implementation"""
    # st.markdown("# 📋 Registrar's Office Dashboard")
    # st.markdown("Comprehensive academic performance analytics and student management system")
    
    # Load all data with performance optimization
    with st.spinner("Loading data..."):
        data = load_all_data()
    
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']
    teachers_df = data['teachers']


    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Academic Standing", 
        "📈 Pass/Fail Distribution", 
        "📉 Enrollment Trends", 
        "⚠️ Incomplete Grades", 
        "🔄 Retention & Dropout", 
        "🏆 Top Performers"
    ])

    with tab1:
        st.subheader("📊 Student Academic Standing Report")
        st.markdown("View student academic performance with GPA calculations and standing classifications")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="academic_course")
        with col2:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("School Year", year_options, key="academic_year")
        with col3:
            if year != "All" and not semesters_df.empty:
                sems_by_year = semesters_df[semesters_df["SchoolYear"] == year]["Semester"].unique().tolist()
                semester_options = ["All"] + sems_by_year
            else:
                semester_options = ["All"] + (list(semesters_df["Semester"].unique()) if not semesters_df.empty else [])
            semester = st.selectbox("Semester", semester_options, key="academic_semester")

        if st.button("Apply Filters", key="academic_apply"):
            with st.spinner("Loading academic standing data..."):
                df = get_academic_standing(data, {"Semester": semester, "Course": course, "SchoolYear": year})
                if not df.empty:
                    # Display summary statistics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Students", len(df))
                    with col2:
                        deans_list = len(df[df["Status"] == "Dean's List"])
                        st.metric("Dean's List", deans_list)
                    with col3:
                        good_standing = len(df[df["Status"] == "Good Standing"])
                        st.metric("Good Standing", good_standing)
                    with col4:
                        probation = len(df[df["Status"] == "Probation"])
                        st.metric("Probation", probation)
                    
                    # Display data table
                    st.subheader("Academic Standing Data")
                    st.dataframe(df, use_container_width=True)
                    
                    # Status distribution pie chart
                    status_counts = df["Status"].value_counts()
                    fig_pie = px.pie(
                        values=status_counts.values, 
                        names=status_counts.index,
                        title="Academic Status Distribution",
                        color_discrete_map={
                            "Dean's List": "#2E8B57",
                            "Good Standing": "#4169E1", 
                            "Probation": "#DC143C"
                        }
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # GPA distribution histogram
                    fig_hist = px.histogram(
                        df, 
                        x="GPA", 
                        nbins=20,
                        title="GPA Distribution",
                        labels={"GPA": "Grade Point Average", "count": "Number of Students"}
                    )
                    fig_hist.add_vline(x=90, line_dash="dash", line_color="green", annotation_text="Dean's List (≥90)")
                    fig_hist.add_vline(x=75, line_dash="dash", line_color="blue", annotation_text="Good Standing (≥75)")
                    st.plotly_chart(fig_hist, use_container_width=True)
                    
                    # Top performers table
                    st.subheader("Top 15 Students (by GPA)")
                    top15 = df.nlargest(15, "GPA")[["Name", "Course", "GPA", "Status", "Semester", "SchoolYear"]]
                    st.dataframe(top15, use_container_width=True)
                    
                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load academic standing data")

    with tab2:
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
                    # Summary statistics
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
                    
                    # Pass/Fail distribution by subject
                    subject_summary = df.groupby(["Subject", "Status"]).size().unstack(fill_value=0)
                    
                    # Bar chart for pass/fail by subject
                    fig_bar = px.bar(
                        subject_summary.reset_index(), 
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
                    
                    # Stacked bar chart
                    fig_stacked = px.bar(
                        subject_summary.reset_index(), 
                        x="Subject", 
                        y=["Pass", "Fail"],
                        title="Pass/Fail Distribution by Subject (Stacked)",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"}
                    )
                    fig_stacked.update_layout(
                        xaxis_tickangle=-45,
                        yaxis_title="Number of Students",
                        xaxis_title="Subject"
                    )
                    st.plotly_chart(fig_stacked, use_container_width=True)
                    
                    # Overall pass/fail pie chart
                    status_counts = df["Status"].value_counts()
                    fig_pie = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Overall Pass/Fail Distribution",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                    # Detailed data table
                    st.subheader("Detailed Pass/Fail Data")
                    st.dataframe(df, use_container_width=True)
                    
                    # Summary table
                    st.subheader("Summary by Subject")
                    st.dataframe(subject_summary, use_container_width=True)
                    
                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load pass/fail distribution data")

    with tab3:
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
                df = get_enrollment_trends(data, {"Course": course})
                
                if not df.empty:
                    # Summary statistics
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
                    
                    # Line chart for enrollment trends
                    if yoy:
                        # Year-over-year analysis
                        fig_line = px.line(
                            df, 
                            x="Semester", 
                            y="Count", 
                            color="SchoolYear",
                            title="Enrollment Trends by School Year",
                            markers=True
                        )
                        fig_line.update_layout(
                            xaxis_tickangle=-45,
                            yaxis_title="Number of Students",
                            xaxis_title="Semester"
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                        
                        # Year-over-year data table
                        st.subheader("Year-over-Year Enrollment Data")
                        st.dataframe(df, use_container_width=True)
                    else:
                        # Overall enrollment trend
                        overall_enrollment = df.groupby("Semester")["Count"].sum().reset_index()
                        overall_enrollment = overall_enrollment.sort_values("Semester")
                        
                        fig_line = px.line(
                            overall_enrollment, 
                            x="Semester", 
                            y="Count",
                            title="Overall Enrollment Trends",
                            markers=True
                        )
                        fig_line.update_layout(
                            xaxis_tickangle=-45,
                            yaxis_title="Number of Students",
                            xaxis_title="Semester"
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                        
                        # Area chart for cumulative enrollment
                        overall_enrollment["Cumulative"] = overall_enrollment["Count"].cumsum()
                        fig_area = px.area(
                            overall_enrollment, 
                            x="Semester", 
                            y="Cumulative",
                            title="Cumulative Enrollment Over Time"
                        )
                        fig_area.update_layout(
                            xaxis_tickangle=-45,
                            yaxis_title="Cumulative Students",
                            xaxis_title="Semester"
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
                        fig_bar.update_layout(
                            xaxis_tickangle=-45,
                            yaxis_title="Number of Students",
                            xaxis_title="Semester"
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                        # Data table
                        st.subheader("Enrollment Data by Semester")
                        st.dataframe(overall_enrollment, use_container_width=True)
                    
                    # Course breakdown if not filtered
                    if course == "All":
                        course_breakdown = df.groupby("Course")["Count"].sum().reset_index().sort_values("Count", ascending=False)
                        
                        fig_pie = px.pie(
                            course_breakdown, 
                            values="Count", 
                            names="Course",
                            title="Enrollment Distribution by Course"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
                        st.subheader("Enrollment by Course")
                        st.dataframe(course_breakdown, use_container_width=True)
                    
                else:
                    st.warning("No enrollment data available")
        else:
            st.info("👆 Click 'Apply Filters' to load enrollment trends data")

    with tab4:
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

    with tab5:
        st.subheader("🔄 Retention and Dropout Rates")
        st.markdown("Analyze student retention and dropout patterns by year level and course")
        
        # Filters
        course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
        course = st.selectbox("Course", course_options, key="retention_course")
        
        if st.button("Apply Filters", key="retention_apply"):
            with st.spinner("Loading retention & dropout data..."):
                summary, year_level_summary = get_retention_dropout(data, {"Course": course})
                
                if not summary.empty:
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
                    
                    # Year level analysis
                    if not year_level_summary.empty:
                        # Pivot for better visualization
                        year_level_pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
                        
                        # Stacked bar chart by year level
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
                        
                        # Calculate retention rate by year level
                        year_level_pivot["Total"] = year_level_pivot["Retained"] + year_level_pivot["Dropped"]
                        year_level_pivot["Retention_Rate"] = (year_level_pivot["Retained"] / year_level_pivot["Total"] * 100).round(1)
                        
                        # Retention rate by year level
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

    with tab6:
        st.subheader("🏆 Top Performers per Program")
        st.markdown("Identify and celebrate the highest achieving students across all programs")
        
        # Filters
        semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
        top_semester = st.selectbox("Semester (optional)", semester_options, key="top_semester")
        
        if st.button("Load Top Performers", key="top_apply"):
            with st.spinner("Loading top performers data..."):
                df = get_top_performers(data, {"Semester": top_semester})
                
                if not df.empty:
                    # Summary statistics
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
                    
                    # Top performers leaderboard
                    st.subheader("🏅 Top Performers Leaderboard")
                    
                    # Add ranking
                    df_ranked = df.copy()
                    df_ranked["Rank"] = df_ranked.groupby("Course")["GPA"].rank(method="dense", ascending=False).astype(int)
                    df_ranked = df_ranked.sort_values(["Course", "Rank"])
                    
                    # Display top 10 per program
                    for course in df_ranked["Course"].unique():
                        course_data = df_ranked[df_ranked["Course"] == course].head(10)
                        st.subheader(f"📚 {course}")
                        
                        # Create a styled table
                        display_data = course_data[["Rank", "Name", "YearLevel", "GPA"]].copy()
                        display_data.columns = ["Rank", "Student Name", "Year Level", "GPA"]
                        st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # GPA distribution by program
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
                    
                    # Top performers scatter plot
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
                    
                    # Program comparison
                    program_stats = df.groupby("Course").agg({
                        "GPA": ["mean", "max", "count"]
                    }).round(2)
                    program_stats.columns = ["Average GPA", "Highest GPA", "Top Performers Count"]
                    program_stats = program_stats.sort_values("Average GPA", ascending=False)
                    
                    st.subheader("Program Performance Comparison")
                    st.dataframe(program_stats, use_container_width=True)
                    
                    # Export options
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Export to Excel", key="export_top_performers_excel"):
                            filename = f"top_performers_{top_semester}.xlsx"
                            export_to_excel(df_ranked, filename)
                            st.success(f"Exported to {filename}")
                    
                else:
                    st.warning("No top performers data available")
        else:
            st.info("👆 Click 'Load Top Performers' to view top performing students")

def show_registrar_dashboard_new():
    """Simplified dashboard implementation with 4 tabs only"""
    
    # Add version indicator
    st.info("🆕 **New Version** - Simplified with 4 essential tabs")
    
    # Load all data with performance optimization
    with st.spinner("Loading data..."):
        data = load_all_data()
    
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']
    teachers_df = data['teachers']

    # Main Dashboard Tabs - Only 4 tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Class List",          # People icon fits class roster
        "📝 Evaluation Sheet",    # Clipboard/notes for evaluations
        "📚 Curriculum Viewer",   # Books for curriculum
        "👨‍🏫 Teacher Analysis"   # Teacher icon for analysis
    ])

    with tab1:
        st.subheader("📊 Class List")
        st.markdown("View class list per Teacher, Subject, and Semester with performance metrics")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="academic_course_new")
        with col2:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("School Year", year_options, key="academic_year_new")
        with col3:
            if year != "All" and not semesters_df.empty:
                sems_by_year = semesters_df[semesters_df["SchoolYear"] == year]["Semester"].unique().tolist()
                semester_options = ["All"] + sems_by_year
            else:
                semester_options = ["All"] + (list(semesters_df["Semester"].unique()) if not semesters_df.empty else [])
            semester = st.selectbox("Semester", semester_options, key="academic_semester_new")

        if st.button("Apply Filters", key="academic_apply_new"):
            with st.spinner("Loading academic standing data..."):
                df = get_academic_standing(data, {"Semester": semester, "Course": course, "SchoolYear": year})
                if not df.empty:
                    # Display summary statistics
                    # col1, col2, col3, col4 = st.columns(4)
                    # with col1:
                    #     st.metric("Total Students", len(df))
                    # with col2:
                    #     deans_list = len(df[df["Status"] == "Dean's List"])
                    #     st.metric("Dean's List", deans_list)
                    # with col3:
                    #     good_standing = len(df[df["Status"] == "Good Standing"])
                    #     st.metric("Good Standing", good_standing)
                    # with col4:
                    #     probation = len(df[df["Status"] == "Probation"])
                    #     st.metric("Probation", probation)
                    st.markdown("**Summary Statistics**")
                    
                    # Display data table
                    # st.subheader("Academic Standing Data")
                    # st.dataframe(df, use_container_width=True)
                    
                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load academic standing data")
    with tab2:
        st.subheader("📝 Evaluation Sheet")
        st.info("Coming soon.")

    with tab3:
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

    with tab4:
        st.subheader("👨‍🏫 Teacher Analysis")
        st.info("Coming soon.")

def show_registrar_dashboard():
    """Main dashboard function with toggle between old and new implementations"""
    # Add toggle at the top left
    col1, col2 = st.columns([1, 3])
    with col1:
        use_new_version = st.toggle(
            "🆕 Toggle Dashboard Version", 
            value=True,  # Default to new version
            help="Toggle between the original dashboard and the enhanced version with improved features"
        ) 
    # Call the appropriate version based on toggle
    if use_new_version:
        show_registrar_dashboard_new()
    else:
        show_registrar_dashboard_old()

if __name__ == "__main__":
    show_registrar_dashboard()