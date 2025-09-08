import streamlit as st
import altair as alt
import pandas as pd 
import matplotlib.pyplot as plt
from global_utils import load_pkl_data, pkl_data_to_df, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

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
        1: "| &nbsp; &nbsp; 1st Year Subject",
        2: "| &nbsp; &nbsp; 2nd Year Subject",
        3: "| &nbsp; &nbsp; 3rd Year Subject",
        4: "| &nbsp; &nbsp; 4th Year Subject",
        5: "| &nbsp; &nbsp; 5th Year Subject",
    }
    
    # Group by semester and subject
    for (semester, school_year, subject_code, subject_desc, SubjectYearLevel), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel']
    ):
        with st.expander(f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code} &nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc} &nbsp;&nbsp; {subject_year_map.get(SubjectYearLevel, "")}", expanded=True):
            
            table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
            table_data.columns = ['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade']
            
            table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
            table_data['Student ID'] = table_data['Student ID'].astype(str)
            course_column = ""
            year_column = ""
            if is_new_curriculum:
                year_column = "Year Taken"
                table_data[f"{year_column}"] = year_map.get(SubjectYearLevel, "")
                course_column = "Year-Course"
                table_data[f"{course_column}"] = (table_data["Year Level"].map(year_map).fillna("") + " - " + table_data["Course"])
            else:
                course_column = "Course"
                year_column = "Year Level"
                table_data[f"{year_column}"] = table_data["Year Level"].map(year_map).fillna("")
            # table_data['Year Level'] = table_data['Year Level'].map(year_map).fillna(table_data['Year Level'].astype(str))
            def pass_fail(g):
                if pd.isna(g) or g == 0:
                    return "Not Set"
                return "Passed" if g >= 75 else "Failed"

            table_data['Pass/Fail'] = table_data['Grade_num'].apply(pass_fail)
            # table_data['Pass/Fail'] = table_data['Grade_num'].apply(lambda g: 'Passed' if g >= 75 else 'Failed')
            def grade_with_star(grade):
                if pd.isna(grade) or grade == 0:
                    return "Not Set"
                else:
                    if grade < 75:
                        return f"🛑 {grade}"
                    else:
                        return f"⭐ {grade}"   

            table_data['Grade'] = table_data['Grade_num'].apply(grade_with_star)
            display_df = table_data[['Student ID', 'Student Name', f"{course_column}", f"{year_column}", 'Grade', 'Pass/Fail']]
            
            def color_status(val):
                if val == 'Passed':
                    return 'color: green'
                elif val == 'Failed':
                    return 'color: red'
                else:
                    return 'color: gray'
            styled_df = (display_df.style.applymap(color_status, subset=['Pass/Fail']))
            # Final display

            # Quick stats
            valid_grades = table_data["Grade_num"][
                (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
            ]

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Students", len(table_data))
            with col2:
                st.metric("Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "Not Set")
            with col3:
                st.metric("Class Median", f"{valid_grades.median():.1f}" if not valid_grades.empty else "Not Set")
            with col4:
                st.metric("Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "Not Set")
            with col5:
                st.metric("Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "Not Set")

            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.markdown("**Grades Summary**")
            freq_data = table_data["Grade_num"].value_counts().reset_index()
            freq_data.columns = ["Grade", "Frequency"]

            freq_data["Grade Status"] = freq_data["Grade"].apply(
                lambda g: "Not Set" if pd.isna(g) or g == 0
                else ("Pass" if g >= 75 else "Fail")
            )


            chart2 = (
                alt.Chart(freq_data)
                .mark_bar()
                .encode(
                    x=alt.X("Grade:O", title="Grades", sort="ascending"),
                    y=alt.Y("Frequency:Q", title="Number of Students"),
                    color=alt.Color(
                        "Grade Status",
                        title="Grade Status",
                        scale=alt.Scale(
                            domain=["Pass", "Fail"],
                            range=["green", "red"]
                        )
                    ),
                    tooltip=["Grade", "Frequency"]
                )
            )

            st.altair_chart(chart2, use_container_width=True)
            
            
            st.divider()
            st.markdown("**Pass vs. Fail**")
            table_data["Grade Status"] = table_data["Grade_num"].apply(
                lambda g: "Not Set" if pd.isna(g) or g == 0
                else ("Pass" if g >= 75 else "Fail")
            )
            pass_fail_data = table_data["Grade Status"].value_counts().reset_index()
            pass_fail_data.columns = ["Grade Status", "Number of Students"]

            # Bar chart
            bars = (
                alt.Chart(pass_fail_data)
                .mark_bar()
                .encode(
                    x=alt.X("Grade Status:N", title="Grade Category", sort=["Pass", "Fail", "Not Set"]),
                    y=alt.Y("Number of Students:Q", title="Number of Students"),
                    color=alt.Color(
                        "Grade Status",
                        scale=alt.Scale(
                            domain=["Pass", "Fail", "Not Set"],
                            range=["green", "red", "gray"]
                        )
                    ),
                    tooltip=["Grade Status", "Number of Students"]
                )
            )

            # Text labels on top of bars
            labels = (
                alt.Chart(pass_fail_data)
                .mark_text(dy=-10, fontSize=14, color="black")
                .encode(
                    x="Grade Status:N",
                    y="Number of Students:Q",
                    text="Number of Students:Q"
                )
            )

            chart3 = bars + labels

            st.altair_chart(chart3, use_container_width=True)
            
            st.divider()
            st.markdown("**Pass vs. Fail (Pie Chart)**")
            
            pie = (
                alt.Chart(pass_fail_data)
                .mark_arc(innerRadius=0) 
                .encode(
                    theta=alt.Theta("Number of Students:Q", title=""),
                    color=alt.Color(
                        "Grade Status:N",
                        scale=alt.Scale(
                            domain=["Pass", "Fail", "Not Set"],
                            range=["green", "red", "gray"]
                        ),
                        legend=alt.Legend(title="Grade Status")
                    ),
                    tooltip=["Grade Status", "Number of Students"]
                )
            )

            st.altair_chart(pie, use_container_width=True)

def show_faculty_tab2_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
    col1, col2 = st.columns([1, 1])
    
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab2_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab2_subject"
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
            
    if st.button("📊 Load Class", type="secondary", key="tab2_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            else:
                results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
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