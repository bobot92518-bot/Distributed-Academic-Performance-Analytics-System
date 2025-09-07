import streamlit as st
import pandas as pd
from datetime import datetime
from dbconnect import *
from global_utils import user_accounts_cache
import time
import os # Make sure this returns a valid MongoDB client

def authenticate_user(username, password):
    """Authenticate user and return user data with role"""
    # Load user accounts from pickle file
    if os.path.exists(user_accounts_cache):
        user_accounts = pd.read_pickle(user_accounts_cache)
        user_accounts_df = pd.DataFrame(user_accounts) if isinstance(user_accounts, list) else user_accounts
    else:
        # If pickle file doesn't exist, fetch from database and create it
        db = db_connect()
        user_accounts = list(db["user_accounts"].find({}))
        user_accounts_df = pd.DataFrame(user_accounts)
        user_accounts_df.to_pickle(user_accounts_cache)

    # Find user by username
    user = user_accounts_df[user_accounts_df["Username"] == username]
    
    if not user.empty and user.iloc[0]["Password"] == password:
        user_data = user.iloc[0].to_dict()
        return user_data

    return None

def main():
    # Page config
    st.set_page_config(page_title="DAPAS Login",page_icon="🏫", layout="centered")
    st.markdown(
        """
        <style>
            .stMainBlockContainer {
                margin: 20px;
                padding: 0;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
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
        "<h2 style='padding:0; margin: 0; font-size:100px; text-align:center; margin:0;'>🏫</h2>"
        "<h1 style='padding:0; margin: 0; text-align: center; color: #4B8BBE;'>Welcome to DAPAS</h1>"
        "<h3 style='padding:0; margin: 0; text-align: center; color: #306998;'>Distributed Academic Performance Analytics System</h3>"
        "<br>",
        unsafe_allow_html=True
    )

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
            user_result_data = authenticate_user(username, password)

        if user_result_data:
            # Store session data
            st.session_state.authenticated = True
            st.session_state.name = user_result_data["Name"]
            st.session_state.username = username
            st.session_state.role = user_result_data["UserType"].lower()
            st.session_state.user_data = user_result_data

            st.success(f"✅ Welcome, {user_result_data["Name"]}! You are logged in as {user_result_data["UserType"].title()}")
            st.balloons()
            time.sleep(2)

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
