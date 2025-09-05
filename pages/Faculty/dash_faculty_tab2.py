import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import load_pkl_data, subjects_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list, get_students_from_grades
from pages.Faculty.faculty_pdf_generator import generate_student_grades_report_pdf

current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')



def get_student_longitude_grades(student_id):
    """
    Fetch all grades for a given student across all semesters using pandas.
    Returns a DataFrame with columns:
    Semester, SchoolYear, Subject Code, Subject Description, Units, Teacher, Grade
    """
    # Load normalized grades DataFrame
    df_grades = get_dataframe_grades()
    if df_grades.empty:
        return pd.DataFrame()

    # Filter by student
    df_student = df_grades[df_grades["StudentID"] == student_id]
    if df_student.empty:
        return pd.DataFrame()

    # Load subjects and semesters
    subjects_data = load_pkl_data(subjects_cache)
    subjects_df = pd.DataFrame(subjects_data) if isinstance(subjects_data, list) else subjects_data

    semesters_data = get_semesters_list()
    semesters_df = pd.DataFrame(semesters_data) if isinstance(semesters_data, list) else semesters_data

    # Merge to get subject info
    df_merged = df_student.merge(
        subjects_df[["_id", "Description", "Units"]],
        left_on="SubjectCode",
        right_on="_id",
        how="left"
    )

    df_merged = df_merged.merge(
        semesters_df[["_id", "Semester", "SchoolYear"]],
        left_on="SemesterID",
        right_on="_id",
        how="left",
        suffixes=("", "_sem")
    )

    # Select and rename columns
    df_merged = df_merged.rename(columns={
        "Description": "Subject Description",
        "Units": "Units",
        "Teacher": "Teacher",
        "Grade": "Grade",
        "Semester": "Semester",
        "SchoolYear": "SchoolYear"
    })

    df_merged = df_merged[["Semester", "SchoolYear", "SubjectCode", "Subject Description", "Units", "Teacher", "Grade"]]
    df_merged = df_merged.rename(columns={"SubjectCode": "Subject Code"})

    # Sort by SchoolYear, Semester, Subject Code
    semester_order = {"FirstSem": 1, "SecondSem": 2, "Summer": 3}
    df_merged["SemesterOrder"] = df_merged["Semester"].map(lambda x: semester_order.get(x, 99))
    df_merged.sort_values(by=["SchoolYear", "SemesterOrder", "Subject Code"], inplace=True)
    df_merged.drop(columns=["SemesterOrder"], inplace=True)

    return df_merged.reset_index(drop=True)

    
    

def show_faculty_tab2_info():
    
    st.title("View longitudinal performance of individual students.")
    
    with st.form(key="studentlist_search_form"):
        st.subheader("📋 Students (Paginated, 10 per page with single selection)")
        search_name = ""
        search_name = st.text_input("🔍 Search student by name").strip()
        search_button = st.form_submit_button("Search")
        
    if search_button:
        df_students = get_students_from_grades(teacher_name = current_faculty, name=search_name)
        st.session_state.df_students = df_students
    elif "df_students" not in st.session_state:
        df_students = get_students_from_grades(teacher_name = current_faculty)
    else:
        df_students = st.session_state.df_students
        
    if df_students.empty:
        st.warning("⚠️ No students found.")
        return
    
    if "selected_student_id" not in st.session_state:
        st.session_state.selected_student_id = None
    
    page_size = 10
    total_students = len(df_students)
    total_pages = (total_students - 1) // page_size + 1
    if search_button:
        st.session_state.page = 1
    if "page" not in st.session_state:
        st.session_state.page = 1

    page = st.number_input(
        "Page", 
        min_value=1, 
        max_value=total_pages, 
        value=st.session_state.page, 
        step=1
    )
    st.session_state.page = page
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df_students.iloc[start_idx:end_idx]
    
    # --- Single radio selection across page ---
    student_choices = df_page["StudentID"].tolist()
    student_labels = [
        f"{row.get('StudentID', 'N/A')} - {row.get('Student', 'Unknown')} ({row.get('Course', 'N/A')})"
        for _, row in df_page.iterrows()
    ]

    selected = st.radio(
        "Select a student to view grades:",
        options=student_choices,
        format_func=lambda x: dict(zip(student_choices, student_labels))[x],
        index=student_choices.index(st.session_state.selected_student_id)
        if st.session_state.selected_student_id in student_choices
        else 0
    )

    st.session_state.selected_student_id = selected

    # --- Show grades if a student is selected ---
    if st.session_state.selected_student_id:
        student_id = st.session_state.selected_student_id
        student_name = df_students.loc[df_students["StudentID"] == student_id, "Student"].values[0]
        df_grades = get_student_longitude_grades(student_id = student_id)

        if not df_grades.empty:
            st.markdown(f"### 📊 Grades for **{student_name}** (All Semesters) - Student ID: **{student_id}**")

            semester_order = {"FirstSem": 1, "SecondSem": 2, "Summer": 3}
            df_grades["SemesterOrder"] = df_grades["Semester"].map(lambda x: semester_order.get(x, 99))
            df_grades.sort_values(by=["SchoolYear", "SemesterOrder", "Subject Code"], inplace=True)

            for (semester, school_year), group in df_grades.groupby(["Semester", "SchoolYear"], sort=False):
                gpa = group["Grade"].mean() if not group["Grade"].isna().all() else None
                gpa_display = f"{gpa:.2f}" if gpa is not None else "N/A"
                st.markdown(f"**{semester} {school_year} (GPA: {gpa_display})**")

                display_cols = ["Subject Code", "Subject Description", "Units", "Teacher", "Grade"]
                st.dataframe(group[display_cols].reset_index(drop=True), use_container_width=True)

            
            st.markdown("---")
            
            overall_avg = df_grades["Grade"].mean() if not df_grades["Grade"].isna().all() else None
            overall_avg_display = f"{overall_avg:.2f}" if overall_avg is not None else "N/A"
            st.markdown(f"### 🏆 Overall General Average: **{overall_avg_display}**")

            df_grades["SemesterLabel"] = df_grades["SchoolYear"].astype(str) + " " + df_grades["Semester"].astype(str)
            avg_grades_per_sem = df_grades.groupby("SemesterLabel")["Grade"].mean().reset_index()

            avg_grades_per_sem["SemesterLabel"] = avg_grades_per_sem.apply(
                lambda row: f"{row['SemesterLabel']} (Avg: {row['Grade']:.2f})", axis=1
            )

            st.markdown("### 📈 Average Grade per Semester")
            st.line_chart(avg_grades_per_sem.set_index("SemesterLabel")["Grade"])
            
            # PDF download
            pdf_buffer = generate_student_grades_report_pdf(student_name, student_id, df_grades, avg_grades_per_sem)
            st.download_button(
                label="📥 Download PDF Report",
                data=pdf_buffer,
                file_name=f"{student_name}_grades_report.pdf",
                mime="application/pdf"
            )

            df_grades.drop(columns=["SemesterOrder"], inplace=True)


        else:
            st.warning(f"⚠️ No grades found for {student_name}.")
        

