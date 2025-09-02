import streamlit as st
from datetime import datetime
import pandas as pd 
import os
from global_utils import load_pkl_data, students_cache, grades_cache, semesters_cache, subjects_cache, teachers_cache

current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')


def show_faculty_tab1_info():
    grades_df = pd.DataFrame(load_pkl_data(grades_cache))
    semesters_df = pd.DataFrame(load_pkl_data(semesters_cache))
    subjects_df = pd.DataFrame(load_pkl_data(subjects_cache))
    
    faculty_subjects = subjects_df[subjects_df["Teacher"] == current_faculty]
    if faculty_subjects.empty:
        st.warning("No subjects assigned to you.")
        return
    
    grades_df = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])

    faculty_grades = grades_df[grades_df["Teachers"] == current_faculty]
    
    if faculty_grades.empty:
        st.info("No grades available for your subjects.")
        return
    

    merged_df = pd.merge(faculty_grades, faculty_subjects, left_on="SubjectCodes", right_on="_id", how="inner")
    
 
    semesters_df["SemesterYear"] = semesters_df["Semester"] + " " + semesters_df["SchoolYear"].astype(str)
    semester_options = semesters_df["SemesterYear"].unique()
    selected_semester = st.selectbox("Select Semester", semester_options)
    
    
    sem, year = selected_semester.split()
    semester_ids = semesters_df[(semesters_df["Semester"] == sem) & (semesters_df["SchoolYear"] == year)]["_id"].tolist()
    merged_df = merged_df[merged_df["SemesterID"].isin(semester_ids)]
    
    if merged_df.empty:
        st.info("No grades found for the selected semester.")
        return
    

    subject_options = merged_df["Description"].unique()
    selected_subject = st.selectbox("Select Subject", subject_options)
    

    subject_grades = merged_df[merged_df["Description"] == selected_subject]["Grades"]
    

    if not subject_grades.empty:
        st.bar_chart(subject_grades.value_counts().sort_index())
        st.write("Grades for", selected_subject)
        st.dataframe(subject_grades)
    else:
        st.info("No grades available for this subject in the selected semester.")