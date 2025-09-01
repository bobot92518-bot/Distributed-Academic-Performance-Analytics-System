import streamlit as st
import pandas as pd
import os

# ------------------ Paths to Pickle Files ------------------ #
student_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"

# ------------------ Helper Functions ------------------ #
def get_student_info(username):
    """Fetch student info from pickle by username"""
    if not os.path.exists(student_cache):
        st.error("Student cache file not found.")
        st.stop()

    students = pd.read_pickle(student_cache)
    students_df = pd.DataFrame(students) if isinstance(students, list) else students
    match = students_df[students_df["username"] == username]
    return match.iloc[0].to_dict() if not match.empty else None

def get_student_grades(student_id):
    """Fetch grades of a student by their student_id and join with semesters"""
    if not os.path.exists(grades_cache) or not os.path.exists(semesters_cache):
        st.error("Grades or semesters cache file not found.")
        st.stop()

    grades = pd.read_pickle(grades_cache)
    semesters = pd.read_pickle(semesters_cache)

    grades_df = pd.DataFrame(grades) if isinstance(grades, list) else grades
    sem_df = pd.DataFrame(semesters) if isinstance(semesters, list) else semesters

    student_grades = grades_df[grades_df["StudentID"] == student_id].copy()

    # Attach Semester + SchoolYear from semesters
    if not student_grades.empty:
        student_grades["Semester"] = ""
        student_grades["SchoolYear"] = ""

        for idx, row in student_grades.iterrows():
            sem_id = row.get("SemesterID")
            match = sem_df[sem_df["_id"] == sem_id]
            if not match.empty:
                student_grades.at[idx, "Semester"] = match.iloc[0].get("Semester", "")
                student_grades.at[idx, "SchoolYear"] = match.iloc[0].get("SchoolYear", "")
    return student_grades.to_dict(orient="records")

# ------------------ Main Dashboard Function ------------------ #
def show_student_dashboard():
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()

    username = st.session_state.username
    student = get_student_info(username)

    if not student:
        st.error("Student record not found.")
        st.stop()

    st.markdown("## 🎓 Student Dashboard")
    st.write(f"Welcome, **{student.get('Name', username)}** 👋")
    st.write("Here you can view your grades, assignments, and academic progress.")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current GPA", student.get("GPA", "N/A"))
    with col2:
        st.metric("Course", student.get("Course", "N/A"))

    st.markdown("### 📝 Academic Transcript")

    grades = get_student_grades(student["_id"])

    if grades:
        df = pd.DataFrame(grades)
        df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

        if "Semester" in df.columns and "SchoolYear" in df.columns:
            grouped = df.groupby(["SchoolYear", "Semester"])
            for (sy, sem), sem_df in grouped:
                st.subheader(f"{sy} - Semester {sem}")

                if (
                    "SubjectCodes" in sem_df
                    and sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any()
                ):
                    expanded_df = pd.DataFrame({
                        "SubjectCode": sem_df["SubjectCodes"].explode().values,
                        "Teacher": sem_df["Teachers"].explode().values,
                        "Grade": sem_df["Grades"].explode().values
                    })
                else:
                    expanded_df = sem_df[["SubjectCodes", "Teachers", "Grades"]].rename(
                        columns={
                            "SubjectCodes": "SubjectCode",
                            "Teachers": "Teacher",
                            "Grades": "Grade"
                        }
                    )

                st.dataframe(expanded_df, use_container_width=True)

                if "Grade" in expanded_df.columns:
                    valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                    if not valid_grades.empty:
                        avg = valid_grades.mean()
                        st.write(f"**Semester Average: {avg:.2f}**")
                    else:
                        st.write("**Semester Average: N/A**")

                st.markdown("---")
        else:
            st.warning("Missing 'Semester' or 'SchoolYear' fields.")
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No grades found for this student.")

    if st.button("Logout"):
        logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
        st.session_state.clear()
        st.success(logout_message)
        st.info("Redirecting to login page...")
        st.switch_page("app.py")

# ------------------ Entry Point ------------------ #
def main():
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()
