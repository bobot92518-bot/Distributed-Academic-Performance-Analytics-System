import streamlit as st
from datetime import datetime

def show_dashboard():
    """Main dashboard function that handles navigation and role-based access"""
    
    # Check if user is authenticated - RETURN instead of st.stop()
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.error("🔒 Authentication required. Please login first.")
        return  # Return instead of st.stop() to allow app.py to handle it
    
    # Get the user role from session state
    role = st.session_state.get("role", None)
    username = st.session_state.get("username", "Unknown User")
    user_data = st.session_state.get("user_data", {})
    
    # Validate role
    if role not in ["faculty", "student", "registrar"]:
        st.error("❌ Invalid role or session expired. Please login again.")
        # Clear invalid session
        st.session_state.clear()
        return
    
    # Page title
    st.title(f"🏫 DAPAS Dashboard - {role.title()}")
    
    # Welcome message
    display_name = get_display_name(user_data, username)
    st.markdown(f"### Welcome back, **{display_name}**! 👋")
    
    # Set up Sidebar Navigation
    setup_sidebar(role, username, display_name)
    
    # Display the main dashboard content
    display_dashboard_content(role)

def get_display_name(user_data, username):
    """Get user's display name from user data"""
    if user_data:
        full_name = user_data.get("Name", "")
        return full_name if full_name else username
    return username


def setup_sidebar(role, username, display_name):
    """Setup sidebar dashboard based on user role"""
    
    # Sidebar header
    st.sidebar.title("🧭 Dashboard")
    st.sidebar.markdown("---")
    
    # User info section
    st.sidebar.markdown("### 👤 User Information")
    st.sidebar.markdown(f"**Name:** {display_name}")
    st.sidebar.markdown(f"**Username:** {username}")
    st.sidebar.markdown(f"**Role:** {role.title()}")
    st.sidebar.markdown(f"**Login Time:** {datetime.now().strftime('%H:%M')}")
    
    st.sidebar.markdown("---")
    
    # Role-based navigation
    st.sidebar.markdown("### 📋 Quick Actions")
    
    if role == "faculty":
        if st.sidebar.button("👨‍🏫 Faculty Dashboard", key="nav_faculty", use_container_width=True):
            st.session_state.current_page = "faculty_main"
        if st.sidebar.button("📊 Grade Management", key="nav_grades", use_container_width=True):
            st.session_state.current_page = "grade_management"
        if st.sidebar.button("👥 Student Records", key="nav_students", use_container_width=True):
            st.session_state.current_page = "student_records"
            #adasdd x
    elif role == "student":
        if st.sidebar.button("🎓 Student Dashboard", key="nav_student", use_container_width=True):
            st.session_state.current_page = "student_main"
        if st.sidebar.button("📈 My Grades", key="nav_my_grades", use_container_width=True):
            st.session_state.current_page = "my_grades"
        if st.sidebar.button("📚 Course Schedule", key="nav_schedule", use_container_width=True):
            st.session_state.current_page = "schedule"
            
    elif role == "registrar":
        if st.sidebar.button("📋 Registrar Dashboard", key="nav_registrar", use_container_width=True):
            st.session_state.current_page = "registrar_main"
        if st.sidebar.button("🏫 Manage Courses", key="nav_courses", use_container_width=True):
            st.session_state.current_page = "manage_courses"
        if st.sidebar.button("👨‍🎓 Manage Students", key="nav_manage_students", use_container_width=True):
            st.session_state.current_page = "manage_students"
        if st.sidebar.button("👨‍🏫 Manage Faculty", key="nav_manage_faculty", use_container_width=True):
            st.session_state.current_page = "manage_faculty"
    
    st.sidebar.markdown("---")
    
    # System actions
    st.sidebar.markdown("### ⚙️ System")
    if st.sidebar.button("🔄 Refresh Data", key="refresh_data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data refreshed successfully!")
        st.rerun()
    
    if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True, type="secondary"):
        logout()

def display_dashboard_content(role):
    """Display main dashboard content based on role"""
    
    # Get current page from session state
    current_page = st.session_state.get('current_page', f'{role}_main')
    
    # Create tabs for better organization
    if role == "faculty":
        display_faculty_content(current_page)
    elif role == "student":
        display_student_content(current_page)
    elif role == "registrar":
        display_registrar_content(current_page)



def display_faculty_content(current_page):
    """Display faculty-specific dashboard content"""
    
    # Try to import and display faculty modules
    try:
        if current_page == "faculty_main" or current_page is None:
            
            try:
                import pages.dash_faculty as dash_faculty
                if hasattr(dash_faculty, 'main'):
                    dash_faculty.main()
                elif hasattr(dash_faculty, 'show_faculty_dashboard'):
                    dash_faculty.show_faculty_dashboard()
                else:
                    st.info("Faculty dashboard module loaded but no main function found.")
            except ImportError:
                st.warning("⚠️ Faculty dashboard module not found. Please ensure 'dash_faculty.py' exists.")
            except Exception as e:
                st.error(f"Error loading faculty dashboard: {e}")
                
    except Exception as e:
        st.error(f"Error displaying faculty content: {e}")

def display_student_content(current_page):
    """Display student-specific dashboard content"""
    
    try:
        if current_page == "student_main" or current_page is None:
            
            # Try to load student module
            try:
                import pages.dash_student as dash_student
                if hasattr(dash_student, 'main'):
                    dash_student.main()
                elif hasattr(dash_student, 'show_student_dashboard'):
                    dash_student.show_student_dashboard()
                else:
                    st.info("Student dashboard module loaded but no main function found.")
            except ImportError:
                st.warning("⚠️ Student dashboard module not found. Please ensure 'dash_student.py' exists.")
            except Exception as e:
                st.error(f"Error loading student dashboard: {e}")
                
    except Exception as e:
        st.error(f"Error displaying student content: {e}")

def display_registrar_content(current_page):
    """Display registrar-specific dashboard content"""
    
    try:
        if current_page == "registrar_main" or current_page is None:
            # Try to load registrar module
            try:
                import pages.dash_registrar as dash_registrar
                if hasattr(dash_registrar, 'main'):
                    dash_registrar.main()
                elif hasattr(dash_registrar, 'show_registrar_dashboard'):
                    dash_registrar.show_registrar_dashboard()
                else:
                    st.info("Registrar dashboard module loaded but no main function found.")
            except ImportError:
                st.warning("⚠️ Registrar dashboard module not found. Please ensure 'dash_registrar.py' exists.")
            except Exception as e:
                st.error(f"Error loading registrar dashboard: {e}")
                
    except Exception as e:
        st.error(f"Error displaying registrar content: {e}")




def logout():
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
    time.sleep(1)
    
    # Rerun to redirect to login
    st.rerun()

def check_authentication():
    """Check if user is authenticated and has valid role"""
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        return False
    
    role = st.session_state.get("role", None)
    if role not in ["faculty", "student", "registrar"]:
        return False
    
    return True

# Main execution
if __name__ == "__main__":
    # Set page config
    st.set_page_config(
        page_title="DAPAS Dashboard",
        page_icon="🏫",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    show_dashboard()
else:
    show_dashboard()