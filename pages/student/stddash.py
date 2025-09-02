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

# ------------------ Self-Assessment: Data Helpers ------------------ #
def _expand_subject_rows(grades_records):
    """Expand per-semester records to per-subject rows with semester labels."""
    if not grades_records:
        return pd.DataFrame([])

    df = pd.DataFrame(grades_records)
    if df.empty:
        return df

    # Ensure required columns exist
    for col in ["SubjectCodes", "Teachers", "Grades", "Semester", "SchoolYear", "SemesterID"]:
        if col not in df.columns:
            df[col] = None

    # Build a semester label
    df["SemesterLabel"] = df.apply(
        lambda r: f"{r.get('SchoolYear', '')} - Sem {r.get('Semester', '')}", axis=1
    )

    # If lists, explode; otherwise, normalize single values
    if df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
        exp = pd.DataFrame({
            "SubjectCode": df["SubjectCodes"].explode().values,
            "Teacher": df["Teachers"].explode().values,
            "Grade": df["Grades"].explode().values,
            "SemesterID": df["SemesterID"].explode().values if df["SemesterID"].apply(lambda x: isinstance(x, list)).any() else df["SemesterID"].values,
            "SemesterLabel": df["SemesterLabel"].explode().values if df["SemesterLabel"].apply(lambda x: isinstance(x, list)).any() else df["SemesterLabel"].values,
        })
    else:
        exp = df.rename(columns={
            "SubjectCodes": "SubjectCode",
            "Teachers": "Teacher",
            "Grades": "Grade",
        })[["SubjectCode", "Teacher", "Grade", "SemesterID", "SemesterLabel"]]

    # Coerce numeric grades
    exp["NumericGrade"] = pd.to_numeric(exp["Grade"], errors="coerce")
    return exp

def _compute_student_trend(grades_records):
    """Return DataFrame with semester-level averages for the student."""
    exp = _expand_subject_rows(grades_records)
    if exp.empty:
        return pd.DataFrame([])

    trend = (
        exp.dropna(subset=["NumericGrade"]) 
           .groupby(["SemesterID", "SemesterLabel"], dropna=False)["NumericGrade"]
           .mean()
           .reset_index()
           .rename(columns={"NumericGrade": "StudentAverage"})
    )
    return trend

def _compute_class_trend():
    """Compute class average per semester across all students."""
    if not os.path.exists(grades_cache) or not os.path.exists(semesters_cache):
        return pd.DataFrame([])

    all_grades = pd.read_pickle(grades_cache)
    semesters = pd.read_pickle(semesters_cache)

    grades_df = pd.DataFrame(all_grades) if isinstance(all_grades, list) else all_grades
    sem_df = pd.DataFrame(semesters) if isinstance(semesters, list) else semesters

    if grades_df.empty:
        return pd.DataFrame([])

    # Join semester label
    merged = grades_df.copy()
    merged["Semester"] = ""
    merged["SchoolYear"] = ""
    for idx, row in merged.iterrows():
        sem_id = row.get("SemesterID")
        match = sem_df[sem_df["_id"] == sem_id]
        if not match.empty:
            merged.at[idx, "Semester"] = match.iloc[0].get("Semester", "")
            merged.at[idx, "SchoolYear"] = match.iloc[0].get("SchoolYear", "")

    merged_records = merged.to_dict(orient="records")
    exp = _expand_subject_rows(merged_records)
    if exp.empty:
        return pd.DataFrame([])

    class_trend = (
        exp.dropna(subset=["NumericGrade"]) 
           .groupby(["SemesterID", "SemesterLabel"], dropna=False)["NumericGrade"]
           .mean()
           .reset_index()
           .rename(columns={"NumericGrade": "ClassAverage"})
    )
    return class_trend

def _compute_pass_fail_summary(grades_records, pass_threshold=75):
    """Return counts of Passed/Failed/Incomplete based on numeric grades and NaNs."""
    exp = _expand_subject_rows(grades_records)
    if exp.empty:
        return pd.Series({"Passed": 0, "Failed": 0, "Incomplete": 0})

    status = pd.Series(index=exp.index, dtype="object")
    status[(exp["NumericGrade"].notna()) & (exp["NumericGrade"] >= pass_threshold)] = "Passed"
    status[(exp["NumericGrade"].notna()) & (exp["NumericGrade"] < pass_threshold)] = "Failed"
    status[exp["NumericGrade"].isna()] = "Incomplete"
    return status.value_counts().reindex(["Passed", "Failed", "Incomplete"]).fillna(0).astype(int)

