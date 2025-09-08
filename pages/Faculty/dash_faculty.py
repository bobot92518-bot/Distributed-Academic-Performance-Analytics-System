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
from global_utils import new_subjects_cache, pkl_data_to_df


current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def show_faculty_dashboard_old():
    """Original faculty dashboard implementation"""
    

def show_faculty_dashboard_new():
    """Enhanced faculty dashboard implementation with simplified tabs"""
    # Add version indicator
    st.info("🆕 **New Curriculum** - Previews Records from the New Curriculum")
    
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="🏫",
        layout="wide"
    )
    
    # Simplified tabs for new version
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Class List",
        "👥 Evaluation Sheet", 
        "📈 Curriculum Viewer",
        "👨‍🏫 Teacher Analysis"
    ])

    with tab1:
        st.subheader("📊 Class List")
        st.markdown("This is Sample tab for New Version")
        
    with tab2:
        st.subheader("👥 Evaluation Sheet")
        st.markdown("This is Sample tab for New Version")
        
    with tab3:
        st.subheader("📈 Curriculum Viewer")
        st.markdown("This is Sample tab for New Version")
      
        
    with tab4:
        st.subheader("👨‍🏫 Teacher Analysis")
        st.markdown("This is Sample tab for New Version")

def show_faculty_dashboard():
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    """Main faculty dashboard function with toggle between old and new implementations"""
    # Add toggle at the top left
    # col1, col2 = st.columns([3, 1])
    # with col1:
    #     new_curriculum = st.toggle(
    #         "📘 Curriculum Mode", 
    #         value=True,
    #         help="Switch between the old curriculum and the new curriculum"
    #     )
    new_subjects_df = pkl_data_to_df(new_subjects_cache)
    new_curriculum = not (new_subjects_df[new_subjects_df["Teacher"] == current_faculty].empty)
    print(current_faculty)
    print(new_curriculum)
    
    label = "📗 New Curriculum &nbsp; &nbsp; | &nbsp; &nbsp; School Year 2022 - 2023" if new_curriculum else "📙 Old Curriculum"
    st.write(f"Currently showing: **{label}**")
    # Call the appropriate version based on toggle
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="🏫",
        layout="wide"
    )
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Class List",
        "📈 Class Analysis (LO1)",
        "📚 Subject Difficulty",
        "👥 At-Risk List",
        "⏳ Grade Status",
        "🔍 Data Query"
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
        st.subheader("⏳ Grade Submission Status")
        show_faculty_tab5_info(new_curriculum)  
    with tab6:
        st.subheader("🔍 Custom Query Builder")
        show_faculty_tab6_info(new_curriculum)  

if __name__ == "__main__":
    show_faculty_dashboard()