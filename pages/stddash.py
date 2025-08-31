import streamlit as st
import pandas as pd
from bson import ObjectId
from dbconnect import *

# ------------------ Helper Functions ------------------ #
def get_student_info(username):
    """Fetch student info from MongoDB by username"""
    db = db_connect()
    students_col = db["students"]
    return students_col.find_one({"username": username})


def get_student_grades(student_id):
    """Fetch grades of a student by their student_id and join with semesters"""
    db = db_connect()
    grades_col = db["grades"]
    sem_col = db["semesters"]

    grades = list(grades_col.find({"StudentID": student_id}))

    # Attach Semester + SchoolYear from semesters collection
    for g in grades:
        sem_id = g.get("SemesterID")
        if sem_id:
            if isinstance(sem_id, ObjectId):
                sem = sem_col.find_one({"_id": sem_id})
            else:
                sem = sem_col.find_one({"_id": sem_id})
            if sem:
                g["Semester"] = sem.get("Semester", "")
                g["SchoolYear"] = sem.get("SchoolYear", "")
    return grades


# ------------------ Student Dashboard ------------------ #
def show_student_dashboard():
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()

    username = st.session_state.username
    student = get_student_info(username)

    if not student:
        st.error("Student record not found in database.")
        st.stop()

    # Default student dashboard
    st.markdown("## 🎓 Student Dashboard")
    st.write(f"Welcome, **{student.get('Name', username)}** 👋")
    st.write("Here you can view your grades, assignments, and academic progress.")

    # Quick stats
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current GPA", student.get("GPA", "N/A"))
    with col2:
        st.metric("Course", student.get("Course", "N/A"))

    # --- Student Grades --- #
    st.markdown("### 📝 Academic Transcript")

    grades = get_student_grades(student["_id"])

    if grades:
        df = pd.DataFrame(grades)

        # Drop unused fields
        df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

        # ✅ Group by SchoolYear + Semester
        if "Semester" in df.columns and "SchoolYear" in df.columns:
            grouped = df.groupby(["SchoolYear", "Semester"])
            for (sy, sem), sem_df in grouped:
                st.subheader(f"{sy} - Semester {sem}")

                # --- If values are lists, expand them so each subject = one row
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

                # Show as table (each subject = one row)
                st.table(expanded_df)

                # --- Compute average
                if "Grade" in expanded_df.columns:
                    valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                    if not valid_grades.empty:
                        avg = valid_grades.mean()
                        st.write(f"**Semester Average: {avg:.2f}**")
                    else:
                        st.write("**Semester Average: N/A**")

                st.markdown("---")
        else:
            st.warning("No 'Semester' or 'SchoolYear' field found in grades collection.")
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No grades found for this student.")

    # Logout button
    if st.button("Logout"):
        logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
        st.session_state.clear()
        st.success(logout_message)
        st.info("Redirecting to login page...")

        import time
        time.sleep(2)
        st.switch_page("app.py")


# ------------------ Run Page ------------------ #
if __name__ == "__main__":
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()
else:
    show_student_dashboard()
