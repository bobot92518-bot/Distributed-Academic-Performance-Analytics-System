import streamlit as st
from datetime import datetime
import pandas as pd
import os
from global_utils import load_pkl_data
from pages.Faculty.dash_faculty_tab1 import show_faculty_tab1_info
from pages.Faculty.dash_faculty_tab2 import show_faculty_tab2_info


def show_faculty_metrics():
    """Display faculty dashboard metrics"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            label="📚 Active Subjects",
            value="5",
            delta="2",
            help="Number of subjects currently teaching"
        )
    
    with col2:
        st.metric(
            label="👥 Total Students", 
            value="127",
            delta="15",
            help="Total students across all subjects"
        )

def show_recent_activities():
    """Display recent faculty activities"""
    st.markdown("### 📋 Recent Activities")
    
    activities = [
        {
            "date": "2024-08-30",
            "activity": "Graded Quiz 3 for Computer Science 101",
            "details": "23 submissions graded",
            "status": "✅ Completed"
        },
        {
            "date": "2024-08-29", 
            "activity": "Updated syllabus for Mathematics 201",
            "details": "Added new reference materials",
            "status": "✅ Completed"
        },
        {
            "date": "2024-08-28",
            "activity": "Created Assignment 4 for Physics 301",
            "details": "Due date: September 5, 2024",
            "status": "📝 Published"
        },
        {
            "date": "2024-08-27",
            "activity": "Submitted final grades for Summer term",
            "details": "All grades submitted to registrar",
            "status": "✅ Completed"
        }
    ]
    
    for activity in activities:
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.write(f"**{activity['date']}**")
            
            with col2:
                st.write(f"**{activity['activity']}**")
                st.caption(activity['details'])
            
            with col3:
                st.write(activity['status'])
        
        st.divider()

def show_quick_actions():
    """Display quick action buttons for faculty"""
    st.markdown("### 🚀 Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📝 Create Assignment", use_container_width=True, key="create_assignment"):
            st.info("🚧 Assignment creation feature coming soon!")
    
    with col2:
        if st.button("📊 Grade Students", use_container_width=True, key="grade_students"):
            st.info("🚧 Student grading feature coming soon!")
    
    with col3:
        if st.button("👥 View Class Roster", use_container_width=True, key="class_roster"):
            st.info("🚧 Class roster feature coming soon!")
    
    with col4:
        if st.button("📈 Analytics", use_container_width=True, key="analytics"):
            st.info("🚧 Analytics dashboard coming soon!")


def show_upcoming_deadlines():
    """Display upcoming deadlines and important dates"""
    st.markdown("### 📅 Upcoming Deadlines")
    
    deadlines = [
        {"date": "2024-09-02", "event": "Submit CS 101 Quiz 4 grades", "priority": "🔴 High"},
        {"date": "2024-09-05", "event": "CS 301 Assignment 4 due", "priority": "🟡 Medium"},
        {"date": "2024-09-10", "event": "Midterm exam preparation", "priority": "🟠 High"},
        {"date": "2024-09-15", "event": "Faculty meeting", "priority": "🟢 Normal"},
    ]
    
    for deadline in deadlines:
        with st.container():
            col1, col2, col3 = st.columns([2, 4, 1])
            
            with col1:
                st.write(f"**{deadline['date']}**")
            
            with col2:
                st.write(deadline['event'])
            
            with col3:
                st.write(deadline['priority'])
        
        st.divider()


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
        st.subheader("📚 Subject Difficulty Heatmap")

    with tab4:
        st.subheader("👥 Intervention Candidates List")

    with tab5:
        st.subheader("⏳ Grade Submission Status")

    with tab6:
        st.subheader("🔍 Custom Query Builder")

    

if __name__ == "__main__":
    show_faculty_dashboard()