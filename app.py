import streamlit as st
from datetime import datetime
from dbconnect import *
import time

def authenticate_user(username, password):
    """Authenticate user and return user data with role"""
    db = db_connect()
    
    # Check students collection
    user = db["students"].find_one({"username": username})
    if user and user.get("Password") == password:
        return {
            "user_data": user,
            "role": "student",          #for testing kay wala pa naayos ang users ta sir, change lang ning role sa "faculty", "registrar", "student"
            "collection": "students"
        }
    
    # Check faculty collection (if you have one)
    try:
        user = db["teachers"].find_one({"Username": username})
        if user and user.get("Password") == password:
            return {
                "user_data": user,
                "role": "faculty",
                "collection": "teachers"
            }
    except:
        pass  # Faculty collection might not exist
    
    # Check registrars collection
    user = db["registrars"].find_one({"Username": username})
    if user and user.get("Password") == password:
        return {
            "user_data": user,
            "role": "registrar",
            "collection": "registrars"
        }
    
    return None

def main():
    # Page config
    st.set_page_config(page_title="DAPAS Login", layout="centered")
    
    # Check if already authenticated 

    
    # Title
    st.markdown(
        "<h1 style='text-align: center; color: #4B8BBE;'>Welcome to DAPAS</h1>"
        "<h3 style='text-align: center; color: #306998;'>Distributed Academic Performance Analytics System</h3>",
        unsafe_allow_html=True
    )
    
    # Add some spacing
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Login form
    with st.form("login_form"):
        st.markdown("<h3 style='text-align: center;'>🔑 Login</h3>", unsafe_allow_html=True)
        

        username = st.text_input("👤 Username", placeholder="Enter your username")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
            
            
        st.markdown("<br>", unsafe_allow_html=True)
        login_button = st.form_submit_button("Login", use_container_width=True)
    
    # Login logic
    if login_button:
        if not username or not password:
            st.error("❌ Please enter both username and password.")
            return
        
        # Show loading spinner
        with st.spinner("Authenticating..."):
            auth_result = authenticate_user(username, password)
        
        if auth_result:
            # Initialize session state for authenticated user
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = auth_result["role"]
            st.session_state.user_data = auth_result["user_data"]
            st.session_state.collection = auth_result["collection"]
            
            # Store user ID for easy access
            st.session_state.user_id = auth_result["user_data"].get("_id")
            
            st.success(f"✅ Welcome, {username}! Logged in as {auth_result['role'].title()}")
            
            # Small delay for better UX
            st.balloons()
            time.sleep(1)
            
            # Switch to dashboard page
            st.switch_page("./pages/dashboard.py")
        else:
            st.error("❌ Invalid username or password. Please try again.")
            
            # Optional: Add forgot password or registration links
            st.markdown(
                "<p style='text-align: center; margin-top: 20px;'>"
                "<small>Don't have an account? Contact your administrator.</small></p>",
                unsafe_allow_html=True
            )
    
    # Footer with copyright, current year, and version
    st.markdown("<br><br>", unsafe_allow_html=True)
    current_year = datetime.now().year
    st.markdown(
        f"<p style='text-align: center; color: gray; margin-top: 50px;'>"
        f"© {current_year} DAPAS | Version 1.0 | MIT261 - Group 1</p>",
        unsafe_allow_html=True
    )

def logout():
    """Handle logout functionality"""
    st.session_state.clear()
    st.rerun()

if __name__ == "__main__":
    main()

    #this is sample comment