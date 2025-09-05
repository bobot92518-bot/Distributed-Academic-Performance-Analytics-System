import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import pkl_data_to_df, subjects_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list, get_students_from_grades
from pages.Faculty.faculty_pdf_generator import generate_student_grades_report_pdf

current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')



def get_student_curriculum(student_id):
    """
    Fetch all grades for a given student across all semesters using pandas.
    Returns a DataFrame with columns:
    Semester, SchoolYear, Subject Code, Subject Description, Units, Teacher, Grade
    """
    
    
    

def show_faculty_tab6_info():
    
    st.title("Additional Filtered Queries.")
    
    with st.form(key="queries_search_form"):
        st.subheader("📋 Students (Paginated, 10 per page with single selection)")
        search_name = ""
        search_name = st.text_input("🔍 Search student by name", key="queries_search").strip()
        search_button = st.form_submit_button("Search",  key="queries_searchbutton")
    

