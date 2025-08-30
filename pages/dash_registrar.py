import streamlit as st

# Check if user is authenticated and has the correct role
if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "registrar":
    st.error("Unauthorized access. Please login as Registrar.")
    st.stop()

def show_registrar_dashboard():
    # Default registrar dashboard
    st.markdown("## 📋 Registrar Dashboard")
    st.write("Welcome to the Registrar Dashboard. Here you can manage student enrollment, records, and more.")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Students", "1,247", "45")
    with col2:
        st.metric("Total Faculty/Instructors", "89", "3")
    with col3:
        st.metric("Total Courses/Subjects", "156", "12")


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
        page_icon="🏫",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    show_registrar_dashboard()
else:
    show_registrar_dashboard()