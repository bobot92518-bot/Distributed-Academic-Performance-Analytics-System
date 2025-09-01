import streamlit as st
from datetime import datetime
import time

# Set page config
st.set_page_config(
    page_title="DAPAS Dashboard",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

def show_dashboard():
    """Main dashboard function that handles navigation and role-based access"""

    # Authentication check
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.error("🔒 Authentication required. Please login first.")
        st.stop()

    role = st.session_state.get("role", None)
    username = st.session_state.get("username", "Unknown User")
    user_data = st.session_state.get("user_data", {})

    if role not in ["faculty", "student", "registrar"]:
        st.error("❌ Invalid role or session expired. Please login again.")
        st.session_state.clear()
        st.stop()

    st.title(f"🏫 DAPAS Dashboard - {role.title()}")
    display_name = user_data.get("Name", username)
    st.markdown(f"### Welcome back, **{display_name}**! 👋")

    setup_sidebar(role, username, display_name)
    display_dashboard_content(role)

def setup_sidebar(role, username, display_name):
    """Sidebar navigation based on user role"""
    st.sidebar.title("🧭 Dashboard")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 User Information")
    st.sidebar.markdown(f"**Name:** {display_name}")
    st.sidebar.markdown(f"**Username:** {username}")
    st.sidebar.markdown(f"**Role:** {role.title()}")
    st.sidebar.markdown(f"**Login Time:** {datetime.now().strftime('%H:%M')}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Quick Actions")

    if role == "faculty":
        sidebar_button("👨‍🏫 Faculty Dashboard", "faculty_main")
        sidebar_button("📊 Grade Management", "grade_management")
        sidebar_button("👥 Student Records", "student_records")
    elif role == "student":
        sidebar_button("🎓 Student Dashboard", "student_main")
        sidebar_button("📈 My Grades", "my_grades")
        sidebar_button("📚 Course Schedule", "schedule")
    elif role == "registrar":
        sidebar_button("📋 Registrar Dashboard", "registrar_main")
        sidebar_button("🏫 Manage Courses", "manage_courses")
        sidebar_button("👨‍🎓 Manage Students", "manage_students")
        sidebar_button("👨‍🏫 Manage Faculty", "manage_faculty")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ System")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data refreshed successfully!")
        st.rerun()
    if st.sidebar.button("🚪 Logout", use_container_width=True, type="secondary"):
        logout()

def sidebar_button(label, page_key):
    if st.sidebar.button(label, key=page_key, use_container_width=True):
        st.session_state.current_page = page_key

def display_dashboard_content(role):
    """Load and display role-specific dashboard"""
    current_page = st.session_state.get('current_page', f'{role}_main')

    try:
        if role == "student" and current_page == "student_main":
            import pages.student.stddash as dash_student
            if hasattr(dash_student, 'main'):
                dash_student.main()
            elif hasattr(dash_student, 'show_student_dashboard'):
                dash_student.show_student_dashboard()
            else:
                st.info("Module loaded but no entry function found.")
        elif role == "faculty" and current_page == "faculty_main":
            import pages.Faculty.dash_faculty as dash_faculty
            if hasattr(dash_faculty, 'main'):
                dash_faculty.main()
            elif hasattr(dash_faculty, 'show_faculty_dashboard'):
                dash_faculty.show_faculty_dashboard()
            else:
                st.info("Module loaded but no entry function found.")
        elif role == "registrar" and current_page == "registrar_main":
            import pages.Registrar.dash_registrar as dash_registrar
            if hasattr(dash_registrar, 'main'):
                dash_registrar.main()
            elif hasattr(dash_registrar, 'show_registrar_dashboard'):
                dash_registrar.show_registrar_dashboard()
            else:
                st.info("Module loaded but no entry function found.")
        else:
            st.warning("No dashboard page matched the current role and page.")
    except ImportError as e:
        st.error(f"Import error: {e}")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

def logout():
    """Clear session and redirect to login"""
    logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
    st.session_state.clear()
    st.success(logout_message)
    st.info("Redirecting to login page...")
    st.rerun()

# Run dashboard
show_dashboard()
