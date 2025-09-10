import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import pkl_data_to_df, subjects_cache, semesters_cache, new_subjects_cache, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import (
    get_semesters_list,
    get_subjects_by_teacher,
    get_semester_from_curriculum,
    get_active_curriculum,
    get_student_grades_by_subject_and_semester,
    get_new_student_grades_by_subject_and_semester,
)
from pages.Faculty.faculty_pdf_generator import generate_student_grades_report_pdf

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def show_faculty_tab6_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    st.title("Additional Filtered Queries.")

    # --- View by Subject (per teacher) ---
    st.subheader("👩‍🏫 View by Subject (Your Classes)")

    semesters_df = pkl_data_to_df(semesters_cache)
    curriculum_year = get_active_curriculum(new_curriculum)
    semesters = []
    if new_curriculum:
        semesters = get_semester_from_curriculum(curriculum_year, semesters_df)
    else:
        semesters = get_semesters_list(new_curriculum)

    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)

    col1, col2 = st.columns([1, 1])
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester",
            semester_options,
            key="tab6_semester_tab6"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject",
            subject_options,
            key="tab6_subject_tab6"
        )

    load_clicked = st.button("📊 Load Grades", type="secondary", key="tab6_load_button_tab6")

    selected_semester_id = None
    for sem in semesters:
        if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
            selected_semester_id = sem['_id']
            break

    selected_subject_code = None
    for subj in subjects:
        if f"{subj['_id']} - {subj['Description']}" == selected_subject_display:
            selected_subject_code = subj['_id']
            break

    if load_clicked and selected_semester_id and selected_subject_code:
        with st.spinner("Loading class list..."):
            if new_curriculum:
                results = get_new_student_grades_by_subject_and_semester(
                    current_faculty=current_faculty,
                    semester_id=selected_semester_id,
                    subject_code=selected_subject_code,
                )
            else:
                results = get_student_grades_by_subject_and_semester(
                    current_faculty=current_faculty,
                    semester_id=selected_semester_id,
                    subject_code=selected_subject_code,
                )

            if results:
                df = result_records_to_dataframe(results)
                st.session_state.tab6_class_df = df
                st.success(f"Loaded {len(df)} records.")
            else:
                st.warning("No records found for the selected filters.")

    class_df = st.session_state.get("tab6_class_df", pd.DataFrame())
    if class_df is not None and not class_df.empty:
        df_display = class_df.copy()
        df_display["Grade_num"] = pd.to_numeric(df_display.get("grade", pd.Series(dtype=float)), errors="coerce")
        df_missing = df_display[df_display["Grade_num"].isna() | (df_display["Grade_num"] == 0)]
        df_valid = df_display[df_display["Grade_num"].notna() & (df_display["Grade_num"] > 0)]

        # Grade range selector (affects only valid numeric grades; missing remain visible)
        colg1, colg2 = st.columns(2)
        with colg1:
            min_grade = st.number_input("Min grade", value=0.0, step=1.0, min_value=0.0, max_value=100.0, key="tab6_min_grade")
        with colg2:
            max_grade = st.number_input("Max grade", value=100.0, step=1.0, min_value=0.0, max_value=100.0, key="tab6_max_grade")
        if max_grade < min_grade:
            max_grade = min_grade

        df_valid_range = df_valid[(df_valid["Grade_num"] >= min_grade) & (df_valid["Grade_num"] <= max_grade)]
        final_df = pd.concat([df_valid_range, df_missing], ignore_index=True)

        # Metrics
        colm1, colm2, colm3, colm4 = st.columns(4)
        with colm1:
            st.metric("Students", len(final_df))
        with colm2:
            st.metric("Avg", f"{df_valid_range['Grade_num'].mean():.2f}" if not df_valid_range.empty else "N/A")
        with colm3:
            st.metric("Highest", f"{df_valid_range['Grade_num'].max():.0f}" if not df_valid_range.empty else "N/A")
        with colm4:
            st.metric("No Grades", int(len(df_missing)))

        show_cols = [
            "studentName", "Course", "YearLevel", "grade"
        ]
        renamed = final_df[show_cols].rename(columns={
            "studentName": "Student Name",
            "grade": "Grade",
        })
        st.dataframe(renamed.sort_values(["Student Name"]).reset_index(drop=True), use_container_width=True)

    # Removed per-student search/radio and per-student PDF/export section for Tab 6