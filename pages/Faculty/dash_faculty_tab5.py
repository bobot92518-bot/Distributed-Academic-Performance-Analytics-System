import streamlit as st
import pandas as pd 
import altair as alt
from global_utils import pkl_data_to_df, semesters_cache, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_semester_from_curriculum, get_active_curriculum,get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def display_chat(table_data):
    # chart_data = table_data.set_index('Student Name')
    # st.bar_chart(chart_data['Grade_num'], use_container_width=True)
            
    table_data["Grade Status"] = table_data["Grade_num"].apply(
        lambda g: "Not Set" if pd.isna(g) or g == 0
        else ("Grade Above 75" if g >= 75 else "Grade Below 75")
    )

    chart = (
        alt.Chart(table_data[table_data["Grade Status"] != "Not Set"])
        .mark_bar()
        .encode(
            x=alt.X("Student Name", title="Students", sort=None),
            y=alt.Y("Grade_num", title="Student Grades"),
            color=alt.Color(
                "Grade Status",
                title="Grade Category",
                scale=alt.Scale(
                    domain=["Grade Above 75", "Grade Below 75"],
                    range=["green", "red"]
                )
            )
        )
    )

    st.altair_chart(chart, use_container_width=True)

def display_grades_table(is_new_curriculum, df, semester_filter = None, subject_filter = None):
    """Display grades in Streamlit format"""
    if df.empty:
        st.warning("No grades found for the selected criteria.")
        return
    
    # Apply filters
    filtered_df = df.copy()
    if semester_filter and semester_filter != " - All Semesters - ":
        filtered_df = filtered_df[filtered_df['semester'] + " - " + filtered_df['schoolYear'].astype(str) == semester_filter]
    
    if subject_filter and subject_filter != " - All Subjects - ":
        filtered_df = filtered_df[filtered_df['subjectCode'] + " - " + filtered_df['subjectDescription'] == subject_filter]
    
    if filtered_df.empty:
        st.warning("No grades found for the selected filters.")
        return
    year_map = {
        1: "1st Year",
        2: "2nd Year",
        3: "3rd Year",
        4: "4th Year",
        5: "5th Year",
    }
    subject_year_map = {
        0: "",
        1: "| &nbsp; &nbsp; 1st Year",
        2: "| &nbsp; &nbsp; 2nd Year",
        3: "| &nbsp; &nbsp; 3rd Year",
        4: "| &nbsp; &nbsp; 4th Year",
        5: "| &nbsp; &nbsp; 5th Year",
    }
    
    
    
    # Group by semester and subject
    for (semester, school_year, subject_code, subject_desc, SubjectYearLevel, Course), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel', 'Course']
    ):
        
        with st.expander(f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code} &nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc} &nbsp;&nbsp; {subject_year_map.get(SubjectYearLevel, "")} &nbsp; - &nbsp; {Course}", expanded=True):
            
            table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
            table_data.columns = ['Student ID', 'Student Name', 'Course', 'YearLevel', 'Grade']
            
            table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
            table_data['Student ID'] = table_data['Student ID'].astype(str)
            table_data['Grade Status'] = table_data['Grade_num'].apply(
                lambda x: "Pending" if pd.isna(x) or x == 0 else "Completed"
            )
            
            valid_grades = table_data["Grade_num"][
                (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
            ]
            invalid_valid_grades = table_data[ (table_data["Grade_num"].isna()) | (table_data["Grade_num"] == 0) ]
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Students", len(table_data))
            with col2:
                st.metric("Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "N/A")
            with col3:
                st.metric("Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "N/A")
            with col4:
                st.metric("Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "N/A")
            with col5:
                st.metric("No Grades", len(invalid_valid_grades))
                
            # Manual table rendering instead of st.table
            st.markdown("### Student Grades")

            st.markdown("**Class Grade Distribution**")
            display_chat(table_data)

def show_faculty_tab5_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
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
            key="tab6_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab6_subject"
        )
    
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    
    selected_subject_code = None
    if selected_subject_display != " - All Subjects - ":
        for subj in subjects:
            if f"{subj['_id']} - {subj['Description']}" == selected_subject_display:
                selected_subject_code = subj['_id']
                break
            
    if st.button("📊 Load Grades", type="secondary", key="tab6_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            else:
                results = results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
            
            if results:
                df = result_records_to_dataframe(results)
                
                # Store in session state for other tabs
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                
                # Display results
                st.success(f"Found {len(results)} grade records for {current_faculty}")
                
                display_grades_table(new_curriculum, df, selected_semester_display, selected_subject_display)
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")