import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.pdf_helper import generate_pdf
from pages.Registrar.dash_registrar_old_tab1 import show_registrar_tab1_info
from pages.Registrar.dash_registrar_old_tab2 import show_registrar_tab2_info
from pages.Registrar.dash_registrar_old_tab3 import show_registrar_tab3_info
from pages.Registrar.dash_registrar_old_tab4 import show_registrar_tab4_info
from pages.Registrar.dash_registrar_old_tab5 import show_registrar_tab5_info
from pages.Registrar.dash_registrar_old_tab6 import show_registrar_tab6_info

from pages.Registrar.dash_registrar_new_tab1 import show_registrar_new_tab1_info
from pages.Registrar.dash_registrar_new_tab2 import show_registrar_new_tab2_info
from pages.Registrar.dash_registrar_new_tab3 import show_registrar_new_tab3_info
from pages.Registrar.dash_registrar_new_tab4 import show_registrar_new_tab4_info
from pages.Registrar.dash_registrar_new_tab5 import show_registrar_new_tab5_info
from pages.Registrar.dash_registrar_new_tab6 import show_registrar_new_tab6_info
from pages.Registrar.dash_registrar_new_tab7 import show_registrar_new_tab7_info
from pages.Registrar.dash_registrar_new_tab8 import show_registrar_new_tab8_info
from pages.Registrar.dash_registrar_new_tab9 import show_registrar_new_tab9_info
from pages.Registrar.dash_registrar_new_tab10 import show_registrar_new_tab10_info
from pages.Registrar.dash_registrar_new_tab11 import show_registrar_new_tab11_info
import time
import json

# Paths to Pickle Files
students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"
curriculums_cache = "pkl/curriculums.pkl"

@st.cache_data(ttl=300)
def load_all_data():
    """Load all data with performance optimization"""
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Always coerce to DataFrame using pkl_data_to_df to avoid list objects
        futures = {
            'students': executor.submit(pkl_data_to_df, students_cache),
            'grades': executor.submit(pkl_data_to_df, grades_cache),
            'semesters': executor.submit(pkl_data_to_df, semesters_cache),
            'subjects': executor.submit(pkl_data_to_df, subjects_cache),
            'teachers': executor.submit(pkl_data_to_df, teachers_cache)
        }
        
        data = {}
        for key, future in futures.items():
            data[key] = future.result()

        # Ensure YearLevel is scalar in students_df
        if 'students' in data and not data['students'].empty and 'YearLevel' in data['students'].columns:
            data['students']["YearLevel"] = data['students']["YearLevel"].apply(lambda x: x[0] if isinstance(x, list) and x else x)
    
    load_time = time.time() - start_time
    st.success(f"📊 Data loaded in {load_time:.2f} seconds")
    
    # Log ingestion results
    log_data = {
        'timestamp': time.time(),
        'load_time_seconds': load_time,
        'records_loaded': {
            'students': len(data['students']),
            'grades': len(data['grades']),
            'semesters': len(data['semesters']),
            'subjects': len(data['subjects']),
            'teachers': len(data['teachers'])
        }
    }
    
    # Save log to cache directory
    os.makedirs('cache', exist_ok=True)
    with open('cache/ingestion_log.json', 'w') as f:
        json.dump(log_data, f, indent=2)
    
    return data

# New loader for updated pickle sources (only used by the NEW dashboard)
@st.cache_data(ttl=300)
def load_all_data_new():
    """Load all data using the new pickle files for students, grades, and subjects."""
    start_time = time.time()

    new_students_path = "pkl/new_students.pkl"
    new_grades_path = "pkl/new_grades.pkl"
    new_subjects_path = "pkl/new_subjects.pkl"
    new_teachers_path = "pkl/new_teachers.pkl"

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            'students': executor.submit(pkl_data_to_df, new_students_path),
            'grades': executor.submit(pkl_data_to_df, new_grades_path),
            'semesters': executor.submit(pkl_data_to_df, semesters_cache),
            'subjects': executor.submit(pkl_data_to_df, new_subjects_path),
            'teachers_new': executor.submit(pkl_data_to_df, new_teachers_path),
        }

        data = {}
        for key, future in futures.items():
            data[key] = future.result()

    # Choose teachers source: prefer new_teachers, else old, else infer
    teachers_new_df = data.get('teachers_new') if isinstance(data.get('teachers_new'), pd.DataFrame) else pd.DataFrame()
    teachers_old_df = data.get('teachers_old') if isinstance(data.get('teachers_old'), pd.DataFrame) else pd.DataFrame()
    teachers_df = pd.DataFrame()
    if not teachers_new_df.empty:
        teachers_df = teachers_new_df
    elif not teachers_old_df.empty:
        teachers_df = teachers_old_df
    else:
        # Infer from subjects or grades if possible
        subjects_df = data.get('subjects', pd.DataFrame())
        grades_df = data.get('grades', pd.DataFrame())
        inferred = pd.DataFrame()
        if 'Teacher' in subjects_df.columns:
            inferred = pd.DataFrame({
                'Teacher': subjects_df['Teacher'].dropna().unique().tolist()
            })
            inferred['_id'] = inferred['Teacher']
        elif 'Teachers' in grades_df.columns:
            # explode teachers from grades
            tmp = grades_df[['Teachers']].copy()
            tmp = tmp[tmp['Teachers'].notna()]
            tmp = tmp.explode('Teachers') if tmp['Teachers'].apply(lambda x: isinstance(x, list)).any() else tmp
            inferred = pd.DataFrame({'_id': tmp['Teachers'].dropna().astype(str).unique().tolist()})
            inferred['Teacher'] = inferred['_id']
        teachers_df = inferred

    data['teachers'] = teachers_df

    load_time = time.time() - start_time
    st.success(f"📊 Data (new) loaded in {load_time:.2f} seconds")

    # Log ingestion results
    log_data = {
        'timestamp': time.time(),
        'load_time_seconds': load_time,
        'records_loaded': {
            'students_new': len(data['students']),
            'grades_new': len(data['grades']),
            'semesters': len(data['semesters']),
            'subjects_new': len(data['subjects']),
            'teachers': len(data['teachers'])
        }
    }

    os.makedirs('cache', exist_ok=True)
    with open('cache/ingestion_log.json', 'w') as f:
        json.dump(log_data, f, indent=2)

    return data


