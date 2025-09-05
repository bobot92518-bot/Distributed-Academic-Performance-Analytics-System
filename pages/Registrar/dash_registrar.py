import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt

# Paths to Pickle Files
students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"



# Helper functions
@st.cache_data
def load_pkl_data(cache_path):
    """Load data from pickle file if exists, else return empty list"""
    if os.path.exists(cache_path):
        return pd.read_pickle(cache_path)
    else:
        print(f"⚠️ Cache file {cache_path} not found.")
        return []

def get_academic_standing(filters):
    """Get academic standing data based on filters"""
    students_df = pd.DataFrame(load_pkl_data(students_cache))
    grades_df = pd.DataFrame(load_pkl_data(grades_cache))
    semesters_df = pd.DataFrame(load_pkl_data(semesters_cache))
    subjects_df = pd.DataFrame(load_pkl_data(subjects_cache))

    if students_df.empty or grades_df.empty:
        return pd.DataFrame()
    
    # Debug: Print filter values
    print(f"🔍 Filters received: {filters}")
    print(f"📊 Available semesters: {semesters_df['Semester'].unique() if not semesters_df.empty else 'None'}")
    print(f"📊 Available school years: {semesters_df['SchoolYear'].unique() if not semesters_df.empty else 'None'}")

    # Merge grades with students to get course information
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            sem_id_val = str(sem_id_arr[0])
            merged = merged[merged["SemesterID"].astype(str) == sem_id_val]

    if filters.get("SchoolYear") != "All":
        # Debug: Print school year filtering info
        print(f"🔍 School Year filter: {filters['SchoolYear']} (type: {type(filters['SchoolYear'])})")
        
        # Handle SchoolYear filtering - convert to int if it's a string
        try:
            school_year_value = int(filters["SchoolYear"]) if isinstance(filters["SchoolYear"], str) else filters["SchoolYear"]
            print(f"🔍 Converted school year value: {school_year_value}")
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"] == school_year_value]["_id"].astype(str).tolist()
            print(f"🔍 Found semester IDs for year {school_year_value}: {sem_ids_by_year}")
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]
                print(f"📊 Records after school year filtering: {len(merged)}")
            else:
                print(f"⚠️ No semesters found for school year {school_year_value}")
        except (ValueError, TypeError) as e:
            print(f"⚠️ Error converting school year: {e}")
            # If conversion fails, try string comparison
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"].astype(str) == str(filters["SchoolYear"])]["_id"].astype(str).tolist()
            print(f"🔍 Found semester IDs (string comparison): {sem_ids_by_year}")
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]
                print(f"📊 Records after school year filtering (string): {len(merged)}")
            else:
                print(f"⚠️ No semesters found for school year {filters['SchoolYear']} (string comparison)")

    # Filter by Course (from students collection)
    if filters.get("Course") != "All" and not merged.empty:
        print(f"🔍 Course filter: {filters['Course']}")
        print(f"📊 Available courses: {students_df['Course'].unique() if not students_df.empty else 'None'}")
        merged = merged[merged["Course"] == filters["Course"]]
        print(f"📊 Records after course filtering: {len(merged)}")


    # Calculate GPA
    merged["GPA"] = merged["Grades"].apply(lambda x: sum(x)/len(x) if isinstance(x, list) and x else 0)

    # Compute total units as number of graded entries (fallback if explicit units are unavailable)
    merged["TotalUnits"] = merged["Grades"].apply(lambda x: len(x) if isinstance(x, list) else (1 if pd.notna(x) else 0))

    # Add semester and school year information based on filtered data
    if not merged.empty:
        # Get unique semester IDs from the filtered data
        unique_sem_ids = merged["SemesterID"].unique()
        filtered_semesters = semesters_df[semesters_df["_id"].isin(unique_sem_ids)]
        
        # Create mapping dictionaries from filtered semester data
        semesters_dict = dict(zip(filtered_semesters["_id"], filtered_semesters["Semester"]))
        years_dict = dict(zip(filtered_semesters["_id"], filtered_semesters["SchoolYear"]))
        
        merged["Semester"] = merged["SemesterID"].map(semesters_dict)
        merged["SchoolYear"] = merged["SemesterID"].map(years_dict)
        
        # Add subject information
        if not subjects_df.empty:
            # Create subject mapping dictionary
            subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"]))
            # Map SubjectCodes to subject names
            merged["Subject"] = merged["SubjectCodes"].apply(
                lambda x: subjects_dict.get(x[0] if isinstance(x, list) and x else x, str(x))
            )
        else:
            merged["Subject"] = merged["SubjectCodes"].apply(
                lambda x: str(x[0] if isinstance(x, list) and x else x)
            )
    else:
        # If no data, create empty columns to avoid index errors
        merged["Semester"] = ""
        merged["SchoolYear"] = ""
        merged["Subject"] = ""

    # Determine academic status with Dean's List
    def _academic_status(gpa: float) -> str:
        if gpa >= 90:
            return "Dean's List"
        if gpa >= 75:
            return "Good Standing"
        return "Probation"

    merged["Status"] = merged["GPA"].apply(_academic_status)

    # Ensure all required columns exist before returning
    required_columns = ["Name", "Course", "GPA", "TotalUnits", "Status", "Semester", "SchoolYear", "Subject"]
    for col in required_columns:
        if col not in merged.columns:
            merged[col] = ""

    return merged[required_columns].drop_duplicates()

