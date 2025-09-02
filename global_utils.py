
import streamlit as st
import pandas as pd
import os

students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
teachers_cache = "pkl/teachers.pkl"
registrar_cache = "pkl/registrars.pkl"

@st.cache_data
def load_pkl_data(cache_path):
    """Load data from pickle file if exists, else return empty list"""
    if os.path.exists(cache_path):
        return pd.read_pickle(cache_path)
    else:
        print(f"⚠️ Cache file {cache_path} not found.")
        return []


def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def export_to_pdf(df, filename):
    """Export DataFrame to PDF (placeholder)"""
    df.to_pdf(filename, index=False)
    print(f"PDF export not implemented. Data: {df.head()}")