def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def export_to_pdf(df, filename):
    """Export DataFrame to PDF (placeholder)"""
    print(f"PDF export not implemented. Data: {df.head()}")

def show_registrar_dashboard_old():
    """Original dashboard implementation"""
    # st.markdown("# 📋 Registrar's Office Dashboard")
    # st.markdown("Comprehensive academic performance analytics and student management system")
    
    # Load all data with performance optimization
    with st.spinner("Loading data..."):
        data = load_all_data()
    
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']
    teachers_df = data['teachers']


    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Academic Standing", 
        "📈 Pass/Fail Distribution", 
        "📉 Enrollment Trends", 
        "⚠️ Incomplete Grades", 
        "🔄 Retention & Dropout", 
        "🏆 Top Performers"
    ])

    with tab1:
        show_registrar_tab1_info(data, students_df, semesters_df)
    with tab2:
        show_registrar_tab2_info(data, students_df, semesters_df)
    with tab3:
        show_registrar_tab3_info(data, students_df, semesters_df)
    with tab4:
        show_registrar_tab4_info(data, students_df, semesters_df, teachers_df)
    with tab5:
        show_registrar_tab5_info(data, students_df, semesters_df)
    with tab6:
        show_registrar_tab6_info(data, students_df, semesters_df)

def show_registrar_dashboard_new():
    """Simplified dashboard implementation with 5 tabs including teacher grade analysis"""

    # Use session state for version toggle
    use_new_version = st.session_state.get('use_new_version', True)

    if not use_new_version:
        show_registrar_dashboard_old()
        st.stop()

    # ✅ Inject CSS to make tabs horizontally scrollable and fit screen
    st.markdown(
        """
        <style>
        /* --- Tab list: target Streamlit's tab container --- */
        div[data-baseweb="tab-list"],
        div[role="tablist"],
        section[data-testid="stHorizontalBlock"] > div {
            display: flex !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            gap: 8px;
            padding: 6px 8px;
            white-space: nowrap;
            scrollbar-width: thin;
            scroll-behavior: smooth;
            box-sizing: border-box;
            width: 100%;
        }

        /* --- Individual tabs: prevent wrapping and allow horizontal scroll --- */
        div[data-baseweb="tab"],
        button[data-baseweb="tab"],
        [role="tab"] {
            flex: 0 0 auto !important;
            min-width: 130px;
            max-width: 280px;
            box-sizing: border-box;
            text-overflow: ellipsis;
            overflow: hidden;
            white-space: nowrap;
            padding: 8px 12px;
        }

        /* Ensure Streamlit main container doesn't overflow horizontally */
        .block-container, .main {
            max-width: 100% !important;
        }

        /* Small-screen adjustments */
        @media (max-width: 900px) {
            div[data-baseweb="tab"], button[data-baseweb="tab"], [role="tab"] {
                min-width: 110px;
            }
        }

        /* Optional: visible scrollbar for webkit browsers */
        div[data-baseweb="tab-list"]::-webkit-scrollbar {
            height: 8px;
        }
        div[data-baseweb="tab-list"]::-webkit-scrollbar-thumb {
            border-radius: 8px;
            background: rgba(0,0,0,0.18);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Load all data with performance optimization (NEW sources)
    with st.spinner("Loading data..."):
        data = load_all_data_new()

    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']
    teachers_df = data['teachers']

    # Tabs navigation (scrollable)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
        "👥 Class List",
        "📝 Evaluation Form (LO2)",
        "📚 Curriculum Viewer",
        "📈 Grades per Teacher (LO1)",
        "👨‍🏫 Teacher Analysis",
        "📊 Academic Standing",
        "📈 Pass/Fail Distribution",
        "📉 Enrollment Trends",
        "⚠️ Incomplete Grades",
        "🔄 Retention & Dropout",
        "🏆 Top Performers"
    ])

    with tab1:
        show_registrar_new_tab1_info(data, students_df, semesters_df, teachers_df)
    with tab2:
        show_registrar_new_tab2_info(data, students_df, semesters_df, teachers_df)
    with tab3:
        show_registrar_new_tab3_info(data, students_df, semesters_df, grades_df)
    with tab4:
        show_registrar_new_tab4_info(data, students_df, semesters_df, teachers_df, grades_df)
    with tab5:
        show_registrar_new_tab5_info(data, students_df, semesters_df, teachers_df)
    with tab6:
        show_registrar_new_tab6_info(data, students_df, semesters_df)
    with tab7:
        show_registrar_new_tab7_info(data, students_df, semesters_df)
    with tab8:
        show_registrar_new_tab8_info(data, students_df, semesters_df)
    with tab9:
        show_registrar_new_tab9_info(data, students_df, semesters_df, teachers_df)
    with tab10:
        show_registrar_new_tab10_info(data, students_df, semesters_df)
    with tab11:
        show_registrar_new_tab11_info(data, students_df, semesters_df)
def show_registrar_dashboard():
    """Main dashboard function - defaults to new version with toggle"""
    show_registrar_dashboard_new()

if __name__ == "__main__":
    show_registrar_dashboard()