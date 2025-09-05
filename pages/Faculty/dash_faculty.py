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


current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')


def show_faculty_dashboard():
    
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="🏫",
        layout="wide"
    )
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Class Grade Distribution",
        "📈 Student Progress Tracker",
        "📚 Subject Difficulty Heatmap",
        "👥 Intervention Candidates List",
        "⏳ Grade Submission Status",
        "🔍 Custom Query Builder"
    ])

    with tab1:
        st.subheader("📋 Class Grade Distribution")
        show_faculty_tab1_info()
    with tab2:
        st.subheader("📈 Student Progress Tracker")
        show_faculty_tab2_info()  

    with tab3:
        st.subheader("📚 Subjects with Highest Failure Rates")
        show_faculty_tab3_info()  
    with tab4:
        st.subheader("👥 Intervention Candidates List")
        show_faculty_tab4_info()  
    with tab5:
        st.subheader("⏳ Grade Submission Status")
        show_faculty_tab5_info()  
    with tab6:
        st.subheader("🔍 Custom Query Builder")
        show_faculty_tab6_info()  
    

if __name__ == "__main__":
    show_faculty_dashboard()