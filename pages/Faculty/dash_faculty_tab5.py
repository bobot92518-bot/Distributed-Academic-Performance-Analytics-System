import streamlit as st
import pandas as pd 
import altair as alt
import math
from global_utils import pkl_data_to_df, semesters_cache, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semester, get_semesters_list, get_subjects_by_teacher, get_semester_from_curriculum, get_active_curriculum,get_student_grades_by_subject_and_semester, get_new_student_grades_from_db_by_subject_and_semester
from pages.Faculty.faculty_data_manager import save_new_student_grades

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

year_map = {
    1: "1st Year",
    2: "2nd Year",
    3: "3rd Year",
    4: "4th Year",
    5: "5th Year",
}    

        
def display_grades_radio(df_students,new_curriculum):
    st.markdown("### 🎓 Student Grades")

    # --- Persist selected student ---
    if "selected_student_id" not in st.session_state:
        st.session_state.selected_student_id = None

    # --- Pagination setup ---
    page_size = 10
    total_students = len(df_students)
    total_pages = (total_students - 1) // page_size + 1

    if "page" not in st.session_state:
        st.session_state.page = 1

    # Page selector
    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.page,
        step=1,
        key="pagination_input"  # Add unique key to prevent conflicts
    )
    st.session_state.page = page

    # Slice dataframe for current page
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df_students.iloc[start_idx:end_idx]

    # --- Radio options (IDs as values, pretty labels for display) ---
    student_choices = df_page["StudentID"].tolist()
    student_labels = [
        f"{row['StudentID']} - {row['studentName']} ({row['Course']}, Year {row['YearLevel']}, Grade: {"Not Set" if pd.isna(row['grade']) or row['grade'] == 0 else row['grade']})"
        for _, row in df_page.iterrows()
    ]

    selected = st.radio(
        "Select a student to view grades:",
        options=student_choices,
        format_func=lambda x: dict(zip(student_choices, student_labels))[x],
        key="student_radio_selection"   # Use a more descriptive key
    )

    # Save selection
    st.session_state.selected_student_id = selected

    # --- Show details if selected ---
    if st.session_state.selected_student_id:
        student_row = df_students[df_students["StudentID"] == st.session_state.selected_student_id].iloc[0]

        year_map = {
            1: "1st Year",
            2: "2nd Year",
            3: "3rd Year",
            4: "4th Year",
            5: "5th Year",
        }
        
        student_year = year_map.get(student_row["YearLevel"], str(student_row["YearLevel"]))

        st.markdown("""
        <style>
        .readonly-box {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 0.5rem 0.75rem;
            margin-bottom: 0.5rem;
            font-size: 0.95rem;
            color: #333;
        }
        .readonly-label {
            font-weight: 600;
            margin-bottom: 0.2rem;
            display: block;
            font-size: 0.85rem;
            color: #555;
        }
        </style>
        """, unsafe_allow_html=True)

        stud_grade = student_row["grade"]
        grade_status = "⚠️ PENDING" if pd.isna(stud_grade) or stud_grade == 0 else f" ✅ DONE - {stud_grade}"
        status_color = "orange" if grade_status == "⚠️ PENDING" else "green"
        save_label = "Save" if pd.isna(stud_grade) or stud_grade  == 0 else "Update"
        semester_df = get_semester(student_row["semester"], student_row["schoolYear"])
        SemesterID = int(semester_df["_id"].iloc[0])

        # Show details in readonly-style input boxes
        st.markdown(f"""#### 📄 Selected Student Info &nbsp; | &nbsp; &nbsp; Grade Submission Status: <span style='color:{status_color}; font-weight:bold;'>{grade_status}</span>""",unsafe_allow_html=True)

        st.markdown(f"<span class='readonly-label'>🆔 Student ID</span><div class='readonly-box'>{student_row['StudentID']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>👤 Name</span><div class='readonly-box'>{student_row['studentName']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>🎓 Course</span><div class='readonly-box'>{student_row['Course']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>📘 Year Level</span><div class='readonly-box'>{student_year}</div>", unsafe_allow_html=True)


        # if new_curriculum:
            
        #     new_grade = st.number_input(
        #         "⭐ Grade",
        #         value=float(student_row["grade"]),
        #         min_value=0.0,
        #         max_value=100.0,
        #         step=0.1,
        #         format="%.1f",
        #         key="grade_input"  # Add unique key
        #     )

        #     if st.button(f"💾 {save_label} Grade", key="save_grade_btn"):
        #         with st.spinner("⏳ Saving grade, please wait..."):
        #             try:
        #                 result = save_new_student_grades(student_id=student_row["StudentID"], subject_code=student_row["subjectCode"], grade=new_grade, semester_id=SemesterID, teacher=current_faculty)
        #                 if result["success"]:
        #                     st.success(f"✅ {result['message']}")
        #                     st.rerun()  
        #                 else:
        #                     st.error(f"❌ {result['message']}")
        #             except Exception as e:
        #                 st.error(f"❌ Error saving grade: {str(e)}")
        # else:
        grade_display = stud_grade if not pd.isna(stud_grade)  else "No Grade"
        st.markdown(f"<span class='readonly-label'>⭐ Grade</span><div class='readonly-box'>{grade_display}</div>", unsafe_allow_html=True)


def show_faculty_tab5_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
    # Initialize session state for persistence
    if 'grades_df' not in st.session_state:
        st.session_state.grades_df = None
    if 'current_faculty' not in st.session_state:
        st.session_state.current_faculty = current_faculty
    if 'loaded_filters' not in st.session_state:
        st.session_state.loaded_filters = {}
    
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
            key="tab5_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab5_subject"
        )
    search_name = st.text_input("🔍 Search Student Name", value="",key="tab5_search_name",placeholder="Type a student name...")
    
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
            
    if st.button("📊 Load Grades", type="secondary", key="tab5_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_from_db_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            else:
                results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
            
            if results:
                df = result_records_to_dataframe(results)
                if search_name.strip():
                    df = df[df["studentName"].str.contains(search_name, case=False, na=False)]
                
                # Store in session state for persistence
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                st.session_state.loaded_filters = {
                    'semester': selected_semester_display,
                    'subject': selected_subject_display,
                    'search_name': search_name
                }
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
                st.session_state.grades_df = None
    
    # Display grades if they exist in session state
    if st.session_state.grades_df is not None and not st.session_state.grades_df.empty:
        # Show current filter info
        if st.session_state.loaded_filters:
            st.info(f"📋 Showing grades for: **{st.session_state.loaded_filters.get('semester', 'All')}** | **{st.session_state.loaded_filters.get('subject', 'All')}**" + 
                   (f" | Search: **{st.session_state.loaded_filters.get('search_name')}**" if st.session_state.loaded_filters.get('search_name') else ""))
        
        display_grades_radio(st.session_state.grades_df,new_curriculum)
    elif st.session_state.grades_df is not None and st.session_state.grades_df.empty:
        st.warning("No students found matching the current filters.")
    else:
        st.info("👆 Select your filters and click 'Load Grades' to view student data.")