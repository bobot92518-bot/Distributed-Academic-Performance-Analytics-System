import streamlit as st
import pandas as pd 
import plotly.express as px
import plotly.io as pio
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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
from pages.Faculty.faculty_data_helper import get_semesters_list, compute_student_risk_analysis, get_subjects_by_teacher

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



def load_student_risk_data(is_new_curriculum, selected_semester_id,selected_subject_code, passing_grade=75):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    """Load and cache student risk analysis data"""
    with st.spinner("Loading student risk analysis data..."):
        student_df = compute_student_risk_analysis(
            is_new_curriculum=is_new_curriculum, current_faculty=current_faculty,
            selected_semester_id=selected_semester_id,
            selected_subject_code=selected_subject_code,
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
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
    # Controls row
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab4_main_semester"
        )
    with col2:
            subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
            selected_subject_display = st.selectbox(
                "📚 Select Subject",
                subject_options,
                key="tab4_subject_dropdown", 
                help="Choose a subject to track student progress"
            )
    
    with col3:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75, key="tab4_passing_grade")

        
    
    if st.session_state.tab4_data_loaded:
        print("Tab 4 Data Loaded")
    else:
        st.info("👆 Select your filters and click 'Load Data' to display Data.")
    # Determine selected semester ID
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    
    selected_subject_code = None
    if selected_subject_display != " - All Subjects - ":
        for subj in subjects:
            if f"{subj['_id']} - {subj['Description']}" == selected_subject_display:
                selected_subject_code = subj['_id']
                break
    
    load_button = st.button("🔄 Load Data", key="tab4_load_button", type="secondary")
    if load_button:
            with st.spinner("Loading data..."):
                try:
                    student_df = load_student_risk_data(new_curriculum, selected_semester_id,selected_subject_code, passing_grade)

                    st.divider()
                    
                    # Header with data status
                    # Display header
                    st.markdown(
                        f"<h3 style='text-align: left;'>🎯 {current_faculty} Student Risk Analysis ({selected_semester_display} - {selected_subject_display})</h3>",
                        unsafe_allow_html=True
                    )

                    # Check if there is data
                    if student_df.empty:
                        if st.session_state.tab4_data_loaded:
                            st.warning("No student data available for the selected parameters.")
                        else:
                            st.info("Click 'Load Data' to view student risk analysis.")
                        return

                    # Overall summary metrics
                    total_students = len(student_df)
                    needs_intervention = len(student_df[student_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
                    on_track = len(student_df[student_df["Intervention Candidate"] == "✅ On Track"])
                    avg_grade_overall = student_df["Grades"].mean()

                    # Summary metrics row
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Students", total_students)
                    col2.metric("Needs Intervention", f"{needs_intervention} ({(needs_intervention/total_students*100 if total_students>0 else 0):.1f}%)")
                    col3.metric("On Track", f"{on_track} ({(on_track/total_students*100 if total_students>0 else 0):.1f}%)")
                    col4.metric("Overall Avg Grade", f"{avg_grade_overall:.1f}")

                    # Overall intervention distribution
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

                    st.subheader("📚 Subject Class Breakdown")

                    for section_name, group_df in student_df.groupby("section"):
                        if group_df.empty:
                            continue
                        
                       # Filter students with grades below passing
                        at_risk_students = group_df[group_df["Grades"] < passing_grade]
                        subject_code = group_df["SubjectCodes"].iloc[0]  # get the subject code for display
                        stud_grade = group_df["Grades"].mean()

                        with st.expander(
                            f"{subject_code}{section_name} ({len(group_df)} students) - {len(at_risk_students)} Students Need Interventions",
                            expanded=True
                        ):
                            # Count at-risk and missing grades
                            at_risk = len(at_risk_students[at_risk_students["Grades"] != 0])
                            missing_grade = len(at_risk_students[at_risk_students["Grades"] == 0])
                            on_track = len(group_df[group_df["Grades"] >= passing_grade])
                            # Needs intervention
                            sec_needs_intervention = len(group_df[group_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
                            sec_needs_intervention_pct = (sec_needs_intervention / len(group_df) * 100) if len(group_df) > 0 else 0
                            metric_text = f"{sec_needs_intervention} ({sec_needs_intervention_pct:.1f}%)"

                            # Display metrics
                            col1, col2, col3, col4, col5, col6 = st.columns(6)
                            col1.metric("Overall Students", len(group_df))
                            col2.metric("On Track", f"{on_track}")
                            col3.metric("Needs Intervention", f"{sec_needs_intervention}")
                            col4.metric("Missing Grade", f"{missing_grade}")
                            col5.metric("At Risk", f"{at_risk}")
                            col6.metric("Class Average", f"{stud_grade:.1f}%")
                            
                            # Prepare display dataframe
                            group_df = group_df[group_df["Grades"] < passing_grade]
                            display_df = group_df.copy()
                            display_df = display_df.rename(columns={
                                "StudentID": "StudentID",
                                "Student": "Student",
                                "SubjectCodes": "SubjectCode",
                                "section": "section",
                                "Description": "Description",
                                "Grades": "Grade",
                                "Risk Flag": "Risk Flag"
                            })

                            # Create concatenated SubjectCode + section column
                            display_df["Subject Code"] = display_df["SubjectCode"].astype(str) + display_df["section"].astype(str)

                            display_df = display_df.rename(columns={
                                "Description": "Subject Description",
                                "Grade": "Current Grade",
                                "Student": "Student Name"
                            })        
                            # Select and order columns for display
                            display_df = display_df[["StudentID", "Student Name", "Subject Code", "Subject Description", "Current Grade", "Risk Flag"]]
                            
                            # Style the table
                            def style_intervention_table(df):
                                def highlight(row):
                                    colors = []
                                    for col in df.columns:
                                        if col == "Risk Flag":
                                            if "At Risk" in row[col]:
                                                colors.append("background-color: #ffe6e6; color: #d63031; font-weight: bold")
                                            elif "Missing" in row[col]:
                                                colors.append("background-color: #FFF8E8; color: #BB6653; font-weight: bold")
                                            else:
                                                colors.append("background-color: #e6f7e6; color: #00b894; font-weight: bold")
                                        elif col == "Grade" and row[col] < passing_grade:
                                            colors.append("color: #e17055; font-weight: bold")
                                        else:
                                            colors.append("")
                                    return colors
                                return df.style.apply(highlight, axis=1)
                            st.markdown(f"⚠️ Students Needs Intervetion: {subject_code} {section_name}")
                            st.dataframe(style_intervention_table(display_df), use_container_width=True, hide_index=True)
                            
                            if not display_df.empty:
                                fig_scatter = px.scatter(
                                    display_df,
                                    x="Student Name",
                                    y="Current Grade",
                                    color="Risk Flag",
                                    size="Current Grade",
                                    hover_data=["Subject Code", "Subject Description"],
                                    color_discrete_map={"⚠️ At Risk": "#ff6b6b", "✅ On Track": "#51cf66", "Missing Grade": "#BB6653"},
                                    title=f"{subject_code}{section_name} - Grades Distribution"
                                )
                                st.plotly_chart(fig_scatter, use_container_width=True)
                        
                    st.subheader("📄 Export Report")
                    add_pdf_download_button(student_df, current_faculty, new_curriculum, selected_semester_display, selected_subject_display, passing_grade)
                except Exception as e:
                    st.error(f"❌ An error occurred while loading data: {str(e)}")

def add_pdf_download_button(student_df, current_faculty, new_curriculum, selected_semester_display, selected_subject_display, passing_grade):
    """
    Generate PDF and display Streamlit download button.
    """
    if student_df.empty:
        st.info("No data available to export.")
        return

    pdf_bytes = generate_intervention_pdf(
        student_df=student_df,
        current_faculty=current_faculty,
        new_curriculum=new_curriculum,
        selected_semester_display=selected_semester_display,
        selected_subject_display=selected_subject_display,
        passing_grade=passing_grade
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    curriculum_type = "New" if new_curriculum else "Old"
    filename = f"Intervention_Candidates_List_{curriculum_type}_{timestamp}.pdf"

    st.download_button(
        label="📄 Download PDF Report",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        type="secondary",
        help="Download Students at Risk Based on Current Semester Performance"
    )
     
def generate_intervention_pdf(student_df, current_faculty, new_curriculum, selected_semester_display, selected_subject_display, passing_grade):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
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
    elements.append(Paragraph(f"<b>Faculty:</b> {current_faculty}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Semester:</b> {selected_semester_display}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Subject:</b> {selected_subject_display}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Passing Grade:</b> {passing_grade}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    if student_df.empty:
        elements.append(Paragraph("No student data available for the selected parameters.", styles["Normal"]))
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    # --- Overall Summary Metrics ---
    total_students = len(student_df)
    needs_intervention = len(student_df[student_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
    on_track = len(student_df[student_df["Intervention Candidate"] == "✅ On Track"])
    avg_grade_overall = student_df["Grades"].mean()

    # Summary metrics table
    summary_data = [
        ["Total Students", "Needs Intervention", "On Track", "Overall Avg Grade"],
        [
            str(total_students),
            f"{needs_intervention} ({(needs_intervention/total_students*100 if total_students>0 else 0):.1f}%)",
            f"{on_track} ({(on_track/total_students*100 if total_students>0 else 0):.1f}%)",
            f"{avg_grade_overall:.1f}"
        ]
    ]
    
    summary_table = Table(summary_data, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2a654")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # --- Overall Intervention Status Distribution ---
    elements.append(Paragraph("📊 Overall Intervention Status Distribution", styles["Heading2"]))
    
    if total_students > 0:
        overall_count_df = student_df['Intervention Candidate'].value_counts().reset_index()
        overall_count_df.columns = ['Status', 'Count']
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Define colors for pie chart
        colors_map = {"⚠️ Needs Intervention": "#ff6b6b", "✅ On Track": "#51cf66"}
        pie_colors = [colors_map.get(status, "#cccccc") for status in overall_count_df['Status']]
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            overall_count_df['Count'], 
            labels=overall_count_df['Status'],
            colors=pie_colors,
            autopct='%1.1f%%',
            startangle=90
        )
        
        ax.set_title('Overall Student Status Distribution', fontsize=14, fontweight='bold')
        
        # Save pie chart to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_pie:
            plt.savefig(tmp_pie.name, format='png', dpi=300, bbox_inches='tight')
            plt.close()
            
            # Add pie chart to PDF
            pie_image = Image(tmp_pie.name, width=4*inch, height=3*inch)
            elements.append(pie_image)
        
        # Create pie chart data table
        pie_data = [["Status", "Count", "Percentage"]]
        for _, row in overall_count_df.iterrows():
            percentage = (row['Count'] / total_students * 100)
            pie_data.append([row['Status'], str(row['Count']), f"{percentage:.1f}%"])
        
        pie_table = Table(pie_data, hAlign="LEFT")
        pie_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b8bbe")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)
        ]))
        elements.append(pie_table)
        elements.append(Spacer(1, 20))

    # --- Subject Class Breakdown ---
    elements.append(Paragraph("📚 Subject Class Breakdown", styles["Heading2"]))
    
    for section_name, group_df in student_df.groupby("section"):
        if group_df.empty:
            continue
            
        # Calculate section metrics
        at_risk_students = group_df[group_df["Grades"] < passing_grade]
        subject_code = group_df["SubjectCodes"].iloc[0]
        stud_grade = group_df["Grades"].mean()
        
        at_risk = len(at_risk_students[at_risk_students["Grades"] != 0])
        missing_grade = len(at_risk_students[at_risk_students["Grades"] == 0])
        on_track_section = len(group_df[group_df["Grades"] >= passing_grade])
        sec_needs_intervention = len(group_df[group_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
        
        # Section header
        elements.append(Paragraph(f"{subject_code}{section_name} ({len(group_df)} students) - {len(at_risk_students)} Students Need Interventions", styles["Heading3"]))
        
        # Section metrics table
        section_metrics_data = [
            ["Overall Students", "On Track", "Needs Intervention", "Missing Grade", "At Risk", "Class Average"],
            [
                str(len(group_df)),
                str(on_track_section),
                str(sec_needs_intervention),
                str(missing_grade),
                str(at_risk),
                f"{stud_grade:.1f}%"
            ]
        ]
        
        section_metrics_table = Table(section_metrics_data, hAlign="LEFT")
        section_metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8)
        ]))
        elements.append(section_metrics_table)
        elements.append(Spacer(1, 12))
        
        # Students needing intervention table
        intervention_students = group_df[group_df["Grades"] < passing_grade].copy()
        
        if not intervention_students.empty:
            elements.append(Paragraph(f"⚠️ Students Needing Intervention: {subject_code} {section_name}", styles["Normal"]))
            
            # Prepare display dataframe
            display_df = intervention_students.copy()
            display_df["Subject Code"] = display_df["SubjectCodes"].astype(str) + display_df["section"].astype(str)
            
            # Create student intervention table
            student_data = [["Student ID", "Student", "Subject-Section", "Description", "Grade", "Risk Flag"]]
            
            for _, row in display_df.iterrows():
                student_data.append([
                    str(row["StudentID"]),
                    str(row["Student"]),
                    str(row["Subject Code"]),
                    str(row["Description"]),
                    str(row["Grades"]),
                    str(row["Risk Flag"])
                ])
            
            student_table = Table(student_data, repeatRows=1)
            
            # Style table based on risk flags
            table_style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
            ]
            
            # Add conditional formatting for risk flags
            for i, row in enumerate(display_df.itertuples(index=False), 1):
                if "At Risk" in str(row._6):  # Risk Flag column
                    table_style.append(("BACKGROUND", (5, i), (5, i), colors.HexColor("#ffebee")))
                    table_style.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#d32f2f")))
                elif "Missing" in str(row._6):
                    table_style.append(("BACKGROUND", (5, i), (5, i), colors.HexColor("#fff8e1")))
                    table_style.append(("TEXTCOLOR", (5, i), (5, i), colors.HexColor("#f57c00")))
                
                # Highlight low grades
                if hasattr(row, '_5') and float(row._5) < passing_grade:
                    table_style.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#d32f2f")))
                    table_style.append(("FONTSIZE", (4, i), (4, i), 8))
            
            student_table.setStyle(TableStyle(table_style))
            elements.append(student_table)
            elements.append(Spacer(1, 15))
            
            # Create scatter plot for grade distribution
            elements.append(Paragraph(f"📈 Grade Distribution Scatter Plot: {subject_code}{section_name}", styles["Normal"]))
            
            # Create scatter plot using matplotlib
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Define colors for different risk categories
            risk_colors = {
                "⚠️ At Risk": "#ff6b6b",
                "✅ On Track": "#51cf66", 
                "Missing Grade": "#BB6653"
            }
            
            # Plot points for each risk category
            for risk_flag in display_df["Risk Flag"].unique():
                mask = display_df["Risk Flag"] == risk_flag
                subset = display_df[mask]
                
                ax.scatter(
                    range(len(subset)), 
                    subset["Grades"],
                    c=risk_colors.get(risk_flag, "#cccccc"),
                    label=risk_flag,
                    s=60,
                    alpha=0.7
                )
            
            # Customize the plot
            ax.set_xlabel('Students', fontsize=12)
            ax.set_ylabel('Grades', fontsize=12)
            ax.set_title(f'{subject_code}{section_name} - Grade Distribution', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Add passing grade line
            ax.axhline(y=passing_grade, color='red', linestyle='--', alpha=0.7, label=f'Passing Grade ({passing_grade})')
            
            # Set student names on x-axis if not too many
            if len(display_df) <= 15:
                student_names = [name[:10] + "..." if len(name) > 10 else name for name in display_df["Student"]]
                ax.set_xticks(range(len(student_names)))
                ax.set_xticklabels(student_names, rotation=45, ha='right', fontsize=8)
            
            # Save scatter plot to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_scatter:
                plt.tight_layout()
                plt.savefig(tmp_scatter.name, format='png', dpi=300, bbox_inches='tight')
                plt.close()
                
                # Add scatter plot to PDF
                scatter_image = Image(tmp_scatter.name, width=6*inch, height=3.5*inch)
                elements.append(scatter_image)
                elements.append(Spacer(1, 15))
            
            # Grade distribution chart (text representation)
            elements.append(Paragraph(f"Grade Distribution Summary for {subject_code}{section_name}:", styles["Normal"]))
            
            # Create grade distribution summary
            grade_ranges = {
                "90-100": len(intervention_students[(intervention_students["Grades"] >= 90) & (intervention_students["Grades"] <= 100)]),
                "80-89": len(intervention_students[(intervention_students["Grades"] >= 80) & (intervention_students["Grades"] < 90)]),
                "70-79": len(intervention_students[(intervention_students["Grades"] >= 70) & (intervention_students["Grades"] < 80)]),
                "60-69": len(intervention_students[(intervention_students["Grades"] >= 60) & (intervention_students["Grades"] < 70)]),
                "Below 60": len(intervention_students[intervention_students["Grades"] < 60]),
                "Missing (0)": len(intervention_students[intervention_students["Grades"] == 0])
            }
            
            grade_dist_data = [["Grade Range", "Number of Students"]]
            for grade_range, count in grade_ranges.items():
                if count > 0:  # Only show ranges with students
                    grade_dist_data.append([grade_range, str(count)])
            
            if len(grade_dist_data) > 1:  # If there's data beyond headers
                grade_dist_table = Table(grade_dist_data, hAlign="LEFT")
                grade_dist_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8)
                ]))
                elements.append(grade_dist_table)
        else:
            elements.append(Paragraph(f"✅ All students in {subject_code}{section_name} are on track!", styles["Normal"]))
        
        elements.append(Spacer(1, 20))

    # --- Summary Insights ---
    elements.append(Paragraph("🔍 Key Insights", styles["Heading2"]))
    
    insights = []
    if total_students > 0:
        intervention_rate = (needs_intervention / total_students) * 100
        insights.append(f"• {intervention_rate:.1f}% of students need intervention")
        
        # Find section with highest risk
        section_risks = {}
        for section_name, group_df in student_df.groupby("section"):
            section_intervention = len(group_df[group_df["Intervention Candidate"] == "⚠️ Needs Intervention"])
            section_risks[section_name] = (section_intervention / len(group_df)) * 100
        
        if section_risks:
            highest_risk_section = max(section_risks, key=section_risks.get)
            lowest_risk_section = min(section_risks, key=section_risks.get)
            insights.append(f"• Highest risk section: Section {highest_risk_section} ({section_risks[highest_risk_section]:.1f}%)")
            insights.append(f"• Lowest risk section: Section {lowest_risk_section} ({section_risks[lowest_risk_section]:.1f}%)")
        
        insights.append(f"• Overall class average: {avg_grade_overall:.1f}")
        
        # Count students with missing grades
        missing_grades = len(student_df[student_df["Grades"] == 0])
        if missing_grades > 0:
            insights.append(f"• {missing_grades} students have missing grades")
    
    for insight in insights:
        elements.append(Paragraph(insight, styles["Normal"]))
        elements.append(Spacer(1, 6))

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