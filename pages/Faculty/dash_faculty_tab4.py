import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import pkl_data_to_df, grades_cache, students_cache, subjects_cache, semesters_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list, get_students_from_grades

current_faculty = user_data = st.session_state.get('user_data', {}).get('Teacher', '')

@st.cache_data(ttl=300)
def compute_student_risk_analysis(selected_semester_id = None, passing_grade: int = 75):
    students_df = get_students_from_grades(teacher_name = current_faculty)
    grades_df = pkl_data_to_df(grades_cache)
    # students_df = pkl_data_to_df(students_cache)
    subjects_df = pkl_data_to_df(subjects_cache)
    semesters_df = pkl_data_to_df(semesters_cache)
    
    if grades_df.empty:
            return []

    # Expand SubjectCodes + Grades + Teachers into rows
    grades_expanded = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])
    if selected_semester_id:
            grades_expanded = grades_expanded[grades_expanded["SemesterID"] == selected_semester_id]
    
    merged = (
            grades_expanded
            .merge(students_df, left_on="StudentID", right_on="StudentID", suffixes=("", "_student"))
            .merge(subjects_df, left_on="SubjectCodes", right_on="_id", suffixes=("", "_subject"))
            .merge(semesters_df, left_on="SemesterID", right_on="_id", suffixes=("", "_semester"))
        )
    
    if merged.empty:
        return pd.DataFrame()

    # Mark failures
    merged["Grades"] = pd.to_numeric(merged["Grades"], errors="coerce")

    # Mark failures: grades < passing or invalid grades (NaN) automatically fail
    merged["is_fail"] = (merged["Grades"] < passing_grade) | (merged["Grades"].isna())

    # Optional: set NaN grades to 0 for averaging if you want them counted as fail
    merged["Grades"] = merged["Grades"].fillna(0)

    # Group per student
    student_summary = merged.groupby(["StudentID", "Student", "YearLevel"]).agg(
        Avg_Grade=("Grades", "mean"),
        Failed_Subjs=("is_fail", "sum"),
        Total_Subjs=("Grades", "count")
    ).reset_index()

    # Round averages
    student_summary["Avg_Grade"] = student_summary["Avg_Grade"].round(1)

    # Risk logic
    def get_risk_reason(avg, fails):
        reasons = []
        if avg < passing_grade:
            reasons.append("Low average")
        if fails > 0:
            reasons.append("Failed core subjects")
        return ", ".join(reasons) if reasons else "–"

    student_summary["Risk Reason(s)"] = student_summary.apply(
        lambda r: get_risk_reason(r["Avg_Grade"], r["Failed_Subjs"]), axis=1
    )
    student_summary["Intervention Candidate"] = student_summary["Risk Reason(s)"].apply(
        lambda x: "✅ Yes" if x != "–" else "❌ No"
    )

    # Final ordered output
    return student_summary[[
        "StudentID", "Student", "Avg_Grade","Total_Subjs", "Failed_Subjs", "Risk Reason(s)", "Intervention Candidate", "YearLevel"
    ]]
    

def show_faculty_tab4_info():
    st.title("Identify students at risk based on current semester performance.")
    semesters = get_semesters_list();
    year_levels = [
        {"value": 1, "label": "1st Year"},
        {"value": 2, "label": "2nd Year"},
        {"value": 3, "label": "3rd Year"},
        {"value": 4, "label": "4th Year"},
        {"value": 0, "label": " - All Year Levels - "}
    ]
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab4_main_semester"
        )
    with col2:
        selected_year_level_display = st.selectbox(
        "Year Level",
        options=[y["value"] for y in year_levels],
        format_func=lambda x: next(item["label"] for item in year_levels if item["value"] == x),
        key="year_level_filter"
    )
    
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    selected_year_level = None
    if selected_year_level_display != 0:
        selected_year_level = selected_year_level_display
    
    student_df = compute_student_risk_analysis(selected_semester_id=selected_semester_id)
    if student_df.empty:
        st.warning("No student data available.")
        return
    
    if selected_year_level is not None:
        student_df = student_df[student_df["YearLevel"] == selected_year_level]
    
    for yl_value, yl_label in [(y["value"], y["label"]) for y in year_levels]:
        group_df = student_df[student_df["YearLevel"] == yl_value]
        if group_df.empty:
            continue

        with st.expander(f"{yl_label} ({len(group_df)} students)", expanded=True):
            display_df = student_df.rename(columns={
                "StudentID": "Student ID",
                "Student": "Student Name",
                "Avg_Grade": "Avg Grade",
                "Total_Subjs": "Total Subjectss",
                "Failed_Subjs": "Failed Subjects",
                "Risk_Reasons": "Risk Reason(s)",
                "Intervention_Candidate": "Intervention Candidate"
            })

            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            
            # Pie chart for Intervention Candidate
            count_df = group_df['Intervention Candidate'].value_counts().reset_index()
            count_df.columns = ['Intervention Candidate', 'Count']

            fig = px.pie(
                count_df,
                names='Intervention Candidate',
                values='Count',
                color='Intervention Candidate',
                color_discrete_map={"✅ Yes": "red", "❌ No": "green"},
                title=f"{yl_label} - Intervention Candidate Distribution"
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