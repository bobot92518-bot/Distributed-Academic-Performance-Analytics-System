import streamlit as st
import pandas as pd 
import plotly.express as px
import altair as alt
import math
import io
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib import colors as rl_colors
from datetime import datetime
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from global_utils import pkl_data_to_df, semesters_cache, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_semester_from_curriculum, get_active_curriculum, get_student_grades_by_semester, get_new_student_grades_by_semester
from pages.Faculty.faculty_data_manager import save_new_student_grades

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

year_map = {
    1: "1st Year",
    2: "2nd Year",
    3: "3rd Year",
    4: "4th Year",
    5: "5th Year",
}    

        
import streamlit as st
import pandas as pd
import plotly.express as px

def display_grades_submission_summary(df_grades, new_curriculum):
    st.markdown("### 🎓 Subject Grades Submission Status")
    
    if df_grades.empty:
        st.info("No grades data available for the selected filters.")
        return

    current_faculty = st.session_state.get('user_data', {}).get('Name', '')

    # --- Summary per subject ---
    subject_summary = df_grades.groupby(['subjectCode', 'subjectDescription']).agg(
        total_students=('studentName', 'count'),
        submitted_grades=('grade', lambda x: ((x.notnull()) & (x > 0)).sum()),
        unsubmitted_grades=('grade', lambda x: ((x.isna()) | (x == 0)).sum())
    ).reset_index()

    subject_summary['submission_rate'] = (subject_summary['submitted_grades'] / subject_summary['total_students'] * 100).round(1)

    # Reorder columns for display
    subject_summary = subject_summary[['subjectCode', 'subjectDescription', 'submitted_grades', 'unsubmitted_grades', 'total_students', 'submission_rate']]

    # Display summary table
    st.dataframe(
        subject_summary.rename(columns={
            'subjectCode': 'Subject Code',
            'subjectDescription': 'Subject Title',
            'submitted_grades': 'Submitted Grades',
            'unsubmitted_grades': 'Unsubmitted Grades',
            'total_students': 'Total Students',
            'submission_rate': 'Submission Rate (%)'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Bar chart for submission rate per subject
    fig_subject = px.bar(
        subject_summary,
        x='subjectCode',
        y='submission_rate',
        text='submission_rate',
        labels={'subjectCode': 'Subject Code', 'submission_rate': 'Submission Rate (%)'},
        title="Submission Rate per Subject",
        color='submission_rate',
        color_continuous_scale=['#1f77b4', '#6baed6', '#bdd7e7']
    )
    
    
    fig_subject.update_yaxes(range=[0, 100])
    
    fig_subject.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_subject, use_container_width=True)
    
    if new_curriculum:
        # --- Expander: detailed per section ---
        st.markdown("### 📂 Detailed Submission per Section")
        for subj_code, subj_group in df_grades.groupby(['subjectCode', 'subjectDescription']):
            subject_code, subject_title = subj_code

            with st.expander(f"{subject_code} - {subject_title}"):
                section_summary = subj_group.groupby('section').agg(
                    total_students=('studentName', 'count'),
                    submitted_grades=('grade', lambda x: ((x.notnull()) & (x > 0)).sum()),
                    unsubmitted_grades=('grade', lambda x: ((x.isna()) | (x == 0)).sum())
                ).reset_index()
                st.markdown(", ".join(section_summary.columns))
                section_summary['submission_rate'] = (section_summary['submitted_grades'] / section_summary['total_students'] * 100).round(1)
                section_summary['subject_section'] = subject_code + section_summary['section']
                section_summary = section_summary[['subject_section', 'total_students', 'submitted_grades', 'unsubmitted_grades', 'submission_rate']]

                # Display DataFrame
                st.dataframe(
                    section_summary.rename(columns={
                        'section': 'Section',
                        'subject_section': 'Subject Code',
                        'total_students': 'Total Students',
                        'submitted_grades': 'Submitted Grades',
                        'unsubmitted_grades': 'Unsubmitted Grades',
                        'submission_rate': 'Submission Rate (%)'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                # Bar chart per Subject Code / Section
                fig_section = px.bar(
                    section_summary,
                    x='subject_section',          # Correct column name
                    y='submission_rate',
                    text='submission_rate',
                    labels={'subject_section': 'Subject Code', 'submission_rate': 'Submission Rate (%)'},
                    title=f"Submission Rate per Section for {subject_code}",
                    color='submission_rate',
                    color_continuous_scale=['#1f77b4', '#6baed6', '#bdd7e7']
                )
                
                # Limit y-axis to 0-100
                fig_section.update_yaxes(range=[0, 100])

                fig_section.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig_section, use_container_width=True)

        
    
    
def show_faculty_tab5_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
    # Initialize session state for persistence
    if 'grades_df' not in st.session_state:
        st.session_state.grades_df = None
    if 'current_faculty' not in st.session_state:
        st.session_state.current_faculty = current_faculty
    if 'loaded_filters' not in st.session_state:
        st.session_state.loaded_filters = {}
    
    semesters_df = pkl_data_to_df(semesters_cache)
    curriculum_year = get_active_curriculum(new_curriculum)
    semesters = []
    if new_curriculum:
        semesters = get_semester_from_curriculum(curriculum_year, semesters_df)
    else:
        semesters = get_semesters_list(new_curriculum)
        
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
    col1, col2 = st.columns([1, 2])
    
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab5_semester"
        )
    
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    

    if st.button("📊 Load Grades", type="secondary", key="tab5_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_by_semester(current_faculty=current_faculty, semester_id = selected_semester_id)
            else:
                results = get_student_grades_by_semester(current_faculty=current_faculty, semester_id = selected_semester_id)
            
            
            if results:
                df = result_records_to_dataframe(results)
                
                # Store in session state for persistence
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                st.session_state.loaded_filters = {
                    'semester': selected_semester_display
                }
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
                st.session_state.grades_df = None
    
    # Display grades if they exist in session state
    if st.session_state.grades_df is not None and not st.session_state.grades_df.empty:
        # Show current filter info
        if st.session_state.loaded_filters:
            st.info(f"📋 Showing Grade Submission Status: **{st.session_state.loaded_filters.get('semester', 'All')}** ")
        
        display_grades_submission_summary(st.session_state.grades_df,new_curriculum)
    else:
        st.info("👆 Select your filters and click 'Load Grades' to view Subject Grade Submission Status")
    
    add_generate_pdf_button(new_curriculum)

    
def add_generate_pdf_button(new_curriculum):
    filters = st.session_state.loaded_filters if "loaded_filters" in st.session_state else {}
    df = st.session_state.grades_df
    
    if df is None or df.empty:
        st.info("ℹ️ Load grades first to enable PDF export.")
        return
    
    selected_student = None
    if st.session_state.get("selected_student_id"):
        selected_student = df[df["StudentID"] == st.session_state.selected_student_id].iloc[0].to_dict()

    pdf_bytes = generate_grades_submission_pdf(
        current_faculty,
        df,
        filters,
        selected_student
    )

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    curriculum_type = "New" if new_curriculum else "Old"
    filename = f"Student_Grades_Submission_Status_{curriculum_type}_{timestamp}.pdf"

    st.divider()
    st.subheader("📄 Export Report")
    st.download_button(
        label="📄 Download PDF Report",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        type="secondary",
        help="Download Grade Submission Status | School Year: 2022-2023",
        key="download_pdf_tab5" 
    )
def generate_grades_submission_pdf(faculty_name, df, filters, selected_student=None):

    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30
    )
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        alignment=TA_LEFT,
        textColor=colors.darkblue
    )
    
    # --- Title + filter info ---
    title = "Student Grades Submission Status Report"
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"<b>Faculty:</b> {faculty_name}", styles['Normal']))

    if filters:
        sem = filters.get("semester", "All")
        subj = filters.get("subject", "All")
        search = filters.get("search_name", "")
        elements.append(Paragraph(f"<b>Semester:</b> {sem}", styles['Normal']))
        elements.append(Paragraph(f"<b>Subject:</b> {subj}", styles['Normal']))
        if search:
            elements.append(Paragraph(f"Search filter: {search}", styles['Normal']))
    elements.append(Spacer(1, 12))

    if df.empty:
        elements.append(Paragraph("No grades data available for the selected filters.", styles['Normal']))
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    # --- Subject Grades Submission Status ---
    elements.append(Paragraph("Subject Grades Submission Status", subtitle_style))
    
    # Calculate subject summary (same logic as display function)
    subject_summary = df.groupby(['subjectCode', 'subjectDescription']).agg(
        total_students=('studentName', 'count'),
        submitted_grades=('grade', lambda x: ((x.notnull()) & (x > 0)).sum()),
        unsubmitted_grades=('grade', lambda x: ((x.isna()) | (x == 0)).sum())
    ).reset_index()
    
    subject_summary['submission_rate'] = (subject_summary['submitted_grades'] / subject_summary['total_students'] * 100).round(1)
    
    # Summary table
    table_data = [['Subject Code', 'Subject Title', 'Submitted Grades', 'Unsubmitted Grades', 'Total Students', 'Submission Rate (%)']]
    
    for _, row in subject_summary.iterrows():
        table_data.append([
            str(row['subjectCode']),
            str(row['subjectDescription']),
            str(row['submitted_grades']),
            str(row['unsubmitted_grades']),
            str(row['total_students']),
            f"{row['submission_rate']:.1f}%"
        ])
    
    # Create table
    summary_table = Table(table_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b8bbe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # --- Bar Chart for Submission Rate per Subject ---
    elements.append(Paragraph("Submission Rate per Subject", subtitle_style))
    
    if not subject_summary.empty:
        # Prepare chart data
        chart_data = subject_summary['submission_rate'].tolist()
        labels = subject_summary['subjectCode'].tolist()
        
        # Create bar chart
        drawing = Drawing(700, 400)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 50, 50, 600, 300
        chart.data = [chart_data]
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 100
        chart.valueAxis.valueStep = 10
        chart.bars[0].fillColor = rl_colors.HexColor("#6baed6")
        chart.categoryAxis.labels.angle = 0
        chart.categoryAxis.labels.fontSize = 10
        chart.valueAxis.labels.fontSize = 10
        
        # Add title to the chart
        drawing.add(chart)
        from reportlab.graphics.shapes import String
        drawing.add(String(350, 370, "Subject Submission Rates (%)", fontSize=14, textAnchor='middle', fillColor=colors.black))
        # 🔹 Add percentage labels above bars
        for i, value in enumerate(chart_data):
            x = chart.x + chart.width / len(chart_data) * (i + 0.5)   # center of each bar
            y = chart.y + (value / chart.valueAxis.valueMax) * chart.height + 5
            drawing.add(String(x, y, f"{value:.1f}%", fontSize=8, textAnchor="middle"))
        elements.append(drawing)
        elements.append(Spacer(1, 20))

    # Check if new_curriculum is available (from the context it seems to be used)
    # For detailed section breakdown - only if we have section data
    if 'section' in df.columns:
        elements.append(Paragraph("Detailed Submission per Section", subtitle_style))
        
        for subj_code, subj_group in df.groupby(['subjectCode', 'subjectDescription']):
            subject_code, subject_title = subj_code
            
            # Section summary for this subject
            section_summary = subj_group.groupby('section').agg(
                total_students=('studentName', 'count'),
                submitted_grades=('grade', lambda x: ((x.notnull()) & (x > 0)).sum()),
                unsubmitted_grades=('grade', lambda x: ((x.isna()) | (x == 0)).sum())
            ).reset_index()
            
            section_summary['submission_rate'] = (section_summary['submitted_grades'] / section_summary['total_students'] * 100).round(1)
            section_summary['subject_section'] = subject_code + section_summary['section'].astype(str)
            
            # Subject section header
            elements.append(Paragraph(f"{subject_code} - {subject_title}", styles["Heading3"]))
            
            # Section table
            section_table_data = [['Subject Code', 'Total Students', 'Submitted Grades', 'Unsubmitted Grades', 'Submission Rate (%)']]
            
            for _, row in section_summary.iterrows():
                section_table_data.append([
                    str(row['subject_section']),
                    str(row['total_students']),
                    str(row['submitted_grades']),
                    str(row['unsubmitted_grades']),
                    f"{row['submission_rate']:.1f}%"
                ])
            
            section_table = Table(section_table_data, repeatRows=1)
            section_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8)
            ]))
            elements.append(section_table)
            elements.append(Spacer(1, 15))
            
            # Bar chart for this subject's sections
            if len(section_summary) > 1:  # Only create chart if multiple sections
                section_chart_data = section_summary['submission_rate'].tolist()
                section_labels = section_summary['subject_section'].tolist()
                
                section_drawing = Drawing(600, 300)
                section_chart = VerticalBarChart()
                section_chart.x, section_chart.y, section_chart.width, section_chart.height = 50, 50, 500, 200
                section_chart.data = [section_chart_data]
                section_chart.categoryAxis.categoryNames = section_labels
                section_chart.valueAxis.valueMin = 0
                section_chart.valueAxis.valueMax = 100
                section_chart.valueAxis.valueStep = 20
                # section_chart.bars.fillColor = rl_colors.HexColor("#1f77b4")
                section_chart.bars[0].fillColor = colors.HexColor("#1f77b4")
                section_chart.categoryAxis.labels.angle = 0
                section_chart.categoryAxis.labels.fontSize = 9
                
                section_drawing.add(section_chart)
                section_drawing.add(String(300, 270, f"Submission Rate per Section - {subject_code}", fontSize=12, textAnchor='middle'))
                for i, value in enumerate(section_chart_data):
                    x = section_chart.x + section_chart.width / len(section_chart_data) * (i + 0.5)   # center of each bar
                    y = section_chart.y + (value / section_chart.valueAxis.valueMax) * section_chart.height + 5
                    section_drawing.add(String(x, y, f"{value:.1f}%", fontSize=8, textAnchor="middle"))

                elements.append(section_drawing)
                elements.append(Spacer(1, 20))

    # --- Key Insights ---
    elements.append(Paragraph("Key Insights", subtitle_style))
    
    insights = []
    if not subject_summary.empty:
        # Overall statistics
        total_all_students = subject_summary['total_students'].sum()
        total_submitted = subject_summary['submitted_grades'].sum()
        total_unsubmitted = subject_summary['unsubmitted_grades'].sum()
        overall_submission_rate = (total_submitted / total_all_students * 100) if total_all_students > 0 else 0
        
        insights.append(f"• Overall submission rate across all subjects: {overall_submission_rate:.1f}%")
        insights.append(f"• Total students across all subjects: {total_all_students}")
        insights.append(f"• Total submitted grades: {total_submitted}")
        insights.append(f"• Total unsubmitted grades: {total_unsubmitted}")
        
        # Best and worst performing subjects
        if len(subject_summary) > 1:
            best_subject = subject_summary.loc[subject_summary['submission_rate'].idxmax()]
            worst_subject = subject_summary.loc[subject_summary['submission_rate'].idxmin()]
            
            insights.append(f"• Highest submission rate: {best_subject['subjectCode']} ({best_subject['submission_rate']:.1f}%)")
            insights.append(f"• Lowest submission rate: {worst_subject['subjectCode']} ({worst_subject['submission_rate']:.1f}%)")
        
        # Subjects with 100% submission
        complete_subjects = subject_summary[subject_summary['submission_rate'] == 100]['subjectCode'].tolist()
        if complete_subjects:
            insights.append(f"• Subjects with 100% submission: {', '.join(complete_subjects)}")
        
        # Subjects with significant unsubmitted grades (less than 80% submission)
        low_submission = subject_summary[subject_summary['submission_rate'] < 80]
        if not low_submission.empty:
            low_subjects = low_submission['subjectCode'].tolist()
            insights.append(f"• Subjects needing attention (< 80% submission): {', '.join(low_subjects)}")
        
        # Average submission rate
        avg_submission_rate = subject_summary['submission_rate'].mean()
        insights.append(f"• Average submission rate per subject: {avg_submission_rate:.1f}%")
    
    for insight in insights:
        elements.append(Paragraph(insight, styles['Normal']))
        elements.append(Spacer(1, 6))

    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes