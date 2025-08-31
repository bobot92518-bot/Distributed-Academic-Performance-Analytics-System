import streamlit as st
from datetime import datetime
import pandas as pd

def check_faculty_auth():
    """Check if user is authenticated and has faculty role"""
    if ('authenticated' not in st.session_state or 
        not st.session_state.authenticated or 
        st.session_state.role != "faculty"):
        st.error("🚫 Unauthorized access. Please login as Faculty.")
        
        # Provide login button
        if st.button("🔑 Go to Login"):
            st.session_state.clear()
            try:
                st.switch_page("app.py")
            except:
                st.rerun()
        st.stop()

def get_faculty_name():
    """Get faculty display name from session data"""
    user_data = st.session_state.get('user_data', {})
    username = st.session_state.get('username', 'Faculty')
    
    # Try to get full name
    first_name = user_data.get('first_name', '')
    last_name = user_data.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()
    
    return full_name if full_name else username

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

def show_current_subjects():
    """Display current subjects being taught"""
    st.markdown("### 📚 Current Subjects")
    
    # Sample subjects data
    subjects_data = [
        {
            "Subject Code": "CS 101",
            "Subject Name": "Introduction to Computer Science",
            "Students": 45,
            "Schedule": "MWF 9:00-10:00 AM",
            "Room": "Lab 201",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 201", 
            "Subject Name": "Data Structures",
            "Students": 32,
            "Schedule": "TTh 2:00-3:30 PM",
            "Room": "Room 305",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 301",
            "Subject Name": "Database Systems",
            "Students": 28,
            "Schedule": "MWF 11:00-12:00 PM", 
            "Room": "Lab 102",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 401",
            "Subject Name": "Software Engineering",
            "Students": 22,
            "Schedule": "TTh 10:00-11:30 AM",
            "Room": "Room 401",
            "Status": "🟡 Planning"
        }
    ]
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(subjects_data)
    
    # Display as interactive table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Students": st.column_config.NumberColumn(
                "Students",
                help="Number of enrolled students",
                format="%d 👥"
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="Current status of the subject"
            )
        }
    )

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

def show_faculty_dashboard():
    """Main faculty dashboard display function"""
    # Check authentication first
    check_faculty_auth()
    
    # Page configuration
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="👨‍🏫",
        layout="wide"
    )
    
    # Get faculty name
    faculty_name = get_faculty_name()
    
    # Header
    st.title("👨‍🏫 Faculty Dashboard")
    st.markdown(f"### Welcome back, **{faculty_name}**! 👋")
    st.markdown(f"*Last login: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*")
    
    st.markdown("---")
    
    # Main metrics
    show_faculty_metrics()
    
    st.markdown("---")
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Overview", "📚 Subjects", "🏆 Grades", "🎓 Students"])

    with tab1:
        st.subheader("📋 Overview")
        st.write("General summary of students, faculty, and registrar activity.")

    with tab2:
        st.subheader("📚 Subjects")
        st.write("List of subjects, descriptions, and assigned teachers.")
        show_current_subjects()

    with tab3:
        st.subheader("🏆 Grades")
        st.write("Student grades and performance analytics.")

    with tab4:
        st.subheader("🎓 Students")
        st.write("Manage student records, profiles, and enrollment.")
    
    if st.button("Logout"):
        """Handle user logout"""
        # Store logout message before clearing session
        logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
        
        # Clear all session state
        st.session_state.clear()
        
        # Show logout message
        st.success(logout_message)
        st.info("Redirecting to login page...")
        
        # Brief delay for user feedback
        import time
        time.sleep(3)
        
        # Rerun to redirect to login
        st.switch_page("app.py")
    
    # Logout section in sidebar
    with st.sidebar:
        st.markdown("### 👤 Account")
        st.markdown(f"**Faculty:** {faculty_name}")
        st.markdown(f"**Role:** {st.session_state.role.title()}")
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            """Handle user logout"""
            # Store logout message before clearing session
            logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
            
            # Clear all session state
            st.session_state.clear()
            
            # Show logout message
            st.success(logout_message)
            st.info("Redirecting to login page...")
            
            # Brief delay for user feedback
            import time
            time.sleep(3)
            
            # Rerun to redirect to login
            st.switch_page("app.py")

def main():
    """Main function to run the faculty dashboard"""
    show_faculty_dashboard()

# Run the dashboard if this file is executed directly
if __name__ == "__main__":
    main()
else:
    # If imported, check auth and show dashboard
    check_faculty_auth()
    show_faculty_dashboard()