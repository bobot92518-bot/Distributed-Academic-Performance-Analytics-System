
import streamlit as st
import pandas as pd
import os

students_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"
registrar_cache = "pkl/registrars.pkl"
user_accounts_cache = "pkl/user_accounts.pkl"
curriculums_cache = "pkl/curriculums.pkl"
new_grades_cache = "pkl/new_grades.pkl"
new_students_cache = "pkl/new_students.pkl"
new_subjects_cache = "pkl/new_subjects.pkl"

@st.cache_data
def load_pkl_data(cache_path):
    """Load data from pickle file if exists, else return empty list"""
    if os.path.exists(cache_path):
        return pd.read_pickle(cache_path)
    else:
        print(f"⚠️ Cache file {cache_path} not found.")
        return pd.DataFrame()

def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def export_to_pdf(df, filename):
    """Export DataFrame to PDF (placeholder)"""
    df.to_pdf(filename, index=False)
    print(f"PDF export not implemented. Data: {df.head()}")

def pkl_data_to_df(cache_path):
    pkl_data = load_pkl_data(cache_path)
    pkl_pd_data = pd.DataFrame(pkl_data) if isinstance(pkl_data, list) else pkl_data
    if pkl_pd_data.empty:
        st.warning(f"{cache_path} is empty!")
    return pkl_pd_data

def result_records_to_dataframe(results):
    """Convert results to pandas DataFrame"""
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    return df

