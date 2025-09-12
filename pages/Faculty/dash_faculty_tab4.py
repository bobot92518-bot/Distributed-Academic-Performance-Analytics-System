import streamlit as st
import pandas as pd 
import plotly.express as px
import plotly.io as pio
import matplotlib.pyplot as plt
import tempfile
from io import BytesIO
from reportlab.platypus import Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from datetime import datetime
from global_utils import pkl_data_to_df, grades_cache, students_cache, subjects_cache, semesters_cache, new_grades_cache, new_subjects_cache
from pages.Faculty.faculty_data_helper import get_semesters_list, get_students_from_grades

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

# Initialize session state keys for tab 4
def initialize_tab4_session_state():
    """Initialize session state variables for tab 4"""
    if 'tab4_data_loaded' not in st.session_state:
        st.session_state.tab4_data_loaded = False
    if 'tab4_student_data' not in st.session_state:
        st.session_state.tab4_student_data = pd.DataFrame()
    if 'tab4_last_params' not in st.session_state:
        st.session_state.tab4_last_params = {}

@st.cache_data(ttl=300)
def compute_student_risk_analysis(is_new_curriculum, selected_semester_id = None, passing_grade: int = 75):
    
    subjects_df = pkl_data_to_df(new_subjects_cache if is_new_curriculum else subjects_cache)
    subjects_df = subjects_df[subjects_df["Teacher"] == current_faculty]
    students_df = get_students_from_grades(is_new_curriculum, teacher_name = current_faculty)
    grades_df = pkl_data_to_df(new_grades_cache if is_new_curriculum else  grades_cache)
    semesters_df = pkl_data_to_df(semesters_cache)
    
    if grades_df.empty:
        return pd.DataFrame()

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
    merged["Failed_SubjectDesc"] = merged.apply(
        lambda r: r["Description"] if r["is_fail"] else None, axis=1
    )
    # Group per student
    student_summary = merged.groupby(["StudentID", "Student", "YearLevel"]).agg(
        Avg_Grade=("Grades", "mean"),
        Failed_Subjs=("is_fail", "sum"),
        Total_Subjs=("Grades", "count"),
        Failed_Subjects=("Failed_SubjectDesc", lambda x: ", ".join(x.dropna()))
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
        lambda x: "⚠️ Needs Intervention" if x != "–" else "✅ On Track"
    )

    # Final ordered output
    return student_summary[[
        "StudentID", "Student", "Avg_Grade","Total_Subjs", "Failed_Subjs","Failed_Subjects", "Intervention Candidate", "YearLevel"
    ]]

def load_student_risk_data(is_new_curriculum, selected_semester_id, passing_grade=75):
    """Load and cache student risk analysis data"""
    with st.spinner("Loading student risk analysis data..."):
        student_df = compute_student_risk_analysis(
            is_new_curriculum=is_new_curriculum,
            selected_semester_id=selected_semester_id,
            passing_grade=passing_grade
        )
        
        # Store in session state
        st.session_state.tab4_student_data = student_df
        st.session_state.tab4_data_loaded = True
        st.session_state.tab4_last_params = {
            'is_new_curriculum': is_new_curriculum,
            'selected_semester_id': selected_semester_id,
            'passing_grade': passing_grade
        }
        
        return student_df

def tab4_params_changed(is_new_curriculum, selected_semester_id, passing_grade):
    """Check if parameters have changed since last load"""
    current_params = {
        'is_new_curriculum': is_new_curriculum,
        'selected_semester_id': selected_semester_id,
        'passing_grade': passing_grade
    }
    return st.session_state.tab4_last_params != current_params