def _compute_subject_vs_class(grades_records):
    """Return DataFrame with student's subject averages vs class averages per subject."""
    exp_student = _expand_subject_rows(grades_records)
    if exp_student.empty:
        return pd.DataFrame([])

    # Student per-subject average
    stu = (
        exp_student.dropna(subset=["NumericGrade"]) 
                 .groupby("SubjectCode")["NumericGrade"].mean()
                 .reset_index()
                 .rename(columns={"NumericGrade": "StudentAvg"})
    )

    # Class per-subject average (across all semesters)
    if not os.path.exists(grades_cache):
        return stu

    all_grades = pd.read_pickle(grades_cache)
    grades_df = pd.DataFrame(all_grades) if isinstance(all_grades, list) else all_grades
    if grades_df.empty:
        return stu

    exp_all = _expand_subject_rows(grades_df.to_dict(orient="records"))
    if exp_all.empty:
        return stu

    cls = (
        exp_all.dropna(subset=["NumericGrade"]) 
              .groupby("SubjectCode")["NumericGrade"].mean()
              .reset_index()
              .rename(columns={"NumericGrade": "ClassAvg"})
    )

    out = pd.merge(stu, cls, on="SubjectCode", how="left")
    return out

# ------------------ Self-Assessment: UI ------------------ #
def show_self_assessment(grades_records):
    st.markdown("### 🧭 Self-Assessment & Insights")

    # Tabs for the four requested views
    tab1, tab2, tab3, tab4 = st.tabs([
        "Performance Trend Over Time",
        "Subject Difficulty Ratings",
        "Comparison with Class Average",
        "Passed vs Failed Summary",
    ])

    # 1) Performance Trend Over Time
    with tab1:
        trend_student = _compute_student_trend(grades_records)
        trend_class = _compute_class_trend()

        if trend_student.empty:
            st.info("No data available to plot GPA trend.")
        else:
            df_plot = trend_student.copy()
            if not trend_class.empty:
                df_plot = pd.merge(
                    df_plot,
                    trend_class[["SemesterID", "ClassAverage"]],
                    on="SemesterID",
                    how="left",
                )
            df_plot = df_plot.sort_values("SemesterID")
            df_plot = df_plot.set_index("SemesterLabel")[["StudentAverage"] + (["ClassAverage"] if "ClassAverage" in df_plot.columns else [])]
            st.line_chart(df_plot, use_container_width=True)

    # 2) Subject Difficulty Ratings (session-level storage)
    with tab2:
        exp = _expand_subject_rows(grades_records)
        if exp.empty:
            st.info("No subjects to rate.")
        else:
            st.caption("Rate perceived difficulty per subject (1 = easiest, 5 = hardest). Saved for this session.")
            if "subject_difficulty" not in st.session_state:
                st.session_state["subject_difficulty"] = {}
            difficulties = st.session_state["subject_difficulty"]

            unique_subjects = sorted(exp["SubjectCode"].dropna().astype(str).unique())
            cols = st.columns(2)
            updated = False
            for i, subj in enumerate(unique_subjects):
                with cols[i % 2]:
                    current = difficulties.get(subj, 3)
                    rating = st.slider(f"{subj}", min_value=1, max_value=5, value=int(current), key=f"rate_{subj}")
                    if rating != current:
                        difficulties[subj] = rating
                        updated = True
            if updated:
                st.session_state["subject_difficulty"] = difficulties
            if difficulties:
                disp = pd.DataFrame({"Subject": list(difficulties.keys()), "Difficulty": list(difficulties.values())}).set_index("Subject")
                st.bar_chart(disp, use_container_width=True)

    # 3) Comparison with Class Average
    with tab3:
        comp = _compute_subject_vs_class(grades_records)
        if comp.empty:
            st.info("No data available for comparison.")
        else:
            comp = comp.set_index("SubjectCode")
            st.bar_chart(comp, use_container_width=True)

    # 4) Passed vs Failed Summary
    with tab4:
        summary = _compute_pass_fail_summary(grades_records)
        if summary.sum() == 0:
            st.info("No summary available.")
        else:
            st.bar_chart(summary)

# ------------------ Main Dashboard Function ------------------ #
def show_student_dashboard():
    st.write("Here you can view your grades, assignments, and academic progress.")
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()

    username = st.session_state.username
    student = get_student_info(username)

    if not student:
        st.error("Student record not found.")
        st.stop()

    grades = get_student_grades(student["_id"])

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current GPA", student.get("GPA", "N/A"))
    with col2:
        st.metric("Course", student.get("Course", "N/A"))

    st.markdown("### 📝 Academic Transcript")

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

    # Self-Assessment section (uses same grades)
    if grades:
        show_self_assessment(grades)

# ------------------ Entry Point ------------------ #
def main():
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()
