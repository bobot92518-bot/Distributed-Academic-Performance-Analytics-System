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
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, teachers_cache, curriculums_cache
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
# @st.cache_data(ttl=300)  # Cache for 5 minutes
# def load_pkl_data(cache_path):
#     """Load data from pickle file if exists, else return empty DataFrame"""
#     if os.path.exists(cache_path):
#         try:
#             data = pd.read_pickle(cache_path)
#             # Convert list to DataFrame if needed
#             if isinstance(data, list):
#                 return pd.DataFrame(data)
#             return data
#         except Exception as e:
#             st.error(f"Error loading {cache_path}: {str(e)}")
#             return pd.DataFrame()
#     else:
#         st.warning(f"⚠️ Cache file {cache_path} not found.")
#         return pd.DataFrame()

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

# New loader for updated pickle sources (only used by the NEW dashboard)
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
    """Simplified dashboard implementation with 5 tabs including teacher grade analysis"""
    
    # Add version indicator
    st.markdown("🆕New Version")
    
    # Load all data with performance optimization (NEW sources)
    with st.spinner("Loading data..."):
        data = load_all_data_new()
    
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']
    teachers_df = data['teachers']

    # Tabs navigation (like the old method)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 Class List",
        "📝 Evaluation Form (LO2)",
        "📚 Curriculum Viewer",
        "📈 Grades per Teacher (LO1)",
        "👨‍🏫 Teacher Analysis",
    ])

    with tab1:
        st.subheader("👩‍🏫 Class List per Teacher")
        st.markdown("Select a teacher, then pick a subject to see the class roster.")

        cc1, cc2 = st.columns(2)
        with cc1:
            cl_teacher_opts = teachers_df["Teacher"].dropna().unique().tolist() if not teachers_df.empty else []
            cl_teacher = st.selectbox("Teacher", cl_teacher_opts, key="cls1_teacher")
        with cc2:
            st.write("")

        # Build expanded roster for teacher and subject selection
        def _expand_rows_cls1(gr):
            out = []
            grades_list = gr.get("Grades", [])
            subjects_list = gr.get("SubjectCodes", [])
            teachers_list = gr.get("Teachers", [])
            grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
            subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
            teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
            n = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
            for i in range(n):
                out.append({
                    "StudentID": gr.get("StudentID"),
                    "SemesterID": gr.get("SemesterID"),
                    "TeacherID": teachers_list[i] if i < len(teachers_list) else None,
                    "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
                })
            return out

        # Merge necessary student info
        cl_merged = grades_df.merge(students_df[["_id", "Name", "Course", "YearLevel"]], left_on="StudentID", right_on="_id", how="left")

        # No term filters in Tab 1 (use all records for teacher/subject)

        # Expand rows
        cls_expanded = []
        for _, rr in cl_merged.iterrows():
            cls_expanded.extend(_expand_rows_cls1(rr))

        if not cls_expanded:
            st.info("No records found. Adjust filters above.")
        else:
            cl_df = pd.DataFrame(cls_expanded)
            # Maps
            tmap = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
            smap = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
            semmap = dict(zip(semesters_df["_id"], semesters_df["Semester"])) if not semesters_df.empty else {}
            name_map = dict(zip(students_df["_id"], students_df["Name"])) if not students_df.empty else {}
            course_map = dict(zip(students_df["_id"], students_df["Course"])) if not students_df.empty else {}
            year_map = dict(zip(students_df["_id"], students_df["YearLevel"])) if not students_df.empty else {}

            cl_df["Teacher"] = cl_df["TeacherID"].map(tmap).fillna(cl_df["TeacherID"].astype(str))
            cl_df["Subject"] = cl_df["SubjectCode"].map(smap).fillna(cl_df["SubjectCode"].astype(str))
            cl_df["Semester"] = cl_df["SemesterID"].map(semmap).fillna(cl_df["SemesterID"].astype(str))
            cl_df["StudentName"] = cl_df["StudentID"].map(name_map).fillna(cl_df["StudentID"].astype(str))
            cl_df["Course"] = cl_df["StudentID"].map(course_map)
            cl_df["YearLevel"] = cl_df["StudentID"].map(year_map)

            # Filter by teacher
            if cl_teacher != "All":
                cl_df = cl_df[cl_df["Teacher"] == cl_teacher]

            if cl_df.empty:
                st.info("No classes for the selected teacher.")
            else:
                # Subject radio under selected teacher
                subj_opts = sorted(cl_df["Subject"].dropna().unique().tolist())
                sel_subj = st.radio("Subject", subj_opts, horizontal=False, key="cls1_subject_radio") if subj_opts else None

                if not sel_subj:
                    st.info("Choose a subject to view the class list.")
                else:
                    df_class = cl_df[cl_df["Subject"] == sel_subj]
                    st.success(f"Found {df_class['StudentID'].nunique()} students for {sel_subj}.")
                    show_cols = ["StudentID", "StudentName", "Course", "YearLevel", "Semester"]
                    st.subheader("Students by Year Level and Semester")
                    for year_level in sorted(df_class["YearLevel"].dropna().unique().tolist()):
                        st.markdown(f"**Year Level: {year_level}**")
                        df_year = df_class[df_class["YearLevel"] == year_level]
                        for sem_name in sorted(df_year["Semester"].dropna().unique().tolist()):
                            st.markdown(f"- Semester: {sem_name}")
                            df_sem = df_year[df_year["Semester"] == sem_name]
                            st.dataframe(
                                df_sem[show_cols]
                                    .sort_values(["StudentName"]) 
                                    .reset_index(drop=True),
                                use_container_width=True
                            )

    with tab2:
        st.subheader("📋 Evaluation Form")
        st.markdown("Enter a student name to evaluate their enrollment eligibility for future subjects.")
        
        # Student dropdown (same as Tab 2)
        student_options = [] if students_df.empty else students_df[["_id", "Name", "Course", "YearLevel"]].copy()
        display_to_id = {}
        if not students_df.empty:
            student_options["display"] = student_options.apply(lambda r: f"{r['Name']} ({r['_id']}) - {r['Course']} - Year {r['YearLevel']}", axis=1)
            display_to_id = dict(zip(student_options["display"], student_options["_id"]))
            sel_student_display = st.selectbox("Student", ["-"] + student_options["display"].tolist(), key="eval_student_sel")
        else:
            sel_student_display = st.selectbox("Student", ["-"], key="eval_student_sel")
        
        # Year level filter
        # (Removed) Year level filter per request

        if sel_student_display and sel_student_display != "-":
            sel_student_id = display_to_id.get(sel_student_display)
            
            if not sel_student_id:
                st.warning("Could not identify selected student.")
                student_info = None
            else:
                student_row = students_df[students_df["_id"] == sel_student_id]
                if student_row.empty:
                    st.warning("Selected student record not found.")
                    student_info = None
                else:
                    student_info = student_row.iloc[0]
                    student_id = student_info.get('_id')
                    st.success(f"Selected student: {student_info.get('Name', 'Unknown')}")
                    
                    # Display student info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Student ID", student_info.get('_id', 'N/A'))
                    with col2:
                        st.metric("Name", student_info.get('Name', 'N/A'))
                    with col3:
                        st.metric("Year Level", student_info.get('YearLevel', 'N/A'))
                    
                    student_year = int(str(student_info.get('YearLevel', 1)).strip()) if str(student_info.get('YearLevel', 1)).strip().isdigit() else 1
                
                # Get student's grades and filter for passing grades
                student_grades = grades_df[grades_df["StudentID"] == student_id].copy()
                
                # Expand grades to individual subject records
                def expand_student_grades(grade_row):
                    results = []
                    grades_list = grade_row.get("Grades", [])
                    subjects_list = grade_row.get("SubjectCodes", [])
                    grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
                    subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
                    
                    for i, grade in enumerate(grades_list):
                        if i < len(subjects_list):
                            subject_code = subjects_list[i]
                            if isinstance(grade, (int, float)) and not pd.isna(grade) and grade >= 75:
                                results.append({
                                    "subject_code": subject_code,
                                    "grade": grade,
                                    "semester_id": grade_row.get("SemesterID")
                                })
                    return results
                
                completed_subjects = []
                for _, grade_row in student_grades.iterrows():
                    completed_subjects.extend(expand_student_grades(grade_row))
                
                # Get subject names from subjects_df
                subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
                for subj in completed_subjects:
                    subj["subject_name"] = subjects_dict.get(subj["subject_code"], subj["subject_code"])
                
                # Display completed subjects in curriculum format (like Tab 2)
                st.subheader("✅ Completed Subjects")
                
                if completed_subjects:
                    # Get curriculum data to organize completed subjects
                    curr_df = load_curriculums_df()
                    
                    if not curr_df.empty:
                        # Filter curriculum by student's course
                        student_course = student_info.get("Course", "")
                        filtered_curr = curr_df.copy()
                        if "courseCode" in curr_df.columns:
                            filtered_curr = curr_df[curr_df["courseCode"].astype(str) == str(student_course)]
                            if filtered_curr.empty and "courseName" in curr_df.columns:
                                filtered_curr = curr_df[curr_df["courseName"].astype(str).str.contains(str(student_course), case=False, na=False)]
                        
                        if filtered_curr.empty:
                            st.warning("No curriculum found for student's course. Showing all curriculums.")
                            filtered_curr = curr_df
                        
                        # Process each matching curriculum
                        for _, crow in filtered_curr.iterrows():
                            st.markdown(f"### {crow.get('courseCode', '')} - {crow.get('courseName', '')} ({crow.get('curriculumYear', '')})")
                            subjects = crow.get("subjects", []) or []
                            
                            if not subjects:
                                st.info("No subjects found in this curriculum.")
                                continue
                            
                            subj_df = pd.DataFrame(subjects)
                            # Ensure columns
                            for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                                if c not in subj_df.columns:
                                    subj_df[c] = None
                            
                            # Filter to completed subjects only
                            completed_codes = {subj["subject_code"] for subj in completed_subjects}
                            completed_subj_df = subj_df[subj_df["subjectCode"].astype(str).isin(completed_codes)].copy()
                            
                            if completed_subj_df.empty:
                                st.info("No completed subjects found in this curriculum.")
                                continue
                            
                            # Group by year level and semester
                            group_cols = ["yearLevel", "semester"] if "semester" in completed_subj_df.columns else ["yearLevel"]
                            try:
                                grouped = completed_subj_df.groupby(group_cols)
                            except Exception:
                                completed_subj_df["yearLevel"] = completed_subj_df["yearLevel"].astype(str)
                                if "semester" in completed_subj_df.columns:
                                    completed_subj_df["semester"] = completed_subj_df["semester"].astype(str)
                                grouped = completed_subj_df.groupby(group_cols)
                            
                            # Process each year/semester group
                            for grp_key, grp in grouped:
                                if isinstance(grp_key, tuple):
                                    title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                                else:
                                    title = f"Year {grp_key}"
                                st.subheader(f"📘 {title}")
                                
                                # Create display data for completed subjects
                                display_data = []
                                
                                for _, subject in grp.iterrows():
                                    subj_code = str(subject["subjectCode"])
                                    
                                    # Find the grade for this subject
                                    grade_display = ""
                                    for comp_subj in completed_subjects:
                                        if comp_subj["subject_code"] == subj_code:
                                            grade_display = f"{comp_subj['grade']}"
                                            break
                                    
                                    # Determine status based on grade
                                    try:
                                        grade_val = float(grade_display)
                                        if grade_val >= 90:
                                            status = "🏆 Excellent"
                                        elif grade_val >= 85:
                                            status = "✅ Very Good"
                                        elif grade_val >= 80:
                                            status = "✅ Good"
                                        elif grade_val >= 75:
                                            status = "✅ Passed"
                                        else:
                                            status = "❌ Failed"
                                    except (ValueError, TypeError):
                                        status = "✅ Passed"
                                    
                                    display_data.append({
                                        "Subject Code": subject["subjectCode"],
                                        "Subject Name": subject["subjectName"],
                                        "Units": subject["units"],
                                        "Lec": subject["lec"],
                                        "Lab": subject["lab"],
                                        "Grade": grade_display,
                                        "Status": status,
                                        "Prerequisite": subject["prerequisite"]
                                    })
                                
                                display_df = pd.DataFrame(display_data)
                                st.dataframe(display_df, use_container_width=True, hide_index=True)
                                
                                # Calculate totals for this semester
                                total_units = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                                total_lec = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                                total_lab = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                                
                                # Calculate average grade for this semester
                                semester_grades = []
                                for _, subject in grp.iterrows():
                                    subj_code = str(subject["subjectCode"])
                                    for comp_subj in completed_subjects:
                                        if comp_subj["subject_code"] == subj_code:
                                            try:
                                                semester_grades.append(float(comp_subj['grade']))
                                            except (ValueError, TypeError):
                                                pass
                                            break
                                
                                avg_grade = sum(semester_grades) / len(semester_grades) if semester_grades else 0
                                
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Total Units", f"{int(total_units)}")
                                with col2:
                                    st.metric("Total Lec Hours", f"{int(total_lec)}")
                                with col3:
                                    st.metric("Total Lab Hours", f"{int(total_lab)}")
                                with col4:
                                    st.metric("Average Grade", f"{avg_grade:.1f}")
                                
                                st.markdown("---")
                            
                            # Overall summary for completed subjects
                            st.subheader("📊 Completed Subjects Summary")
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Completed", len(completed_subj_df))
                            with col2:
                                all_grades = [float(comp_subj['grade']) for comp_subj in completed_subjects 
                                            if comp_subj["subject_code"] in completed_subj_df["subjectCode"].astype(str).tolist()]
                                overall_avg = sum(all_grades) / len(all_grades) if all_grades else 0
                                st.metric("Overall Average", f"{overall_avg:.1f}")
                            with col3:
                                excellent_count = len([g for g in all_grades if g >= 90])
                                st.metric("Excellent (≥90)", excellent_count)
                            with col4:
                                passed_count = len([g for g in all_grades if g >= 75])
                                st.metric("Passed (≥75)", passed_count)
                            
                            st.markdown("---")
                    else:
                        # Fallback: simple table if no curriculum data
                        completed_df = pd.DataFrame(completed_subjects)
                        display_completed = completed_df[["subject_code", "subject_name", "grade"]].copy()
                        display_completed.columns = ["Subject Code", "Subject Name", "Grade"]
                        st.dataframe(display_completed, use_container_width=True, hide_index=True)
                else:
                    st.info("No completed subjects found.")
                
                # Get curriculum data (same logic as Tab 2)
                curr_df = load_curriculums_df()
                
                if not curr_df.empty:
                    # Filter curriculum by student's course
                    student_course = student_info.get("Course", "")
                    filtered_curr = curr_df.copy()
                    if "courseCode" in curr_df.columns:
                        filtered_curr = curr_df[curr_df["courseCode"].astype(str) == str(student_course)]
                        if filtered_curr.empty and "courseName" in curr_df.columns:
                            filtered_curr = curr_df[curr_df["courseName"].astype(str).str.contains(str(student_course), case=False, na=False)]
                    
                    if filtered_curr.empty:
                        st.warning("No curriculum found for student's course. Showing all curriculums.")
                        filtered_curr = curr_df
                    
                    # Process each matching curriculum
                    for _, crow in filtered_curr.iterrows():
                        st.markdown(f"### {crow.get('courseCode', '')} - {crow.get('courseName', '')} ({crow.get('curriculumYear', '')})")
                        subjects = crow.get("subjects", []) or []
                        
                        if not subjects:
                            st.info("No subjects found in this curriculum.")
                            continue
                        
                        subj_df = pd.DataFrame(subjects)
                        # Ensure columns
                        for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                            if c not in subj_df.columns:
                                subj_df[c] = None
                        
                        # Filter to future subjects only (year_level > student's current year)
                        subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")
                        future_subj_df = subj_df[subj_df["_yl_num"] > student_year].copy()
                        
                        if future_subj_df.empty:
                            st.info("No future subjects found in this curriculum.")
                            continue
                        
                        # Group by year level and semester
                        group_cols = ["yearLevel", "semester"] if "semester" in future_subj_df.columns else ["yearLevel"]
                        try:
                            grouped = future_subj_df.groupby(group_cols)
                        except Exception:
                            future_subj_df["yearLevel"] = future_subj_df["yearLevel"].astype(str)
                            if "semester" in future_subj_df.columns:
                                future_subj_df["semester"] = future_subj_df["semester"].astype(str)
                            grouped = future_subj_df.groupby(group_cols)
                        
                        # Process each year/semester group
                        for grp_key, grp in grouped:
                            if isinstance(grp_key, tuple):
                                title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                            else:
                                title = f"Year {grp_key}"
                            st.subheader(f"📘 {title}")
                            
                            # Evaluate each subject in this group
                            display_data = []
                            completed_codes = {subj["subject_code"] for subj in completed_subjects}
                            
                            def parse_prereq(prereq):
                                if not prereq or prereq in ["None", "N/A", ""]:
                                    return []
                                if isinstance(prereq, list):
                                    return [str(x).strip() for x in prereq if str(x).strip()]
                                return [str(prereq).strip()]
                            
                            def normalize_subject_code(code):
                                """Normalize subject code by removing spaces and converting to uppercase"""
                                if not code:
                                    return ""
                                return str(code).replace(" ", "").upper()
                            
                            # Get current semester info for prerequisite checking
                            current_year = grp_key[0] if isinstance(grp_key, tuple) else grp_key
                            current_sem = grp_key[1] if isinstance(grp_key, tuple) and len(grp_key) > 1 else None
                            
                            # Determine previous semester for prerequisite checking
                            prev_year = current_year
                            prev_sem = None
                            
                            if current_sem == 2:
                                prev_sem = 1  # Same year, previous semester
                            elif current_sem == 1:
                                prev_year = current_year - 1
                                prev_sem = 2  # Previous year, second semester
                            else:
                                # Default: check all previous semesters
                                prev_year = current_year - 1
                                prev_sem = None
                            
                            # Get all completed subjects (with passing grades) for prerequisite checking
                            # This includes subjects from any previous year that the student has passed
                            completed_codes_with_grades = {}
                            for comp_subj in completed_subjects:
                                # Normalize the subject code for matching
                                normalized_code = normalize_subject_code(comp_subj["subject_code"])
                                completed_codes_with_grades[normalized_code] = comp_subj["grade"]
                            
                            # Create set of prerequisite-eligible subject codes (all completed subjects)
                            prereq_eligible_codes = set(completed_codes_with_grades.keys())
                            
                            for _, subject in grp.iterrows():
                                subj_code = str(subject["subjectCode"])
                                
                                # Check if already taken
                                if subj_code in completed_codes:
                                    status = "✅ Already Passed"
                                    grade_display = ""
                                    enroll = "No - Already Passed"
                                    # Find the grade
                                    for comp_subj in completed_subjects:
                                        if comp_subj["subject_code"] == subj_code:
                                            grade_display = f"({comp_subj['grade']})"
                                            break
                                else:
                                    # Check prerequisites against all completed subjects
                                    prerequisites = parse_prereq(subject.get("prerequisite", []))
                                    missing_prereqs = []
                                    met_prereqs = []
                                    
                                    for prereq in prerequisites:
                                        # Normalize prerequisite code for matching
                                        normalized_prereq = normalize_subject_code(prereq)
                                        if normalized_prereq in prereq_eligible_codes:
                                            # Prerequisite is completed, show the grade
                                            prereq_grade = completed_codes_with_grades.get(normalized_prereq, "N/A")
                                            met_prereqs.append(f"{prereq}({prereq_grade})")
                                        else:
                                            missing_prereqs.append(prereq)
                                    
                                    if not missing_prereqs:
                                        status = "📝 Ready to Enroll"
                                        grade_display = f"Prereqs: {', '.join(met_prereqs)}"
                                        enroll = "Yes - Prerequisites Met"
                                    else:
                                        status = "⚠️ Prerequisites Not Met"
                                        grade_display = f"Missing: {', '.join(missing_prereqs)}"
                                        enroll = "No - Missing Prerequisites"
                                
                                display_data.append({
                                    "Subject Code": subject["subjectCode"],
                                    "Subject Name": subject["subjectName"],
                                    "Units": subject["units"],
                                    "Lec": subject["lec"],
                                    "Lab": subject["lab"],
                                    "Status": status,
                                    "Grade": grade_display,
                                    "Enroll?": enroll,
                                    "Prerequisite": subject["prerequisite"]
                                })
                            
                            display_df = pd.DataFrame(display_data)
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            # Calculate totals for this semester
                            total_units = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                            total_lec = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                            total_lab = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                            
                            # Count enrollment recommendations
                            ready_to_enroll = len([d for d in display_data if d["Enroll?"].startswith("Yes")])
                            already_passed = len([d for d in display_data if "Already Passed" in d["Status"]])
                            missing_prereqs = len([d for d in display_data if "Prerequisites Not Met" in d["Status"]])
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Units", f"{int(total_units)}")
                            with col2:
                                st.metric("Ready to Enroll", ready_to_enroll)
                            with col3:
                                st.metric("Already Passed", already_passed)
                            with col4:
                                st.metric("Missing Prereqs", missing_prereqs)
                            
                            st.markdown("---")
                        
                        # Overall summary for this curriculum
                        st.subheader("📊 Overall Enrollment Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Completed Subjects", len(completed_subjects))
                        with col2:
                            st.metric("Future Subjects", len(future_subj_df))
                        with col3:
                            total_ready = len([d for d in display_data if d["Enroll?"].startswith("Yes")])
                            st.metric("Ready to Enroll", total_ready)
                        with col4:
                            total_missing = len([d for d in display_data if "Prerequisites Not Met" in d["Status"]])
                            st.metric("Missing Prereqs", total_missing)
                        
                        st.markdown("---")
                else:
                    st.warning("No curriculum data available.")
        else:
            st.info("Please enter a student name to begin evaluation.")

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
        st.subheader("📈 Student Grade Analytics (per Teacher)")
        st.markdown("Select a teacher, then choose a class to view analytics and students list.")

        # Prepare expanded dataframe once
        def _expand_rows(gr):
            rows = []
            grades_list = gr.get("Grades", [])
            subjects_list = gr.get("SubjectCodes", [])
            teachers_list = gr.get("Teachers", [])
            grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
            subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
            teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
            max_len = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
            for i in range(max_len):
                rows.append({
                    "StudentID": gr.get("StudentID"),
                    "SemesterID": gr.get("SemesterID"),
                    "Grade": grades_list[i] if i < len(grades_list) else None,
                    "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
                    "TeacherID": teachers_list[i] if i < len(teachers_list) else None,
                })
            return rows

        merged_base = grades_df.merge(students_df[["_id", "Name", "Course", "YearLevel"]], left_on="StudentID", right_on="_id", how="left")
        expanded_rows = []
        for _, rr in merged_base.iterrows():
            expanded_rows.extend(_expand_rows(rr))

        if not expanded_rows:
            st.warning("No grade records available.")
        else:
            df_exp = pd.DataFrame(expanded_rows)
            # Maps
            tmap = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
            smap = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
            semmap = dict(zip(semesters_df["_id"], semesters_df["Semester"])) if not semesters_df.empty else {}

            df_exp["Teacher"] = df_exp["TeacherID"].map(tmap).fillna(df_exp["TeacherID"].astype(str))
            df_exp["Subject"] = df_exp["SubjectCode"].map(smap).fillna(df_exp["SubjectCode"].astype(str))
            df_exp["Semester"] = df_exp["SemesterID"].map(semmap).fillna(df_exp["SemesterID"].astype(str))

            # Filter to valid numeric grades
            df_exp = df_exp[pd.to_numeric(df_exp["Grade"], errors="coerce").notna()].copy()
            df_exp["Grade"] = pd.to_numeric(df_exp["Grade"], errors="coerce")

            # Teacher selector (distinct)
            teacher_choices = sorted([t for t in df_exp["Teacher"].dropna().unique().tolist() if t is not None])
            sel_teacher = st.selectbox("Teacher", teacher_choices, key="tga_teacher_distinct") if teacher_choices else None

            if not sel_teacher:
                st.info("Select a teacher to view analytics.")
            else:
                df_t = df_exp[df_exp["Teacher"] == sel_teacher]
                if df_t.empty:
                    st.warning("No records for the selected teacher.")
                else:
                    # Build subject options under selected teacher
                    subject_options = sorted(df_t["Subject"].dropna().unique().tolist())
                    sel_subject = st.radio("Subject", subject_options, horizontal=False, key="tga_subject_radio") if subject_options else None

                    if not sel_subject:
                        st.info("Choose a subject to see analytics.")
                    else:
                        df_c = df_t[df_t["Subject"] == sel_subject]

                        if df_c.empty:
                            st.warning("No data for the selected class.")
                        else:
                            # Summary metrics table (mean, median, highest, lowest)
                            mean_g = df_c["Grade"].mean()
                            med_g = df_c["Grade"].median()
                            max_g = df_c["Grade"].max()
                            min_g = df_c["Grade"].min()
                            summary_df = pd.DataFrame([
                                {"Metric": "Mean", "Value": round(mean_g, 2)},
                                {"Metric": "Median", "Value": round(med_g, 2)},
                                {"Metric": "Highest", "Value": round(max_g, 2)},
                                {"Metric": "Lowest", "Value": round(min_g, 2)},
                            ])
                            st.subheader("Summary Statistics")
                            st.dataframe(summary_df, use_container_width=True, hide_index=True)

                            # Grade distribution (bar)
                            vc = df_c["Grade"].round(0).astype(int).value_counts().sort_index().reset_index()
                            vc.columns = ["Grade", "Count"]
                            fig_dist = px.bar(vc, x="Grade", y="Count", title="Grade Distribution (Rounded)")
                            fig_dist.update_layout(xaxis_title="Grade", yaxis_title="Students")
                            st.plotly_chart(fig_dist, use_container_width=True)

                            # Pass/Fail per class (bar)
                            df_c["Status"] = df_c["Grade"].apply(lambda g: "Pass" if g >= 75 else "Fail")
                            pf = df_c["Status"].value_counts().reindex(["Pass", "Fail"], fill_value=0).reset_index()
                            pf.columns = ["Status", "Count"]
                            fig_pf = px.bar(pf, x="Status", y="Count", title="Pass/Fail Counts")
                            fig_pf.update_layout(xaxis_title="Status", yaxis_title="Students")
                            st.plotly_chart(fig_pf, use_container_width=True)

                            # Students list with remarks (⭐ for pass, ❌ for fail)
                            # Join back details
                            name_map = dict(zip(students_df["_id"], students_df["Name"])) if not students_df.empty else {}
                            course_map = dict(zip(students_df["_id"], students_df["Course"])) if not students_df.empty else {}
                            year_map = dict(zip(students_df["_id"], students_df["YearLevel"])) if not students_df.empty else {}
                            df_c["StudentName"] = df_c["StudentID"].map(name_map).fillna(df_c["StudentID"].astype(str))
                            df_c["Course"] = df_c["StudentID"].map(course_map)
                            df_c["YearLevel"] = df_c["StudentID"].map(year_map)
                            df_c["Remark"] = df_c["Grade"].apply(lambda g: "⭐ Pass" if g >= 75 else "❌ Fail")
                            st.subheader("Students by Course and Year Level")
                            show_cols = ["StudentID", "StudentName", "Course", "YearLevel", "Remark"]
                            courses_in_class = [c for c in sorted(df_c["Course"].dropna().unique().tolist())]
                            for course_name in courses_in_class:
                                st.markdown(f"**Course: {course_name}**")
                                df_course = df_c[df_c["Course"] == course_name]
                                years = [y for y in sorted(df_course["YearLevel"].dropna().unique().tolist())]
                                for ylevel in years:
                                    st.markdown(f"- Year Level: {ylevel}")
                                    df_year = df_course[df_course["YearLevel"] == ylevel]
                                    st.dataframe(
                                        df_year[show_cols]
                                            .sort_values(["StudentName"], ascending=[True])
                                            .reset_index(drop=True),
                                        use_container_width=True
                                    )

    with tab5:
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