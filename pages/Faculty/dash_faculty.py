import streamlit as st
from datetime import datetime
import pandas as pd
import os
from global_utils import load_pkl_data
from pages.Faculty.dash_faculty_tab1 import show_faculty_tab1_info
from pages.Faculty.dash_faculty_tab2 import show_faculty_tab2_info
from pages.Faculty.dash_faculty_tab3 import show_faculty_tab3_info
from pages.Faculty.dash_faculty_tab4 import show_faculty_tab4_info
from pages.Faculty.dash_faculty_tab5 import show_faculty_tab5_info
from pages.Faculty.dash_faculty_tab6 import show_faculty_tab6_info
from pages.Faculty.dash_faculty_tab7 import show_faculty_tab7_info
from global_utils import new_subjects_cache, pkl_data_to_df, curriculums_cache


current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def get_active_curriculum(new_curriculum):
    if new_curriculum:
        curriculum_df = pkl_data_to_df(curriculums_cache)

        if curriculum_df is None or curriculum_df.empty:
            return ""

        curriculum_df = curriculum_df.sort_values("curriculumYear", ascending=False).head(1)
        return f"&nbsp;&nbsp; | &nbsp;&nbsp; School Year: {curriculum_df["curriculumYear"].iloc[0]}"
    else:
        return ""
if "active_load" not in st.session_state:
        st.session_state.active_load = None
        
def show_faculty_dashboard():
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    """Main faculty dashboard function with toggle between old and new implementations"""

    new_subjects_df = pkl_data_to_df(new_subjects_cache)
    new_curriculum = not (new_subjects_df[new_subjects_df["Teacher"] == current_faculty].empty)

    
    label = "📗 New Curriculum &nbsp; &nbsp; | &nbsp; &nbsp; School Year 2022 - 2023" if new_curriculum else "📙 Old Curriculum"
    st.write(f"Currently showing: **{label}**")
    
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="🏫",
        layout="wide"
    )
    
    # data_query_label = f"{"🔍 Data Query (LO2)" if new_curriculum else "🔍 Data Query"}"
    data_query_label = f"{""}"
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📋 Class List",
        "📈 Student Tracker",
        "📚 Subject Difficulty",
        "👥 At-Risk List",
        "⏳ Grade Status",
        "🔍 Data Query",
        "📑 Grade Analytics"
    ])

    with tab1:
        st.subheader("📋 Class Grade Distribution")
        show_faculty_tab1_info(new_curriculum)
    with tab2:
        st.subheader("📈 Student Progress Tracker")
        show_faculty_tab2_info(new_curriculum)  
    with tab3:
        st.subheader("📚 Subjects with Highest Failure Rates")
        show_faculty_tab3_info(new_curriculum)  
    with tab4:
        st.subheader("👥 Students at Risk Based on Current Semester Performance")
        show_faculty_tab4_info(new_curriculum)  
    with tab5:
        st.subheader(f"⏳ Grade Submission Status {get_active_curriculum(new_curriculum)}")
        show_faculty_tab5_info(new_curriculum)  
    with tab6:
        st.subheader("🔍 Custom Query Builder")
        show_faculty_tab6_info(new_curriculum)  
    with tab7:
        st.subheader("🔍 Students Grade Analytics (LO1)")
        show_faculty_tab7_info(new_curriculum)  

if __name__ == "__main__":
    show_faculty_dashboard()