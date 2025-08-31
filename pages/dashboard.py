import streamlit as st
from datetime import datetime

# Set page config at the top
st.set_page_config(
    page_title="DAPAS Dashboard",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

def show_dashboard():
    """Main dashboard function that handles navigation and role-based access"""
    
    # Check if user is authenticated
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.error("🔒 Authentication required. Please login first.")
        st.stop()
    
    # Get user info
    role = st.session_state.get("role", None)
    username = st.session_state.get("username", "Unknown User")
    user_data = st.session_state.get("user_data", {})
    
    if role not in ["faculty", "student", "registrar"]:
        st.error("❌ Invalid role or session expired. Please login again.")
        st.session_state.clear()
        st.stop()
    
    # Page title
    st.title(f"🏫 DAPAS Dashboard - {role.title()}")
    
    # Welcome message
    display_name = get_display_name(user_data, username)
    st.markdown(f"### Welcome back, **{display_name}**! 👋")
    
    # Sidebar
    setup_sidebar(role, username, display_name)
    
    # Main content
    display_dashboard_content(role)

def get_display_name(user_data, username):
    return user_data.get("Name", username) if user_data else username

def setup_sidebar(role, username, display_name):
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
    if st.sidebar.button("🔄 Refresh Data", key="refresh_data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data refreshed successfully!")
        st.rerun()
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True, type="secondary"):
        logout()

def sidebar_button(label, page_key):
    if st.sidebar.button(label, key=page_key, use_container_width=True):
        st.session_state.current_page = page_key

def display_dashboard_content(role):
    current_page = st.session_state.get('current_page', f'{role}_main')
    if role == "faculty":
        display_faculty_content(current_page)
    elif role == "student":
        display_student_content(current_page)
    elif role == "registrar":
        display_registrar_content(current_page)

def display_faculty_content(current_page):
    try:
        if current_page == "faculty_main":
            import pages.Faculty.dash_faculty as dash_faculty
            run_module(dash_faculty)
    except Exception as e:
        st.error(f"Error displaying faculty content: {e}")

def display_student_content(current_page):
    try:
        if current_page == "student_main":
            import pages.student.stddash as dash_student
            run_module(dash_student)
    except Exception as e:
        st.error(f"Error displaying student content: {e}")

def display_registrar_content(current_page):
    try:
        if current_page == "registrar_main":
            import pages.Registrar.dash_registrar as dash_registrar
            run_module(dash_registrar)
    except Exception as e:
        st.error(f"Error displaying registrar content: {e}")

def run_module(module):
    if hasattr(module, 'main'):
        module.main()
    elif hasattr(module, 'show_dashboard'):
        module.show_dashboard()
    else:
        st.info("Module loaded but no entry function found.")

def logout():
    logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
    st.session_state.clear()
    st.success(logout_message)
    st.info("Redirecting to login page...")
    st.rerun()


# Run dashboard when page loads
show_dashboard()
