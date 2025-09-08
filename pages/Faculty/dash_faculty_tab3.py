import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import pkl_data_to_df, subjects_cache, new_subjects_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

@st.cache_data(ttl=300)
def compute_subject_failure_rates(df, new_curriculum, passing_grade: int = 75, selected_semester_id = None):
    """
    Compute failure rates per Teacher + SubjectCode.
    Assumes Grade < passing_grade = failure.
    Only includes subjects handled by the given faculty.
    """
    
    
    if df.empty:
        return pd.DataFrame()
    
    if selected_semester_id is not None:
        df = df[df["SemesterID"] == selected_semester_id]
    
    subjects_df = pkl_data_to_df(new_subjects_cache if new_curriculum else subjects_cache)

    if subjects_df is None or subjects_df.empty:
        st.warning("Subjects data not available.")
        return pd.DataFrame()


    subjects_df = subjects_df[subjects_df["Teacher"] == current_faculty]
    if subjects_df.empty:
        return pd.DataFrame()


    df["is_fail"] = df["Grade"] < passing_grade

    grouped = df.groupby(["Teacher", "SubjectCode"]).agg(
        total=("StudentID", "count"),
        failures=("is_fail", "sum")
    ).reset_index()

    grouped["fail_rate"] = (grouped["failures"] / grouped["total"] * 100).round(2)

    grouped = grouped[grouped["total"] > 0]

    merged = grouped.merge(
        subjects_df[["_id", "Description", "Units", "Teacher"]],
        left_on="SubjectCode", right_on="_id", how="inner"
    )

    merged = merged.drop(columns=["_id"])
    

    merged = merged.sort_values(
        ["fail_rate", "failures", "total"],
        ascending=[False, False, False]
    )

    return merged

def show_faculty_tab3_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters] + [" - All Semesters - "]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab3_main_semester"
        )
    with col2:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75)
    with col3:
        top_n = st.slider("Show Top", 5, 50, 10)
    
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    

    st.divider()
    st.markdown(f"<h3 style='text-align: left;'>👨‍🏫 {current_faculty} Subject Difficulty Heatmap ({selected_semester_display})</h3>",unsafe_allow_html=True)
    
    grades_df = get_dataframe_grades(new_curriculum)
    
    df = compute_subject_failure_rates(grades_df, new_curriculum,  passing_grade=passing_grade, selected_semester_id=selected_semester_id)

    if df.empty:
        st.warning("No data available")
        return
    table_df = df.copy()
    
    table_df["Failure Rate"] = table_df["fail_rate"].astype(str) + "%"
    table_df["Units"] = table_df["Units"].astype(str)
    table_df["Total Students"] = table_df["total"].astype(str)
    table_df["Total Failures"] = table_df["failures"].astype(str)

    table_df = table_df.rename(columns={
        "SubjectCode": "Subject Code",
        "Description": "Description"
    })

    display_cols = [
        "Subject Code",
        "Description",
        "Units",
        "Total Students",
        "Total Failures",
        "Failure Rate"
    ]
    
    st.dataframe(style_failure_table(table_df[display_cols].head(top_n)), use_container_width=True, hide_index=True)

    # df["Label"] = df["SubjectCode"] + " - " + df["Description"]
    # chart_df = df.head(top_n)[["Label", "fail_rate"]]
    # fig = px.pie(
    #     chart_df,
    #     names="Label",
    #     values="fail_rate",
    #     title="Failure Rate Distribution by Subject",
    #     hole=0
    # )

    # st.plotly_chart(fig, use_container_width=True)
    # Make label: "CS101 - Intro to Programming"
    table_df["Label"] = table_df["Subject Code"] + " - " + table_df["Description"]

    # Convert Failure Rate back to numeric (remove % sign if present)
    table_df["Failure Rate %"] = table_df["Failure Rate"].str.replace("%", "").astype(float)
    # Bar chart
    fig = px.bar(
        table_df.head(top_n),
        x="Label",
        y="Failure Rate %",
        text="Failure Rate",
        title="Failure Rate per Subject",
        color="Failure Rate %",  # color intensity by fail rate
        color_continuous_scale="oranges"
    )

    fig.update_layout(
        xaxis_title="Subject",
        yaxis_title="Failure Rate (%)",
        xaxis_tickangle=-25
    )

    st.plotly_chart(fig, use_container_width=True)
    
def style_failure_table(df):
    """Style Total Failures and Failure Rate in dark red."""
    return df.style.apply(
        lambda row: [
            "color: orange; font-weight: bold" if col in ["Total Failures", "Failure Rate"] else ""
            for col in df.columns
        ],
        axis=1
    )