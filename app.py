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
        return {"user_data": user, "role": "student"}
    

    # Check faculty collection
    try:
        user = db["teachers"].find_one({"Username": username})
        if user and user.get("Password") == password:
            return {"user_data": user, "role": "faculty"}
    except:
        pass

    # Check registrars collection
    user = db["registrars"].find_one({"Username": username})
    if user and user.get("Password") == password:
        return {"user_data": user, "role": "registrar"}

    return None

def main():
    # Page config
    st.set_page_config(page_title="DAPAS Login", layout="centered")

    # Hide sidebar completely
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="stSidebarNav"] { display: none; }
            [data-testid="stSidebarContent"] { display: none; }
            .block-container {
                padding-left: 2rem;
                padding-right: 2rem;
            }
        </style>
    """, unsafe_allow_html=True)

    # Title
    st.markdown(
        "<h1 style='text-align: center; color: #4B8BBE;'>Welcome to DAPAS</h1>"
        "<h3 style='text-align: center; color: #306998;'>Distributed Academic Performance Analytics System</h3>",
        unsafe_allow_html=True
    )

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

        with st.spinner("Authenticating..."):
            auth_result = authenticate_user(username, password)

        if auth_result:
            # Store session data
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.role = auth_result["role"]
            st.session_state.user_data = auth_result["user_data"]

            st.success(f"✅ Welcome, {username}! You are logged in as {auth_result['role'].title()}")
            st.balloons()
            time.sleep(1)

            if st.session_state.role == "student":
                st.switch_page("pages/stddash.py")
            else:
                st.switch_page("pages/dashboard.py")
        else:
            st.error("❌ Invalid username or password. Please try again.")
            st.markdown(
                "<p style='text-align: center; margin-top: 20px;'>"
                "<small>Don't have an account? Contact your administrator.</small></p>",
                unsafe_allow_html=True
            )

    # Footer
    st.markdown("<br><br>", unsafe_allow_html=True)
    current_year = datetime.now().year
    st.markdown(
        f"<p style='text-align: center; color: gray; margin-top: 50px;'>"
        f"© {current_year} DAPAS | Version 1.0 | MIT261 - Group 1</p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