def show_faculty_tab4_info(new_curriculum):
    # Initialize session state
    initialize_tab4_session_state()
    
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    year_levels = [
        {"value": 1, "label": "1st Year"},
        {"value": 2, "label": "2nd Year"},
        {"value": 3, "label": "3rd Year"},
        {"value": 4, "label": "4th Year"}
    ]
    
    # Controls row
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab4_main_semester"
        )
    
    with col2:
        selected_year_level_display = st.selectbox(
            "📚 Year Level",
            options=[0] + [y["value"] for y in year_levels],
            format_func=lambda x: "All Years" if x == 0 else next(item["label"] for item in year_levels if item["value"] == x),
            key="year_level_filter"
        )
    
    with col3:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75, key="tab4_passing_grade")

        
    load_button = st.button("🔄 Load Data", key="tab4_load_button", type="secondary")
    if st.session_state.tab4_data_loaded:
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
    
    selected_year_level = None if selected_year_level_display == 0 else selected_year_level_display
    
    # Check if we need to reload data
    should_load = (
        load_button or 
        not st.session_state.tab4_data_loaded or 
        tab4_params_changed(new_curriculum, selected_semester_id, passing_grade)
    )
    
    # Load data if needed
    if should_load:
        student_df = load_student_risk_data(new_curriculum, selected_semester_id, passing_grade)
    else:
        student_df = st.session_state.tab4_student_data
    
    st.divider()
    
    # Header with data status
    data_status = "Current Data" if st.session_state.tab4_data_loaded else "No Data Loaded"
    year_filter_text = f" - {next(item['label'] for item in year_levels if item['value'] == selected_year_level)}" if selected_year_level else " - All Years"
    st.markdown(
        f"<h3 style='text-align: left;'>🎯 {current_faculty} Student Risk Analysis ({selected_semester_display}{year_filter_text}) - {data_status}</h3>",
        unsafe_allow_html=True
    )
    
    # Display results
    if student_df.empty:
        if st.session_state.tab4_data_loaded:
            st.warning("No student data available for the selected parameters.")
        else:
            st.info("Click 'Load Data' to view student risk analysis.")
        return
    
    # Apply year level filter if selected
    if selected_year_level is not None:
        student_df = student_df[student_df["YearLevel"] == selected_year_level]
        if student_df.empty:
            st.warning(f"No students found for {next(item['label'] for item in year_levels if item['value'] == selected_year_level)}.")
            return
    
    # Overall summary metrics
    total_students = len(student_df)
    needs_intervention = len(student_df[student_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
    on_track = len(student_df[student_df["Intervention Candidate"] == "✅ On Track"])
    avg_grade_overall = student_df["Avg_Grade"].mean()
    
    # Summary metrics row
    col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4)
    
    with col_metrics1:
        st.metric("Total Students", total_students)
    
    with col_metrics2:
        intervention_rate = (needs_intervention / total_students * 100) if total_students > 0 else 0
        st.metric("Needs Intervention", f"{needs_intervention} ({intervention_rate:.1f}%)")
    
    with col_metrics3:
        on_track_rate = (on_track / total_students * 100) if total_students > 0 else 0
        st.metric("On Track", f"{on_track} ({on_track_rate:.1f}%)")
    
    with col_metrics4:
        st.metric("Overall Avg Grade", f"{avg_grade_overall:.1f}")
    
    # Overall distribution chart
    if total_students > 0:
        st.subheader("📊 Overall Intervention Status Distribution")
        overall_count_df = student_df['Intervention Candidate'].value_counts().reset_index()
        overall_count_df.columns = ['Status', 'Count']
        
        fig_overall = px.pie(
            overall_count_df,
            names='Status',
            values='Count',
            color='Status',
            color_discrete_map={"⚠️ Needs Intervention": "#ff6b6b", "✅ On Track": "#51cf66"},
            title="Overall Student Status Distribution"
        )
        fig_overall.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_overall, use_container_width=True)
    
    # Year level breakdown
    st.subheader("📚 Year Level Breakdown")
    
    # Determine which year levels to show
    year_levels_to_show = [selected_year_level] if selected_year_level else [1, 2, 3, 4]
    
    for yl_value in year_levels_to_show:
        yl_label = next(item["label"] for item in year_levels if item["value"] == yl_value)
        group_df = student_df[student_df["YearLevel"] == yl_value]
        
        if group_df.empty:
            continue

        # Calculate year level specific metrics
        yl_needs_intervention = len(group_df[group_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
        yl_on_track = len(group_df[group_df["Intervention Candidate"] == "✅ On Track"])
        yl_avg_grade = group_df["Avg_Grade"].mean()
        
        with st.expander(f"{yl_label} ({len(group_df)} students) - Avg: {yl_avg_grade:.1f} | ⚠️ {yl_needs_intervention} | ✅ {yl_on_track}", expanded=True):
            
            # Year level metrics
            yl_col1, yl_col2, yl_col3, yl_col4 = st.columns(4)
            
            with yl_col1:
                st.metric("Students", len(group_df))
            
            with yl_col2:
                yl_intervention_rate = (yl_needs_intervention / len(group_df) * 100) if len(group_df) > 0 else 0
                st.metric("Needs Intervention", f"{yl_needs_intervention} ({yl_intervention_rate:.1f}%)")
            
            with yl_col3:
                yl_on_track_rate = (yl_on_track / len(group_df) * 100) if len(group_df) > 0 else 0
                st.metric("On Track", f"{yl_on_track} ({yl_on_track_rate:.1f}%)")
            
            with yl_col4:
                st.metric("Avg Grade", f"{yl_avg_grade:.1f}")
            
            # Prepare display dataframe
            display_df = group_df.copy()
            display_df = display_df.rename(columns={
                "StudentID": "Student ID",
                "Student": "Student Name",
                "Avg_Grade": "Avg Grade",
                "Total_Subjs": "Total Subjects",
                "Failed_Subjs": "No. of Failed Subjects",
                "Failed_Subjects": "Failed Subjects"
            })

            # Style the dataframe
            def style_intervention_table(df):
                def highlight_intervention(row):
                    colors = []
                    for col in df.columns:
                        if col == "Intervention Candidate":
                            if row[col] == "⚠️ Needs Intervention":
                                colors.append("background-color: #ffe6e6; color: #d63031; font-weight: bold")
                            elif row[col] == "✅ On Track":
                                colors.append("background-color: #e6f7e6; color: #00b894; font-weight: bold")
                            else:
                                colors.append("")
                        elif col == "No. of Failed Subjects" and row[col] > 0:
                            colors.append("color: #d63031; font-weight: bold")
                        elif col == "Avg Grade" and row[col] < passing_grade:
                            colors.append("color: #e17055; font-weight: bold")
                        else:
                            colors.append("")
                    return colors
                return df.style.apply(highlight_intervention, axis=1)
            
            # Display styled table
            st.dataframe(
                style_intervention_table(display_df.drop(columns=["YearLevel"])), 
                use_container_width=True, 
                hide_index=True
            )
            
            # Pie chart for year level
            if len(group_df) > 0:
                count_df = group_df['Intervention Candidate'].value_counts().reset_index()
                count_df.columns = ['Intervention Candidate', 'Count']

                fig = px.pie(
                    count_df,
                    names='Intervention Candidate',
                    values='Count',
                    color='Intervention Candidate',
                    color_discrete_map={"⚠️ Needs Intervention": "#ff6b6b", "✅ On Track": "#51cf66"},
                    title=f"{yl_label} - Intervention Status Distribution"
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
    
    if not student_df.empty:
        pdf_bytes = generate_intervention_pdf(
            student_df,
            current_faculty,
            new_curriculum,
            selected_semester_display,
            selected_year_level,
            year_levels,
            passing_grade
        )

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "New" if new_curriculum else "Old"
        filename = f"Intervention_Candidates_List_{curriculum_type}_{timestamp}.pdf"
        st.divider()
        st.subheader("📄 Export Report")
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download Students at Risk Based on Current Semester Performance",
            key="download_pdf_tab4" 
        )
    

def generate_intervention_pdf(student_df, current_faculty, new_curriculum, selected_semester_display, selected_year_level, year_levels, passing_grade):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,  
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    styles.add(ParagraphStyle(name="CenterHeading", alignment=1, fontSize=14, spaceAfter=12, leading=16))

    elements = []

    # Title
    title = f"Student Risk Analysis Report ({'New Curriculum' if new_curriculum else 'Old Curriculum'})"
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Faculty: {current_faculty}", styles["Normal"]))
    elements.append(Paragraph(f"Semester: {selected_semester_display}", styles["Normal"]))
    if selected_year_level:
        yl_label = next(item["label"] for item in year_levels if item["value"] == selected_year_level)
        elements.append(Paragraph(f"Year Level: {yl_label}", styles["Normal"]))
    elements.append(Paragraph(f"Passing Grade: {passing_grade}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Summary metrics
    total_students = len(student_df)
    needs_intervention = len(student_df[student_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
    on_track = len(student_df[student_df["Intervention Candidate"] == "✅ On Track"])
    avg_grade_overall = student_df["Avg_Grade"].mean()

    summary_data = [
        ["Total Students", total_students],
        ["Needs Intervention", f"{needs_intervention} ({needs_intervention/total_students*100:.1f}%)" if total_students > 0 else "0"],
        ["On Track", f"{on_track} ({on_track/total_students*100:.1f}%)" if total_students > 0 else "0"],
        ["Overall Average Grade", f"{avg_grade_overall:.1f}" if total_students > 0 else "–"],
    ]
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 18))

    # Year-level breakdown tables
    year_levels_to_show = [selected_year_level] if selected_year_level else [1, 2, 3, 4]
    for yl_value in year_levels_to_show:
        group_df = student_df[student_df["YearLevel"] == yl_value]
        if group_df.empty:
            continue

        yl_label = next(item["label"] for item in year_levels if item["value"] == yl_value)
        elements.append(Paragraph(f"{yl_label} ({len(group_df)} students)", styles["Heading3"]))
        elements.append(Spacer(1, 6))

        display_df = group_df.rename(columns={
            "StudentID": "Student ID",
            "Student": "Student Name",
            "Avg_Grade": "Avg Grade",
            "Total_Subjs": "Total Subjects",
            "Failed_Subjs": "No. of Failed Subjects",
            "Failed_Subjects": "Failed Subjects",
            "Intervention Candidate": "Status"
        })

        table_data = [list(display_df.columns)] + display_df.values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        # Highlight intervention candidates
        for row_idx, row in enumerate(table_data[1:], start=1):
            status = row[-1]
            if status == "⚠️ Needs Intervention":
                table.setStyle([("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.red)])
            elif status == "✅ On Track":
                table.setStyle([("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.green)])

        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # 📊 Overall pie chart
        overall_counts = student_df['Intervention Candidate'].value_counts()
        if not overall_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(
                overall_counts.values,
                labels=overall_counts.index,
                autopct="%1.1f%%",
                colors=["#ff6b6b" if s == "⚠️ Needs Intervention" else "#51cf66" for s in overall_counts.index]
            )
            ax.set_title("Overall Intervention Status Distribution")
            img_buf = BytesIO()
            plt.savefig(img_buf, format="png", bbox_inches="tight")
            plt.close(fig)
            img_buf.seek(0)
            elements.append(Image(img_buf, width=4*inch, height=3*inch))
            elements.append(Spacer(1, 12))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def style_failure_table(df):
    """Style Total Failures and Failure Rate in dark red."""
    return df.style.apply(
        lambda row: [
            "color: orange; font-weight: bold" if col in ["Total Failures", "Failure Rate"] else ""
            for col in df.columns
        ],
        axis=1
    )