import streamlit as st
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# -----------------------------
# Step 1: Load environment variables
# -----------------------------
load_dotenv()

# -----------------------------
# Step 2: MongoDB connection
# -----------------------------
uri = "mongodb+srv://smsgaldones:mit261laban@cluster0.jp5aupl.mongodb.net/"
client = MongoClient(uri)

db = client["mit261"]
students_col = db["students"]
grades_col = db["grades"]
subjects_col = db["subjects"]
semester_col = db["semesters"]

# -----------------------------
# Step 3: Authentication check
# -----------------------------
if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
    st.error("Unauthorized access. Please login as Student.")
    st.stop()

# -----------------------------
# Step 4: Function to fetch student details
# -----------------------------

def get_student_details(username):
    """
    Fetch student info from MongoDB using the logged-in username.
    """
    student = students_col.find_one({"Username": username})  # Make sure your students collection has a 'Username' field
    if student:
        return {
            "StudentID": str(student.get("_id")),
            "Name": student.get("Name"),
            "Course": student.get("Course"),
            "YearLevel": student.get("YearLevel")
        }
    else:
        return None

# -----------------------------
# Step 5: Student Dashboard
# -----------------------------
def show_student_dashboard():
    username = st.session_state.get("username")
    
    # Fetch details from database
    student_info = get_student_details(username)
    
    if not student_info:
        st.error("Student details not found.")
        return
    
    st.markdown(f"## 🎓 Student Dashboard - {student_info['Name']}")
    st.write(f"**ID:** {student_info['StudentID']} | **Course:** {student_info['Course']} | **Year Level:** {student_info['YearLevel']}")
    
    # Quick stats (example, replace with dynamic if available)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Current GPA", "3.75", "0.12")
    with col2:
        st.metric("Current Courses", "6", "0")

    if st.button("Logout"):
        logout_message = f"Goodbye, {st.session_state.get('username', 'User')}! 👋"
        st.session_state.clear()
        st.success(logout_message)
        st.info("Redirecting to login page...")
        import time
        time.sleep(3)
        st.switch_page("app.py")

# -----------------------------
# Step 6: Run Dashboard
# -----------------------------
if __name__ == "__main__":
    st.set_page_config(
        page_title="DAPAS Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    show_student_dashboard()
