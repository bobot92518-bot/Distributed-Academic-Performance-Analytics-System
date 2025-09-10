import streamlit as st
import pandas as pd 
import plotly.express as px
from global_utils import pkl_data_to_df, subjects_cache, new_subjects_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

# Initialize session state keys
def initialize_session_state():
    """Initialize session state variables for tab 3"""
    if 'tab3_data_loaded' not in st.session_state:
        st.session_state.tab3_data_loaded = False
    if 'tab3_failure_data' not in st.session_state:
        st.session_state.tab3_failure_data = pd.DataFrame()
    if 'tab3_last_params' not in st.session_state:
        st.session_state.tab3_last_params = {}

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

def load_failure_data(new_curriculum, passing_grade, selected_semester_id):
    """Load and cache failure rate data"""
    with st.spinner("Loading failure rate data..."):
        grades_df = get_dataframe_grades(new_curriculum)
        df = compute_subject_failure_rates(
            grades_df, 
            new_curriculum, 
            passing_grade=passing_grade, 
            selected_semester_id=selected_semester_id
        )
        
        # Store in session state
        st.session_state.tab3_failure_data = df
        st.session_state.tab3_data_loaded = True
        st.session_state.tab3_last_params = {
            'new_curriculum': new_curriculum,
            'passing_grade': passing_grade,
            'selected_semester_id': selected_semester_id
        }
        
        return df

def params_changed(new_curriculum, passing_grade, selected_semester_id):
    """Check if parameters have changed since last load"""
    current_params = {
        'new_curriculum': new_curriculum,
        'passing_grade': passing_grade,
        'selected_semester_id': selected_semester_id
    }
    return st.session_state.tab3_last_params != current_params

def show_faculty_tab3_info(new_curriculum):
    # Initialize session state
    initialize_session_state()
    
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    
    # Controls row
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters] + [" - All Semesters - "]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab3_main_semester"
        )
    
    with col2:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75, key="tab3_passing_grade")
    
    load_button = st.button("🔄 Load Data", key="tab3_load_button", type="secondary")
    if st.session_state.tab3_data_loaded:
        print("Data Loaded")
    else:
        st.info("👆 Select your filters and click 'Load Data' to display Data.")
    # Determine selected semester ID
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    
    # Check if we need to reload data
    should_load = (
        load_button or 
        not st.session_state.tab3_data_loaded or 
        params_changed(new_curriculum, passing_grade, selected_semester_id)
    )
    
    # Load data if needed
    if should_load:
        df = load_failure_data(new_curriculum, passing_grade, selected_semester_id)
    else:
        df = st.session_state.tab3_failure_data
    
    st.divider()
    
    # Header with data status
    data_status = "Current Data" if st.session_state.tab3_data_loaded else "No Data Loaded"
    st.markdown(
        f"<h3 style='text-align: left;'>👨‍🏫 {current_faculty} Subject Difficulty Heatmap ({selected_semester_display}) - {data_status}</h3>",
        unsafe_allow_html=True
    )
    
    # Display results
    if df.empty:
        if st.session_state.tab3_data_loaded:
            st.warning("No data available for the selected parameters.")
        else:
            st.info("Click 'Load Data' to view failure rate analysis.")
        return
    
    # Prepare table data
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
    
    # Data summary metrics
    col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4)
    
    with col_metrics1:
        st.metric("Total Subjects", len(df))
    
    with col_metrics2:
        avg_failure_rate = df["fail_rate"].mean()
        st.metric("Avg Failure Rate", f"{avg_failure_rate:.1f}%")
    
    with col_metrics3:
        highest_failure = df["fail_rate"].max() if not df.empty else 0
        st.metric("Highest Failure Rate", f"{highest_failure:.1f}%")
    
    with col_metrics4:
        total_students_analyzed = df["total"].sum()
        st.metric("Total Students", total_students_analyzed)
    
    # Display table
    st.subheader("📊 Detailed Failure Rate Table")
    st.dataframe(
        style_failure_table(table_df[display_cols]), 
        use_container_width=True, 
        hide_index=True
    )
    
    # Display chart
    st.subheader("📈 Failure Rate Visualization")
    
    # Prepare chart data
    table_df["Label"] = table_df["Subject Code"] + " - " + table_df["Description"]
    table_df["Failure Rate %"] = table_df["Failure Rate"].str.replace("%", "").astype(float)
    
    # Bar chart
    fig = px.bar(
        table_df,
        x="Label",
        y="Failure Rate %",
        text="Failure Rate",
        title="Failure Rate per Subject",
        color="Failure Rate %",
        color_continuous_scale="oranges"
    )

    fig.update_layout(
        xaxis_title="Subject",
        yaxis_title="Failure Rate (%)",
        xaxis_tickangle=-25,
        showlegend=False
    )
    
    fig.update_traces(textposition='outside')

    st.plotly_chart(fig, use_container_width=True)
    
    # Additional insights
    if not df.empty:
        st.subheader("🔍 Key Insights")
        
        # Find subjects with highest and lowest failure rates
        highest_failure_subject = df.loc[df["fail_rate"].idxmax()]
        lowest_failure_subject = df.loc[df["fail_rate"].idxmin()]
        
        insight_col1, insight_col2 = st.columns(2)
        
        with insight_col1:
            st.error(f"**Highest Failure Rate:** {highest_failure_subject['SubjectCode']} - {highest_failure_subject['Description']} ({highest_failure_subject['fail_rate']}%)")
        
        with insight_col2:
            st.success(f"**Lowest Failure Rate:** {lowest_failure_subject['SubjectCode']} - {lowest_failure_subject['Description']} ({lowest_failure_subject['fail_rate']}%)")

def style_failure_table(df):
    """Style Total Failures and Failure Rate in dark red."""
    return df.style.apply(
        lambda row: [
            "color: orange; font-weight: bold" if col in ["Total Failures", "Failure Rate"] else ""
            for col in df.columns
        ],
        axis=1
    )