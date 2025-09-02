import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
from global_utils import load_pkl_data #import function sa helper hihi

students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"


def get_academic_standing(filters):
    """Get academic standing data based on filters"""
    students_df = pd.DataFrame(load_pkl_data(students_cache))
    grades_df = pd.DataFrame(load_pkl_data(grades_cache))
    semesters_df = pd.DataFrame(load_pkl_data(semesters_cache))

    if students_df.empty or grades_df.empty:
        return pd.DataFrame()

    # Merge grades with students
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id) > 0:
            merged = merged[merged["SemesterID"] == sem_id[0]]

    if filters.get("SchoolYear") != "All":
        sem_id = semesters_df[semesters_df["SchoolYear"] == int(filters["SchoolYear"])]["_id"].values
        if len(sem_id) > 0:
            merged = merged[merged["SemesterID"].isin(sem_id)]

    # Calculate GPA
    merged["GPA"] = merged["Grades"].apply(lambda x: sum(x)/len(x) if isinstance(x, list) and x else 0)

    # Determine status
    merged["Status"] = merged["GPA"].apply(lambda g: "Good Standing" if g >= 75 else "Probation")

    return merged[["Name", "GPA", "Status"]].drop_duplicates()


