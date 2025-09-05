
import streamlit as st
import pandas as pd
from global_utils import pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, teachers_cache


@st.cache_data(ttl=300)
def get_semesters_list():
    """Get list of all semesters"""
    try:
        semesters_df = pkl_data_to_df(semesters_cache)


        # Handle empty data
        if semesters_df is None or semesters_df.empty:
            return []

        # Validate required columns
        required_cols = {"SchoolYear", "Semester"}
        if not required_cols.issubset(semesters_df.columns):
            st.warning(f"Required columns {required_cols} not found in semesters data")
            return []

        # Sort: SchoolYear descending, Semester ascending
        semesters_df_sorted = semesters_df.sort_values(
            ["SchoolYear", "Semester"],
            ascending=[False, True]
        )

        # Return as list of dicts
        return semesters_df_sorted[["_id", "Semester", "SchoolYear"]].to_dict("records")

    except Exception as e:
        st.error(f"Error fetching semesters: {e}")
        return []

@st.cache_data(ttl=300)
def get_semesters_list():
    """Get list of all semesters"""
    try:
        semesters_df = pkl_data_to_df(semesters_cache)

        # Handle empty data
        if semesters_df is None or semesters_df.empty:
            return []

        # Validate required columns
        required_cols = {"SchoolYear", "Semester"}
        if not required_cols.issubset(semesters_df.columns):
            st.warning(f"Required columns {required_cols} not found in semesters data")
            return []

        # Sort: SchoolYear descending, Semester ascending
        semesters_df_sorted = semesters_df.sort_values(
            ["SchoolYear", "Semester"],
            ascending=[False, True]
        )

        # Return as list of dicts
        return semesters_df_sorted[["_id", "Semester", "SchoolYear"]].to_dict("records")

    except Exception as e:
        st.error(f"Error fetching semesters: {e}")
        return []


@st.cache_data(ttl=300)
def get_subjects_by_teacher(teacher_name):
    """Get subjects taught by a specific teacher"""
    try:
        subjects_df = pkl_data_to_df(subjects_cache)

        # Handle empty DataFrame
        if subjects_df is None or subjects_df.empty:
            return []

        # Filter by teacher
        if "Teacher" in subjects_df.columns:
            teacher_subjects = subjects_df[subjects_df["Teacher"] == teacher_name]

            # Sort by subject _id if present
            if "_id" in teacher_subjects.columns:
                teacher_subjects = teacher_subjects.sort_values("_id")

            # Return only the useful columns
            columns_to_return = ["_id", "Description", "Units", "Teacher"]
            available_columns = [col for col in columns_to_return if col in teacher_subjects.columns]

            return teacher_subjects[available_columns].to_dict("records")
        else:
            st.warning("'Teacher' column not found in subjects data")
            return []

    except Exception as e:
        st.error(f"Error fetching subjects for teacher {teacher_name}: {e}")
        return []



@st.cache_data(ttl=300)
def get_students_from_grades(teacher_name, name=""):
    df = get_dataframe_grades()
    if df.empty:
        return pd.DataFrame()

    students_df = pkl_data_to_df(students_cache)

    if students_df is None or students_df.empty:
        st.warning("Students data not available.")
        return pd.DataFrame()

    # Merge grades with student info
    merged = df.merge(
        students_df[["_id", "Name", "Course", "YearLevel"]],
        left_on="StudentID", right_on="_id",
        how="inner"
    )

    # Apply filters
    if name:
        merged = merged[merged["Name"].str.contains(name, case=False, na=False)]
    if teacher_name:
        merged = merged[merged["Teacher"] == teacher_name]

    # Only distinct students
    distinct_students = merged.drop_duplicates(subset=["StudentID", "Name", "Course", "YearLevel"])
    distinct_students = distinct_students.rename(columns={
        "Name": "Student",
        "Course": "Course",
        "YearLevel": "YearLevel"
    })

    return distinct_students[["StudentID", "Student", "Course", "YearLevel"]].reset_index(drop=True)

    
    
    
@st.cache_data(ttl=300)
def get_dataframe_grades():
    """
    Flatten the 'grades' collection where SubjectCodes, Grades, Teachers are arrays.
    Returns a DataFrame with columns:
    StudentID, SubjectCode, Grade, Teacher, SemesterID
    """
    try:
        df = pkl_data_to_df(grades_cache)

        if df is None or df.empty:
            return pd.DataFrame()

        # Ensure required columns
        required_cols = {"StudentID", "SubjectCodes", "Grades", "Teachers", "SemesterID"}
        if not required_cols.issubset(df.columns):
            st.warning(f"Missing required columns: {required_cols - set(df.columns)}")
            return pd.DataFrame()

        # Explode arrays into rows
        df_exploded = df.explode(["SubjectCodes", "Grades", "Teachers"]).reset_index(drop=True)

        # Rename for clarity
        df_exploded = df_exploded.rename(columns={
            "SubjectCodes": "SubjectCode",
            "Grades": "Grade",
            "Teachers": "Teacher"
        })

        return df_exploded[["StudentID", "SubjectCode", "Grade", "Teacher", "SemesterID"]]

    except Exception as e:
        st.error(f"Error normalizing grades: {e}")
        return pd.DataFrame()


