import streamlit as st
import pandas as pd 

def show_faculty_tab2_info():
    """Display current subjects being taught"""
    st.markdown("### 📚 Current Subjects")
    
    # Sample subjects data
    subjects_data = [
        {
            "Subject Code": "CS 101",
            "Subject Name": "Introduction to Computer Science",
            "Students": 45,
            "Schedule": "MWF 9:00-10:00 AM",
            "Room": "Lab 201",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 201", 
            "Subject Name": "Data Structures",
            "Students": 32,
            "Schedule": "TTh 2:00-3:30 PM",
            "Room": "Room 305",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 301",
            "Subject Name": "Database Systems",
            "Students": 28,
            "Schedule": "MWF 11:00-12:00 PM", 
            "Room": "Lab 102",
            "Status": "🟢 Active"
        },
        {
            "Subject Code": "CS 401",
            "Subject Name": "Software Engineering",
            "Students": 22,
            "Schedule": "TTh 10:00-11:30 AM",
            "Room": "Room 401",
            "Status": "🟡 Planning"
        }
    ]
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(subjects_data)
    
    # Display as interactive table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Students": st.column_config.NumberColumn(
                "Students",
                help="Number of enrolled students",
                format="%d 👥"
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="Current status of the subject"
            )
        }
    )
