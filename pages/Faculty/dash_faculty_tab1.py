import streamlit as st
import pandas as pd 
from global_utils import load_pkl_data, students_cache, grades_cache, semesters_cache, subjects_cache
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher

current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')


def get_student_grades_by_subject_and_semester( semester_id=None, subject_code=None):
    """Retrieve all student grades for subjects taught by a specific teacher in a given semester"""
    try:
        # Load datasets
        grades_data = load_pkl_data(grades_cache)
        students_data = load_pkl_data(students_cache)
        subjects_data = load_pkl_data(subjects_cache)
        semesters_data = load_pkl_data(semesters_cache)

        # Convert to DataFrames if needed
        grades_df = pd.DataFrame(grades_data) if isinstance(grades_data, list) else grades_data
        students_df = pd.DataFrame(students_data) if isinstance(students_data, list) else students_data
        subjects_df = pd.DataFrame(subjects_data) if isinstance(subjects_data, list) else subjects_data
        semesters_df = pd.DataFrame(semesters_data) if isinstance(semesters_data, list) else semesters_data

        if grades_df.empty:
            return []

        # Expand SubjectCodes + Grades + Teachers into rows
        grades_expanded = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])

        # Filter by teacher
        grades_expanded = grades_expanded[grades_expanded["Teachers"] == current_faculty]

        # Optional filters
        if semester_id:
            grades_expanded = grades_expanded[grades_expanded["SemesterID"] == semester_id]
        if subject_code:
            grades_expanded = grades_expanded[grades_expanded["SubjectCodes"] == subject_code]

        if grades_expanded.empty:
            st.warning("No grades available")
        # Join with students, subjects, semesters
        merged = (
            grades_expanded
            .merge(students_df, left_on="StudentID", right_on="_id", suffixes=("", "_student"))
            .merge(subjects_df, left_on="SubjectCodes", right_on="_id", suffixes=("", "_subject"))
            .merge(semesters_df, left_on="SemesterID", right_on="_id", suffixes=("", "_semester"))
        )

        # Select relevant columns
        results = merged[[
            "Semester", "SchoolYear", "SubjectCodes", "Description", "Units", "Name", "Grades"
        ]].rename(columns={
            "Semester": "semester",
            "SchoolYear": "schoolYear",
            "SubjectCodes": "subjectCode",
            "Description": "subjectDescription",
            "Units": "units",
            "Name": "studentName",
            "Grades": "grade"
        })

        # Sort like Mongo pipeline
        results = results.sort_values(
            by=["schoolYear", "semester", "subjectCode", "studentName"],
            ascending=[False, True, True, True]
        )

        return results.to_dict("records")

    except Exception as e:
        st.error(f"Error querying grades: {e}")
        return []


def create_grades_dataframe(results):
    """Convert results to pandas DataFrame"""
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    return df

def display_grades_table(df, semester_filter = None, subject_filter = None):
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
    
    # Group by semester and subject
    for (semester, school_year, subject_code, subject_desc, units), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'units']
    ):
        with st.expander(f"{semester} - {school_year}   |   {subject_code} - {subject_desc}", expanded=True):
            # Create table
            table_data = group[['studentName', 'grade']].copy()
            table_data.columns = ['Student', 'Grade']
            table_data['Grade_num'] = table_data['Grade']  # numeric
            table_data['Grade'] = table_data['Grade'].astype(str)  # string for left-alignment
            # Add Status column
            table_data['Status'] = table_data['Grade_num'].apply(lambda g: 'Passed' if g >= 75 else 'Failed')
            display_df = table_data[['Student', 'Grade', 'Status']]
            # Function to color the Status column
            def color_status(val):
                if val == 'Passed':
                    return 'color: green; font-weight: bold'
                else:
                    return 'color: darkred; font-weight: bold'
            
            # Apply styling
            styled_df = (display_df.style.applymap(color_status, subset=['Status']))
            
            # Display responsive table without index
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Quick stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Students", len(table_data))
            with col2:
                st.metric("Average", f"{table_data['Grade_num'].mean():.1f}")
            with col3:
                st.metric("Highest", f"{table_data['Grade_num'].max()}")
            with col4:
                st.metric("Lowest", f"{table_data['Grade_num'].min()}")
            
            st.markdown("**Grade Distribution**")
            chart_data = table_data.set_index('Student')
            st.bar_chart(chart_data['Grade_num'], use_container_width=True)
            
            #USING MATPLOTLIB
            # grades = table_data['Grade']
            # students = table_data['Student']
            # colors = ['green' if g >= 75 else 'red' for g in grades]

            # fig, ax = plt.subplots(figsize=(max(6, len(students)*0.6), 4))  # Adjust width based on #students
            # ax.bar(students, grades, color=colors)
            # ax.set_ylabel("Grade")
            # ax.set_xlabel("Student")
            # ax.set_ylim(0, 100)
            # ax.set_title("Grade Distribution")
            # plt.xticks(rotation=45, ha='right')  # Rotate names for readability
            # plt.tight_layout()
            
            # st.pyplot(fig)

def show_faculty_tab1_info():

    semesters = get_semesters_list()
    subjects = get_subjects_by_teacher(current_faculty)
    
    col1, col2 = st.columns([1, 1])
    
    
    with col1:
        semester_options = [" - All Semesters - "] + [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="main_semester"
        )
    with col2:
        subject_options = [" - All Subjects - "] + [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="main_subject"
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
            
    if st.button("📊 Load Grades", type="secondary"):
        with st.spinner("Loading grades data..."):
            
            results = get_student_grades_by_subject_and_semester(selected_semester_id, selected_subject_code)
            
            if results:
                df = create_grades_dataframe(results)
                
                # Store in session state for other tabs
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                
                # Display results
                st.success(f"Found {len(results)} grade records for {current_faculty}")
                
                display_grades_table(df, selected_semester_display, selected_subject_display)
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")