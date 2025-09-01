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

    if students_df.empty or grades_df.empty:
        return pd.DataFrame()

    # Merge grades with students
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id) > 0:
            merged = merged[merged["SemesterID"] == sem_id[0]]

    if filters.get("SchoolYear") != "All":
        sem_id = semesters_df[semesters_df["SchoolYear"] == int(filters["SchoolYear"])]["_id"].values
        if len(sem_id) > 0:
            merged = merged[merged["SemesterID"].isin(sem_id)]

    # Calculate GPA
    merged["GPA"] = merged["Grades"].apply(lambda x: sum(x)/len(x) if isinstance(x, list) and x else 0)

    # Determine status
    merged["Status"] = merged["GPA"].apply(lambda g: "Good Standing" if g >= 75 else "Probation")

    return merged[["Name", "GPA", "Status"]].drop_duplicates()

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

    # Load data
    students_df = pd.DataFrame(load_pkl_data(students_cache))
    grades_df = pd.DataFrame(load_pkl_data(grades_cache))
    semesters_df = pd.DataFrame(load_pkl_data(semesters_cache))
    subjects_df = pd.DataFrame(load_pkl_data(subjects_cache))
    teachers_df = pd.DataFrame(load_pkl_data(teachers_cache))

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
            semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
            semester = st.selectbox("Semester", semester_options, key="academic_semester")
        with col2:
            course_options = ["All"] + list(subjects_df["Description"].unique()) if not subjects_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="academic_course")
        with col3:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("Year Level", year_options, key="academic_year")

        if st.button("Apply Filters", key="academic_apply"):
            df = get_academic_standing({"Semester": semester, "Subject": course, "SchoolYear": year})
            if not df.empty:
                st.dataframe(df)
                fig, ax = plt.subplots()
                ax.hist(df["GPA"], bins=10, edgecolor='black')
                ax.set_title("GPA Distribution")
                ax.set_xlabel("GPA")
                ax.set_ylabel("Number of Students")
                st.pyplot(fig)
            else:
                st.write("No data available")

    with tab2:
        st.subheader("Pass/Fail Distribution")
        semester = st.selectbox("Semester", semester_options, key="passfail_semester")
        if st.button("Apply", key="passfail_apply"):
            if semester != "All":
                sem_id = semesters_df[semesters_df["Semester"] == semester]["_id"].values
                if len(sem_id) > 0:
                    df = grades_df[grades_df["SemesterID"] == sem_id[0]]
                else:
                    df = pd.DataFrame()
            else:
                df = grades_df
            if not df.empty and "Grades" in df.columns and "SubjectCodes" in df.columns:
                df["SubjectCodes"] = df["SubjectCodes"].apply(lambda x: x[0] if isinstance(x, list) and x else str(x))
                df["Result"] = df["Grades"].apply(lambda g: "Pass" if isinstance(g, list) and g and max(g) >= 75 else "Fail")
                summary = df.groupby(["SubjectCodes", "Result"]).size().unstack(fill_value=0)
                st.dataframe(summary)
                fig, ax = plt.subplots()
                summary.plot(kind="bar", ax=ax, color=["green", "red"])
                ax.set_title("Pass/Fail Distribution by Subject")
                ax.set_xlabel("Subjects")
                ax.set_ylabel("Number of Students")
                st.pyplot(fig)
            else:
                st.write("No data")

    with tab3:
        st.subheader("Enrollment Trends")
        course = st.selectbox("Course", ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"], key="enrollment_course")
        if st.button("Apply", key="enrollment_apply"):
            df = grades_df
            if not df.empty:
                semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
                df["Semester"] = df["SemesterID"].map(semesters_dict)
                if course != "All":
                    student_ids = students_df[students_df["Course"] == course]["_id"].tolist()
                    df = df[df["StudentID"].isin(student_ids)]
                enrollment = df.groupby("Semester").size().reset_index(name="Count").sort_values("Semester")
                st.dataframe(enrollment)
                fig, ax = plt.subplots()
                ax.bar(enrollment["Semester"], enrollment["Count"], color="skyblue")
                ax.set_title("Enrollment Trends by Semester")
                ax.set_xlabel("Semester")
                ax.set_ylabel("Number of Students")
                st.pyplot(fig)
            else:
                st.write("No data")

    with tab4:
        st.subheader("Incomplete Grades")
        col1, col2 = st.columns(2)
        with col1:
            semester = st.selectbox("Semester", semester_options, key="incomplete_semester")
        with col2:
            faculty_options = ["All"] + list(teachers_df["Teacher"].unique()) if not teachers_df.empty else ["All"]
            faculty = st.selectbox("Faculty", faculty_options, key="incomplete_faculty")
        if st.button("Apply", key="incomplete_apply"):
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

    with tab5:
        st.subheader("Retention & Dropout")
        course = st.selectbox("Course", ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"], key="retention_course")
        if st.button("Apply", key="retention_apply"):
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

    with tab6:
        st.subheader("Top Performers")
        if st.button("Load Top Performers", key="top_apply"):
            if not grades_df.empty and not students_df.empty:
                gpa_data = {}
                for _, g in grades_df.iterrows():
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

    with tab7:
        st.subheader("For Updates")
        st.write("No data")

    if st.button("Logout"):
        logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
        st.session_state.clear()
        st.success(logout_message)
        st.info("Redirecting to login page...")
        import time
        time.sleep(3)
        st.switch_page("app.py")

if __name__ == "__main__":
    show_registrar_dashboard()
