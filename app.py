import streamlit as st
import pandas as pd
from datetime import datetime
from dbconnect import *
from global_utils import students_cache, teachers_cache, registrar_cache
import time
import os # Make sure this returns a valid MongoDB client

def authenticate_user(username, password):
    """Authenticate user and return user data with role"""
    db = db_connect()

    # STUDENT
    if os.path.exists(students_cache):
        students = pd.read_pickle(students_cache)
        students_df = pd.DataFrame(students) if isinstance(students, list) else students
    else:
        students = list(db["students"].find({}))
        students_df = pd.DataFrame(students)
        students_df.to_pickle(students_cache)

    student = students_df[students_df["username"] == username]
    if not student.empty and student.iloc[0]["Password"] == password:
        return {
            "user_data": student.iloc[0].to_dict(),
            "role": "student",
            "collection": "students"
        }

    # FACULTY
    if os.path.exists(teachers_cache):
        teachers = pd.read_pickle(teachers_cache)
        teachers_df = pd.DataFrame(teachers) if isinstance(teachers, list) else teachers
    else:
        teachers = list(db["teachers"].find({}))
        teachers_df = pd.DataFrame(teachers)
        teachers_df.to_pickle(teachers_cache)

    teacher = teachers_df[teachers_df["Username"] == username]
    if not teacher.empty and teacher.iloc[0]["Password"] == password:
        return {
            "user_data": teacher.iloc[0].to_dict(),
            "role": "faculty",
            "collection": "teachers"
        }

    # REGISTRAR
    if os.path.exists(registrar_cache):
        registrars = pd.read_pickle(registrar_cache)
        registrars_df = pd.DataFrame(registrars) if isinstance(registrars, list) else registrars
    else:
        registrars = list(db["registrars"].find({}))
        registrars_df = pd.DataFrame(registrars)
        registrars_df.to_pickle(registrar_cache)

    registrar = registrars_df[registrars_df["Username"] == username]
    if not registrar.empty and registrar.iloc[0]["Password"] == password:
        return {
            "user_data": registrar.iloc[0].to_dict(),
            "role": "registrar",
            "collection": "registrars"
        }

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
