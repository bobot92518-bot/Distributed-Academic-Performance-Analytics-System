import streamlit as st
from datetime import datetime
import time
import os
import pandas as pd
from global_utils import load_pkl_data, pkl_data_to_df
from dbconnect import *
from global_utils import user_accounts_cache

# Set page config
st.set_page_config(
    page_title="DAPAS Dashboard",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_dashboard_title(role, current_page):
    if current_page == "faculty_main":
        return "👨‍🏫 Faculty Dashboard"
    elif current_page == "student_main":
        return "🎓 Student Dashboard"
    elif current_page == "registrar_main":
        return "📋 Registrar Dashboard"
    else:
        icon = "🏫"
        if role == "faculty":
            icon = "👨‍🏫"
        elif role == "student":
            icon = "🎓"
        elif role == "registrar":
            icon = "📋"
        return f"{icon} {role.title()} Dashboard"

def show_dashboard():
    """Main dashboard function that handles navigation and role-based access"""

    # Authentication check
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.error("🔒 Authentication required. Please login first.")
        st.info("Redirecting to login page...")
        time.sleep(1)
        st.switch_page("app.py")

    role = st.session_state.get("role", None)
    username = st.session_state.get("username", "Unknown User")
    user_data = st.session_state.get("user_data", {})
    current_page = st.session_state.get('current_page', f'{role}_main')

    if role not in ["faculty", "student", "registrar"]:
        st.error("❌ Invalid role or session expired. Please login again.")
        st.session_state.clear()
        st.stop()

    st.markdown("""
        <style>
            /* Hide "Pages" header */
            div[data-testid="stMainBlockContainer"] {padding:60px 40px;}

            /* Hide entire nav container */
            #faculty-dashboard {padding:0;}
        </style>
    """, unsafe_allow_html=True)

    st.title(get_dashboard_title(role, current_page))
    display_name = user_data.get("Name", username)
    st.markdown(f"### Welcome back, **{display_name}**! 👋")

    setup_sidebar(role, username, display_name)

    if st.session_state.get('show_faculty_select_modal', False):
        show_faculty_select_modal()

    if st.session_state.get('show_student_select_modal', False):
        show_student_select_modal()

    if st.session_state.get('show_registrar_select_modal', False):
        show_registrar_select_modal()

    if st.session_state.get('show_teacher_search_modal', False):
        show_teacher_search_modal()

    display_dashboard_content(role)

def setup_sidebar(role, username, display_name):
    """Sidebar navigation based on user role"""
    
    st.markdown("""
        <style>
            /* Hide "Pages" header */
            div[data-testid="stSidebarHeader"] {display: none;}
            
            /* Hide entire nav container */
            div[data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("<h2 style='font-size:60px; text-align:center; margin:0;'>🏫</h2>",unsafe_allow_html=True)

    st.sidebar.markdown("<h2 style='font-size:24px; text-align:center; margin:0; padding:0'>Distributed Academic Performance Analytics System</h2>",unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 User Information")
    st.sidebar.markdown(f"**Name:** {display_name}")
    st.sidebar.markdown(f"**Username:** {username}")
    st.sidebar.markdown(f"**Role:** {role.title()}")
    st.sidebar.markdown(f"**Login Time:** {datetime.now().strftime('%H:%M')}")


    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ System")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.success("Data refreshed successfully!")
        st.rerun()
    if st.sidebar.button("🚪 Logout", use_container_width=True, type="secondary"):
        logout()

    if role == "registrar" or st.session_state.get('accessed_from_registrar', False):
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Dashboard Access")
        if st.sidebar.button("👨‍🏫 Faculty Dashboard", use_container_width=True):
            st.session_state['show_faculty_select_modal'] = True
            st.rerun()
        if st.sidebar.button("🎓 Student Dashboard", use_container_width=True):
            st.session_state['show_student_select_modal'] = True
            st.rerun()
        if st.sidebar.button("📋 Registrar Dashboard", use_container_width=True):
            # Restore original registrar user data if backup exists
            if 'registrar_user_data_backup' in st.session_state:
                st.session_state['user_data'] = st.session_state['registrar_user_data_backup']
                st.session_state['username'] = st.session_state['registrar_user_data_backup'].get('Username', st.session_state.get('username', ''))
                st.session_state['role'] = 'registrar'
                del st.session_state['registrar_user_data_backup']
            else:
                st.session_state['role'] = "registrar"
            st.session_state['current_page'] = "registrar_main"
            st.session_state['accessed_from_registrar'] = False  # reset
            st.rerun()

def sidebar_button(label, page_key):
    if st.sidebar.button(label, key=page_key, use_container_width=True):
        st.session_state.current_page = page_key

def display_dashboard_content(role):
    """Load and display role-specific dashboard"""
    current_page = st.session_state.get('current_page', f'{role}_main')

    try:
        if current_page == "student_main" and role in ["student", "registrar"]:
            import pages.student.dash_student as dash_student
            if hasattr(dash_student, 'main'):
                dash_student.main()
            elif hasattr(dash_student, 'show_student_dashboard'):
                dash_student.show_student_dashboard()
            else:
                st.info("Module loaded but no entry function found.")
        elif current_page == "faculty_main" and role in ["faculty", "registrar"]:
            from pages.Faculty.dash_faculty import show_faculty_dashboard
            show_faculty_dashboard()
        elif current_page == "registrar_main" and role == "registrar":
            from pages.Registrar.dash_registrar import show_registrar_dashboard
            show_registrar_dashboard()
        else:
            st.warning("No dashboard page matched the current role and page.")
    except ImportError as e:
        st.error(f"Import error: {e}")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

def logout():
    """Clear session and redirect to login"""

    logout_message = f"Goodbye, {st.session_state.get('user_data', {}).get('Name', 'Username')}! 👋"
    st.session_state.clear()
    st.success(logout_message)
    st.info("Redirecting to login page...")
    time.sleep(2)
    st.switch_page("app.py")

@st.dialog("Select Faculty")
def show_faculty_select_modal():
    st.write("Choose a faculty member to view their dashboard:")

    user_accounts_df = None
    if os.path.exists(user_accounts_cache):
        user_accounts = pd.read_pickle(user_accounts_cache)
        user_accounts_df = pd.DataFrame(user_accounts) if isinstance(user_accounts, list) else user_accounts
    else:
        db = db_connect()
        user_accounts = list(db["user_accounts"].find({}))
        user_accounts_df = pd.DataFrame(user_accounts)
        user_accounts_df.to_pickle(user_accounts_cache)

    if user_accounts_df is not None and not user_accounts_df.empty:
        teachers_df = user_accounts_df[user_accounts_df['UserType'] == 'Faculty']
        if not teachers_df.empty:
            faculty_names = teachers_df['Name'].unique().tolist()
            selected_faculty = st.selectbox("Select Faculty", faculty_names)

            if selected_faculty:
                role = teachers_df[teachers_df['Name'] == selected_faculty]['UserType'].iloc[0]
                st.selectbox("Role", [role], disabled=True)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Load Dashboard", use_container_width=True):
                    selected_user_data = teachers_df[teachers_df['Name'] == selected_faculty].to_dict('records')[0]
                    # Backup registrar user data before switching
                    if st.session_state.get('role') == 'registrar':
                        st.session_state['registrar_user_data_backup'] = st.session_state.get('user_data', {})
                    st.session_state['selected_faculty'] = selected_faculty
                    st.session_state['current_page'] = "faculty_main"
                    st.session_state['show_faculty_select_modal'] = False
                    st.session_state['role'] = 'faculty'
                    st.session_state['username'] = selected_faculty
                    st.session_state['user_data'] = selected_user_data
                    st.session_state['accessed_from_registrar'] = True
                    st.rerun()
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state['show_faculty_select_modal'] = False
                    st.rerun()
        else:
            st.error("No faculty data available.")
            if st.button("Close"):
                st.session_state['show_faculty_select_modal'] = False
                st.rerun()
    else:
        st.error("No user accounts data.")
        if st.button("Close"):
            st.session_state['show_faculty_select_modal'] = False
            st.rerun()

@st.dialog("Select Student")
def show_student_select_modal():
    st.write("Choose a student to view their dashboard:")

    user_accounts_df = None
    if os.path.exists(user_accounts_cache):
        user_accounts = pd.read_pickle(user_accounts_cache)
        user_accounts_df = pd.DataFrame(user_accounts) if isinstance(user_accounts, list) else user_accounts
    else:
        db = db_connect()
        user_accounts = list(db["user_accounts"].find({}))
        user_accounts_df = pd.DataFrame(user_accounts)
        user_accounts_df.to_pickle(user_accounts_cache)

    if user_accounts_df is not None and not user_accounts_df.empty:
        students_df = user_accounts_df[user_accounts_df['UserType'] == 'Student']
        if not students_df.empty:
            student_names = students_df['Name'].unique().tolist()
            search = st.text_input("Search Student")
            if search:
                filtered_names = [name for name in student_names if search.lower() in name.lower()]
            else:
                filtered_names = student_names
            selected_student = st.selectbox("Select Student", filtered_names)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Load Dashboard", use_container_width=True):
                    selected_user_data = students_df[students_df['Name'] == selected_student].to_dict('records')[0]
                    # Backup registrar user data before switching
                    if st.session_state.get('role') == 'registrar':
                        st.session_state['registrar_user_data_backup'] = st.session_state.get('user_data', {})
                    st.session_state['selected_student'] = selected_student
                    st.session_state['current_page'] = "student_main"
                    st.session_state['show_student_select_modal'] = False
                    st.session_state['role'] = 'student'
                    st.session_state['username'] = selected_student
                    st.session_state['user_data'] = selected_user_data
                    st.session_state['accessed_from_registrar'] = True
                    st.rerun()
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state['show_student_select_modal'] = False
                    st.rerun()
        else:
            st.error("No student data available.")
            if st.button("Close"):
                st.session_state['show_student_select_modal'] = False
                st.rerun()
    else:
        st.error("No user accounts data.")
        if st.button("Close"):
            st.session_state['show_student_select_modal'] = False
            st.rerun()

# Run dashboard
show_dashboard()