def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def export_to_pdf(df, filename):
    """Export DataFrame to PDF (placeholder)"""
    # For simplicity, just print
    print(f"PDF export not implemented. Data: {df.head()}")

def show_registrar_dashboard():
    # st.markdown("## 📋 Registrar Dashboard")
    # st.write("Welcome to the Registrar Dashboard. Here you can manage student enrollment, records, and more.")

    # Load data only when needed
    if 'students_df' not in st.session_state:
        st.session_state.students_df = pd.DataFrame(load_pkl_data(students_cache))
    if 'grades_df' not in st.session_state:
        st.session_state.grades_df = pd.DataFrame(load_pkl_data(grades_cache))
    if 'semesters_df' not in st.session_state:
        st.session_state.semesters_df = pd.DataFrame(load_pkl_data(semesters_cache))
    if 'subjects_df' not in st.session_state:
        st.session_state.subjects_df = pd.DataFrame(load_pkl_data(subjects_cache))
    if 'teachers_df' not in st.session_state:
        st.session_state.teachers_df = pd.DataFrame(load_pkl_data(teachers_cache))
    
    students_df = st.session_state.students_df
    grades_df = st.session_state.grades_df
    semesters_df = st.session_state.semesters_df
    subjects_df = st.session_state.subjects_df
    teachers_df = st.session_state.teachers_df

    # # KPIs
    # col1, col2, col3 = st.columns(3)
    # with col1:
    #     total_students = len(students_df) if not students_df.empty else 0
    #     st.metric("Total Students", total_students)
    # with col2:
    #     if not grades_df.empty:
    #         gpa_map = {}
    #         for _, g in grades_df.iterrows():
    #             sid = g["StudentID"]
    #             grade_list = g.get("Grades", [])
    #             if isinstance(grade_list, list) and grade_list:
    #                 avg = sum(grade_list) / len(grade_list)
    #                 gpa_map.setdefault(sid, []).append(avg)
    #         final_gpas = [sum(gpas) / len(gpas) for gpas in gpa_map.values()]
    #         avg_gpa = sum(final_gpas) / len(final_gpas) if final_gpas else 0
    #     else:
    #         avg_gpa = 0
    #     st.metric("Average GPA", f"{avg_gpa:.2f}")
    # with col3:
    #     if not semesters_df.empty and not grades_df.empty:
    #         latest_sem = semesters_df.sort_values(by=["SchoolYear", "Semester"], ascending=False).iloc[0]
    #         retained_ids = set(grades_df[grades_df["SemesterID"] == latest_sem["_id"]]["StudentID"])
    #         retained = sum(1 for _, s in students_df.iterrows() if s["_id"] in retained_ids)
    #         retention_rate = (retained / total_students) * 100 if total_students else 0
    #     else:
    #         retention_rate = 0
    #     st.metric("Retention Rate", f"{retention_rate:.1f}%")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Academic Standing", "Pass/Fail Distribution", "Enrollment Trends", "Incomplete Grades", "Retention & Dropout", "Top Performers", "Updates"])

    with tab1:
        st.subheader("Academic Standing")
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
                df = get_academic_standing({"Semester": semester, "Course": course, "SchoolYear": year})
                if not df.empty:
                    st.dataframe(df)

                    # Top 15 students (per current filters)
                    st.subheader("Top 15 Students (by GPA)")
                    top15_source = df[["Name", "Course", "GPA", "Semester", "SchoolYear"]].copy()
                    # Aggregate in case multiple rows per student remain after filtering
                    top15_agg = (top15_source
                        .groupby(["Name", "Course", "Semester", "SchoolYear"], as_index=False)["GPA"].mean())
                    top15 = top15_agg.sort_values(by="GPA", ascending=False).head(15)
                    st.dataframe(top15)
                    
                    # Create subplots for different views
                    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
                    
                    # Scatter plot for individual GPAs
                    ax1.scatter(range(len(df)), df["GPA"], alpha=0.6, s=30)
                    ax1.set_title("Individual Student GPAs")
                    ax1.set_xlabel("Student Index")
                    ax1.set_ylabel("GPA")
                    ax1.grid(True, alpha=0.3)
                    
                    # Box plot for distribution summary
                    ax2.boxplot(df["GPA"])
                    ax2.set_title("GPA Distribution Summary")
                    ax2.set_ylabel("GPA")
                    ax2.grid(True, alpha=0.3)
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                else:
                    st.write("No data available")
        else:
            st.info("👆 Click 'Apply Filters' to load academic standing data")

    with tab2:
        st.subheader("Pass/Fail Distribution")
        
        # Add filters similar to Academic Standing tab
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
        
        if st.button("Apply", key="passfail_apply"):
            with st.spinner("Loading pass/fail distribution data..."):
                # Use the same filtering approach as Academic Standing
                filters = {"Semester": semester, "Course": course, "SchoolYear": year}
                df = get_academic_standing(filters)
                
                if not df.empty:
                    # Convert to pass/fail format
                    df["Result"] = df["GPA"].apply(lambda g: "Pass" if g >= 75 else "Fail")
                    
                    # Create summary table by Subject and Result
                    summary = df.groupby(["Subject", "Result"]).size().unstack(fill_value=0)
                    
                    # Display filtered data table
                    st.subheader("Filtered Pass/Fail Data")
                    display_columns = ["Name", "Course", "Subject", "GPA", "Result", "Semester", "SchoolYear"]
                    st.dataframe(df[display_columns])
                    
                    # Display summary table
                    st.subheader("Pass/Fail Summary by Subject")
                    st.dataframe(summary)
                    
                    # Create subplots for different views
                    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
                    
                    # Stacked bar chart (by subject)
                    summary.plot(kind="bar", stacked=True, ax=ax1, color=["green", "red"])
                    ax1.set_title(f"Pass/Fail Distribution by Subject\n(Semester: {semester}, Year: {year}, Course: {course})")
                    ax1.set_xlabel("Subjects")
                    ax1.set_ylabel("Number of Students")
                    ax1.legend()
                    ax1.tick_params(axis='x', rotation=45)
                    
                    # Heatmap for better visualization of large datasets
                    ax2.imshow(summary.T, cmap='RdYlGn', aspect='auto')
                    ax2.set_title(f"Pass/Fail Heatmap\n(Semester: {semester}, Year: {year}, Course: {course})")
                    ax2.set_xlabel("Subjects")
                    ax2.set_ylabel("Result")
                    ax2.set_yticks(range(len(summary.columns)))
                    ax2.set_yticklabels(summary.columns)
                    ax2.set_xticks(range(len(summary.index)))
                    ax2.set_xticklabels(summary.index, rotation=45)
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    
                    # Display summary statistics
                    st.subheader("Summary Statistics")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        total_students = len(df)
                        st.metric("Total Records", total_students)
                    with col2:
                        pass_count = len(df[df["Result"] == "Pass"])
                        pass_rate = (pass_count / total_students * 100) if total_students > 0 else 0
                        st.metric("Pass Rate", f"{pass_rate:.1f}%")
                    with col3:
                        fail_count = len(df[df["Result"] == "Fail"])
                        fail_rate = (fail_count / total_students * 100) if total_students > 0 else 0
                        st.metric("Fail Rate", f"{fail_rate:.1f}%")
                else:
                    st.write("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply' to load pass/fail distribution data")

    with tab3:
        st.subheader("Enrollment Trends")
        course = st.selectbox("Course", ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"], key="enrollment_course")
        yoy = st.checkbox("Show Year-over-Year (by SchoolYear)", value=False, key="enrollment_yoy")
        if st.button("Apply", key="enrollment_apply"):
            with st.spinner("Loading enrollment trends data..."):
                df = grades_df
                if not df.empty:
                    semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
                    df["Semester"] = df["SemesterID"].map(semesters_dict)
                    df = df.merge(students_df[["_id", "Course"]], left_on="StudentID", right_on="_id", how="left", suffixes=("", "_stu"))
                    df.rename(columns={"Course": "CourseName"}, inplace=True)
                    if course != "All":
                        df = df[df["CourseName"] == course]
                    # base enrollment by Semester
                    enrollment = df.groupby(["Semester"]).size().reset_index(name="Count").sort_values("Semester")
                    if yoy and "SemesterID" in df.columns:
                        year_map = dict(zip(semesters_df["_id"], semesters_df["SchoolYear"]))
                        df["SchoolYear"] = df["SemesterID"].map(year_map)
                        enrollment_yoy = df.groupby(["SchoolYear", "Semester"]).size().reset_index(name="Count").sort_values(["SchoolYear", "Semester"])
                        st.subheader("Year-over-Year Enrollment by Semester")
                        st.dataframe(enrollment_yoy)
                    st.dataframe(enrollment)
                    
                    # Create subplots for different views
                    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
                    
                    # Area chart for trends
                    ax1.fill_between(enrollment["Semester"], enrollment["Count"], alpha=0.6, color="skyblue")
                    ax1.plot(enrollment["Semester"], enrollment["Count"], marker='o', linewidth=2, color="darkblue")
                    ax1.set_title("Enrollment Trends by Semester")
                    ax1.set_xlabel("Semester")
                    ax1.set_ylabel("Number of Students")
                    ax1.grid(True, alpha=0.3)
                    ax1.tick_params(axis='x', rotation=45)
                    
                    # Step plot for cumulative enrollment (by course if filtered)
                    cumulative = enrollment["Count"].cumsum()
                    ax2.step(enrollment["Semester"], cumulative, where='post', linewidth=2, marker='o')
                    ax2.set_title("Cumulative Enrollment")
                    ax2.set_xlabel("Semester")
                    ax2.set_ylabel("Cumulative Students")
                    ax2.grid(True, alpha=0.3)
                    ax2.tick_params(axis='x', rotation=45)
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                else:
                    st.write("No data")
        else:
            st.info("👆 Click 'Apply' to load enrollment trends data")

    with tab4:
        st.subheader("Incomplete Grades")
        col1, col2 = st.columns(2)
        with col1:
            semester = st.selectbox("Semester", semester_options, key="incomplete_semester")
        with col2:
            faculty_options = ["All"] + list(teachers_df["Teacher"].unique()) if not teachers_df.empty else ["All"]
            faculty = st.selectbox("Faculty", faculty_options, key="incomplete_faculty")
        if st.button("Apply", key="incomplete_apply"):
            with st.spinner("Loading incomplete grades data..."):
                df = grades_df
                if semester != "All":
                    sem_id = semesters_df[semesters_df["Semester"] == semester]["_id"].values
                    if len(sem_id) > 0:
                        df = df[df["SemesterID"] == sem_id[0]]
                if faculty != "All":
                    teacher_id = teachers_df[teachers_df["Teacher"] == faculty]["_id"].values
                    if len(teacher_id) > 0:
                        df = df[df["Teachers"] == teacher_id[0]]
                df = df[df["Grades"].apply(lambda g: g in ["INC", "Dropped", None] if g is not None else True)]
                teachers_dict = dict(zip(teachers_df["_id"], teachers_df["Teacher"]))
                df["TeacherName"] = df["Teachers"].map(teachers_dict)
                semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
                df["SemesterName"] = df["SemesterID"].map(semesters_dict)
                st.dataframe(df[["StudentID", "SubjectCodes", "Grades", "TeacherName", "SemesterName"]])
        else:
            st.info("👆 Click 'Apply' to load incomplete grades data")

    with tab5:
        st.subheader("Retention & Dropout")
        course = st.selectbox("Course", ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"], key="retention_course")
        if st.button("Apply", key="retention_apply"):
            with st.spinner("Loading retention & dropout data..."):
                if not semesters_df.empty:
                    latest_sem = semesters_df.sort_values(by=["SchoolYear", "Semester"], ascending=False).iloc[0]
                    active_ids = set(grades_df[grades_df["SemesterID"] == latest_sem["_id"]]["StudentID"])
                    df = students_df
                    if course != "All":
                        df = df[df["Course"] == course]
                    df["Status"] = df["_id"].apply(lambda sid: "Retained" if sid in active_ids else "Dropped")
                    summary = df["Status"].value_counts()
                    st.dataframe(summary.reset_index())
                    fig, ax = plt.subplots()
                    ax.pie(summary.values, labels=summary.index, autopct='%1.1f%%', colors=["green", "red"])
                    ax.set_title("Retention vs Dropout")
                    st.pyplot(fig)
                else:
                    st.write("No semester data")
        else:
            st.info("👆 Click 'Apply' to load retention & dropout data")

    with tab6:
        st.subheader("Top Performers")
        # Optional semester filter
        top_semester = st.selectbox("Semester (optional)", ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"], key="top_semester")
        if st.button("Load Top Performers", key="top_apply"):
            with st.spinner("Loading top performers data..."):
                if not grades_df.empty and not students_df.empty:
                    gpa_data = {}
                    df_top = grades_df
                    if top_semester != "All":
                        sem_id = semesters_df[semesters_df["Semester"] == top_semester]["_id"].values
                        if len(sem_id) > 0:
                            df_top = df_top[df_top["SemesterID"] == sem_id[0]]
                        else:
                            df_top = df_top.iloc[0:0]
                    for _, g in df_top.iterrows():
                        sid = g["StudentID"]
                        grade_list = g.get("Grades", [])
                        if isinstance(grade_list, list) and grade_list:
                            avg = sum(grade_list) / len(grade_list)
                            if sid in gpa_data:
                                gpa_data[sid].append(avg)
                            else:
                                gpa_data[sid] = [avg]
                    rows = []
                    for sid, gpas in gpa_data.items():
                        student = students_df[students_df["_id"] == sid]
                        if not student.empty:
                            student = student.iloc[0]
                            final_gpa = round(sum(gpas) / len(gpas), 2)
                            rows.append({
                                "Name": student["Name"],
                                "Course": student["Course"],
                                "YearLevel": student["YearLevel"],
                                "GPA": final_gpa
                            })
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        top_df = df.sort_values(by="GPA", ascending=False).groupby("Course").head(3)
                        st.dataframe(top_df)
                    else:
                        st.write("No GPA data")
                else:
                    st.write("No data")
        else:
            st.info("👆 Click 'Load Top Performers' to view top performing students")

    with tab7:
        st.subheader("For Updates")
        st.write("No data")

if __name__ == "__main__":
    show_registrar_dashboard()
