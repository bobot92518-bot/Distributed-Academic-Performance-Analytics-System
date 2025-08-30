import streamlit as st

# Check if user is authenticated and has the correct role
if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
    st.error("Unauthorized access. Please login as Student.")
    st.stop()

def show_student_dashboard():
    # Default student dashboard
    st.markdown("## 🎓 Student Dashboard")
    st.write("Welcome to the Student Dashboard. Here you can view your grades, assignments, and academic progress.")
    
    # Quick stats
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current GPA", "3.75", "0.12")
    with col2:
        st.metric("Current Courses", "6", "0")

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

if __name__ == "__main__":
    # Set page config
    st.set_page_config(
        page_title="DAPAS Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    show_student_dashboard()
else:
    show_student_dashboard()