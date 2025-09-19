import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from reportlab.lib import colors
from datetime import datetime

def export_to_excel(df, filename):
    """Export DataFrame to Excel"""
    df.to_excel(filename, index=False)
    print(f"Exported to {filename}")

def create_incomplete_grades_pdf(df, semester_filter, faculty_filter, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts):
    """Generate PDF report for incomplete grades"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)

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

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        alignment=TA_LEFT,
        textColor=colors.black
    )

    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_LEFT
    )

    # Title
    elements.append(Paragraph("⚠️ Incomplete Grades Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Information
    report_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Semester Filter:</b> {semester_filter if semester_filter != "All" else "All Semesters"}<br/>
    <b>Faculty Filter:</b> {faculty_filter if faculty_filter != "All" else "All Faculty"}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))

    if df.empty:
        # If no data, add a message
        elements.append(Paragraph("NO STUDENT INCOMPLETE GRADES", header_style))
        elements.append(Spacer(1, 12))
    else:
        # Summary Statistics
        elements.append(Paragraph("Summary Statistics", header_style))
        elements.append(Spacer(1, 6))

        summary_data = [
            ["Metric", "Value"],
            ["Total Incomplete Grades", f"{total_incomplete:,}"],
            ["Affected Students", f"{unique_students:,}"],
            ["Affected Subjects", f"{unique_subjects:,}"],
            ["Involved Faculty", f"{unique_teachers:,}"]
        ]
        summary_table = Table(summary_data, repeatRows=1)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Key Insights Section (moved to bottom)

        # Grade Type Distribution
        elements.append(Paragraph("Grade Type Distribution", header_style))
        elements.append(Spacer(1, 6))

        grade_type_data = [["Grade Type", "Count", "Percentage"]]
        total_types = grade_type_counts.sum()
        for grade_type, count in grade_type_counts.items():
            percentage = (count / total_types * 100) if total_types > 0 else 0
            grade_type_data.append([grade_type, str(count), f"{percentage:.1f}%"])

        grade_type_table = Table(grade_type_data, repeatRows=1)
        grade_type_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(grade_type_table)
        elements.append(Spacer(1, 20))

        # Detailed Data Table
        elements.append(Paragraph("Detailed Incomplete Grades Report", header_style))
        elements.append(Spacer(1, 6))

        # Prepare data for table
        display_df = df[["StudentID", "Name", "SubjectCodes", "Grades", "TeacherName", "SemesterName", "GradeType"]].copy()
        table_data = [display_df.columns.tolist()] + display_df.values.tolist()

        # Create table with word wrapping
        wrap_style = ParagraphStyle(
            'WrapStyle',
            fontSize=8,
            leading=10,
            alignment=TA_LEFT
        )

        def wrap_text(cell):
            if isinstance(cell, str):
                return Paragraph(cell, wrap_style)
            return cell

        table_data_wrapped = [[wrap_text(cell) for cell in row] for row in table_data]

        data_table = Table(table_data_wrapped, repeatRows=1, colWidths=[1*inch, 1.5*inch, 1.5*inch, 1*inch, 1.5*inch, 1*inch, 1*inch])
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(data_table)

        # Key Insights Section (moved to bottom)
        if not df.empty:
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("🔍 Key Insights", header_style))
            elements.append(Spacer(1, 6))

            total = total_incomplete
            students = unique_students
            subjects = unique_subjects
            faculty = unique_teachers

            insights_text = f"""
<b>Incomplete Grades Overview:</b><br/>
• Total incomplete grades identified: {total:,} across the institution.<br/>
• Number of affected students: {students:,}, requiring immediate academic support.<br/>
• Subjects impacted: {subjects:,}, indicating potential curriculum or teaching challenges.<br/>
• Faculty members involved: {faculty:,}, highlighting areas for faculty development.<br/>
<br/>
<b>Grade Type Analysis:</b><br/>
• {'High incidence of incomplete grades suggests systemic issues requiring attention.' if total > 50 else 'Moderate incomplete grades indicate manageable academic support needs.'}<br/>
• {'Multiple students affected indicates widespread academic challenges.' if students > 20 else 'Limited student impact allows for targeted interventions.'}<br/>
• {'Faculty involvement across multiple subjects points to teaching methodology concerns.' if faculty > 5 else 'Concentrated faculty issues suggest specific training needs.'}<br/>
<br/>
<b>Recommendations:</b><br/>
• Implement proactive academic monitoring and early intervention programs.<br/>
• Provide additional faculty training on grade completion and student support.<br/>
• Establish clear policies for handling incomplete grades and student communication.<br/>
• Monitor trends to identify patterns and implement preventive measures.
"""

            elements.append(Paragraph(insights_text, info_style))
            elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_incomplete_grades_pdf_download_button(df, semester_filter, faculty_filter, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts):
    """Add a download button for incomplete grades PDF export"""

    if df is None:
        st.warning("No data available to export to PDF.")
        return

    try:
        pdf_data = create_incomplete_grades_pdf(df, semester_filter, faculty_filter, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Incomplete_Grades_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of incomplete grades",
            key="download_pdf_tab9"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def add_incomplete_grades_pdf_print_button(df, semester_filter, faculty_filter, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts):
    """Add a print button for incomplete grades PDF"""

    if df is None:
        st.warning("No data available to print PDF.")
        return

    try:
        pdf_data = create_incomplete_grades_pdf(df, semester_filter, faculty_filter, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts)

        # Convert PDF data to base64 for JS
        import base64
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

        # HTML and JS to create blob and print
        html_code = f"""
        <button onclick="printPDF()" style="background-color: #f0f2f6; border: 1px solid #d3d3d3; border-radius: 0.25rem; padding: 0.25rem 0.75rem; font-size: 0.875rem; color: #262730; cursor: pointer;">🖨️ Print PDF Report</button>
        <script>
        function printPDF() {{
            const pdfData = '{pdf_base64}';
            const byteCharacters = atob(pdfData);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {{
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }}
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {{ type: 'application/pdf' }});
            const url = URL.createObjectURL(blob);
            const newWindow = window.open(url, '_blank');
            newWindow.onload = function() {{
                newWindow.print();
            }};
        }}
        </script>
        """

        components.html(html_code, height=50)

    except Exception as e:
        st.error(f"Error generating PDF for print: {str(e)}")

@st.cache_data(ttl=300)
def load_all_data_new():
    """Load all data using the new pickle files for students, grades, and subjects."""
    start_time = time.time()

    new_students_path = "pkl/new_students.pkl"
    new_grades_path = "pkl/new_grades.pkl"
    new_subjects_path = "pkl/new_subjects.pkl"
    new_teachers_path = "pkl/new_teachers.pkl"

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            'students': executor.submit(pkl_data_to_df, new_students_path),
            'grades': executor.submit(pkl_data_to_df, new_grades_path),
            'semesters': executor.submit(pkl_data_to_df, semesters_cache),
            'subjects': executor.submit(pkl_data_to_df, new_subjects_path),
            'teachers_new': executor.submit(pkl_data_to_df, new_teachers_path),
        }

        data = {}
        for key, future in futures.items():
            data[key] = future.result()

    # Choose teachers source: prefer new_teachers, else old, else infer
    teachers_new_df = data.get('teachers_new') if isinstance(data.get('teachers_new'), pd.DataFrame) else pd.DataFrame()
    teachers_old_df = data.get('teachers_old') if isinstance(data.get('teachers_old'), pd.DataFrame) else pd.DataFrame()
    teachers_df = pd.DataFrame()
    if not teachers_new_df.empty:
        teachers_df = teachers_new_df
    elif not teachers_old_df.empty:
        teachers_df = teachers_old_df
    else:
        # Infer from subjects or grades if possible
        subjects_df = data.get('subjects', pd.DataFrame())
        grades_df = data.get('grades', pd.DataFrame())
        inferred = pd.DataFrame()
        if 'Teacher' in subjects_df.columns:
            inferred = pd.DataFrame({
                'Teacher': subjects_df['Teacher'].dropna().unique().tolist()
            })
            inferred['_id'] = inferred['Teacher']
        elif 'Teachers' in grades_df.columns:
            # explode teachers from grades
            tmp = grades_df[['Teachers']].copy()
            tmp = tmp[tmp['Teachers'].notna()]
            tmp = tmp.explode('Teachers') if tmp['Teachers'].apply(lambda x: isinstance(x, list)).any() else tmp
            inferred = pd.DataFrame({'_id': tmp['Teachers'].dropna().astype(str).unique().tolist()})
            inferred['Teacher'] = inferred['_id']
        teachers_df = inferred

    data['teachers'] = teachers_df

    load_time = time.time() - start_time
    st.success(f"📊 Data (new) loaded in {load_time:.2f} seconds")

    # Log ingestion results
    log_data = {
        'timestamp': time.time(),
        'load_time_seconds': load_time,
        'records_loaded': {
            'students_new': len(data['students']),
            'grades_new': len(data['grades']),
            'semesters': len(data['semesters']),
            'subjects_new': len(data['subjects']),
            'teachers': len(data['teachers'])
        }
    }

    os.makedirs('cache', exist_ok=True)
    with open('cache/ingestion_log.json', 'w') as f:
        json.dump(log_data, f, indent=2)

    return data

def get_incomplete_grades(data, filters):
    """Get students with incomplete grades (INC, Dropped, null)"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    teachers_df = data['teachers']

    if grades_df.empty:
        return pd.DataFrame()

    # Apply semester filter
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            grades_df = grades_df[grades_df["SemesterID"] == sem_id_arr[0]]

    # Apply faculty filter
    if filters.get("Faculty") != "All":
        teacher_id = teachers_df[teachers_df["Teacher"] == filters["Faculty"]]["_id"].values
        if len(teacher_id) > 0:
            grades_df = grades_df[grades_df["Teachers"].apply(lambda x: teacher_id[0] in x if isinstance(x, list) else x == teacher_id[0])]

    # Find incomplete grades
    def has_incomplete_grade(grades):
        if isinstance(grades, list):
            return any(g in ["INC", "Dropped", None] or pd.isna(g) for g in grades)
        return grades in ["INC", "Dropped", None] or pd.isna(grades)

    incomplete_df = grades_df[grades_df["Grades"].apply(has_incomplete_grade)].copy()

    if incomplete_df.empty:
        return pd.DataFrame()

    # Merge with students and other data
    result = incomplete_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")
    
    # Add semester info
    semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
    result["SemesterName"] = result["SemesterID"].map(semesters_dict)
    
    # Add teacher info
    teachers_dict = dict(zip(teachers_df["_id"], teachers_df["Teacher"]))
    result["TeacherName"] = result["Teachers"].apply(
        lambda x: teachers_dict.get(x[0] if isinstance(x, list) and x else x, "Unknown")
    )

    return result[["StudentID", "Name", "SubjectCodes", "Grades", "TeacherName", "SemesterName"]]

def show_registrar_new_tab9_info(data, students_df, semesters_df, teachers_df):
        st.subheader("⚠️ Incomplete Grades Report")
        st.markdown("Identify students with incomplete, dropped, or missing grades requiring attention")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
            semester = st.selectbox("Semester", semester_options, key="incomplete_semester")
        with col2:
            faculty_options = ["All"] + list(teachers_df["Teacher"].unique()) if not teachers_df.empty else ["All"]
            faculty = st.selectbox("Faculty", faculty_options, key="incomplete_faculty")
        
        if st.button("Apply Filters", key="incomplete_apply"):
            with st.spinner("Loading incomplete grades data..."):
                df = get_incomplete_grades(data, {"Semester": semester, "Faculty": faculty})

                # Summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_incomplete = len(df)
                    st.metric("Total Incomplete", f"{total_incomplete:,}")
                with col2:
                    unique_students = df["StudentID"].nunique() if not df.empty else 0
                    st.metric("Affected Students", f"{unique_students:,}")
                with col3:
                    unique_subjects = df["SubjectCodes"].nunique() if not df.empty else 0
                    st.metric("Affected Subjects", unique_subjects)
                with col4:
                    unique_teachers = df["TeacherName"].nunique() if not df.empty else 0
                    st.metric("Involved Faculty", unique_teachers)

                if not df.empty:
                    # Incomplete grades by type
                    def categorize_grade(grade):
                        if isinstance(grade, list):
                            for g in grade:
                                if g in ["INC", "Dropped", None] or pd.isna(g):
                                    return "Incomplete" if g == "INC" else "Dropped" if g == "Dropped" else "Missing"
                        elif grade in ["INC", "Dropped", None] or pd.isna(grade):
                            return "Incomplete" if grade == "INC" else "Dropped" if grade == "Dropped" else "Missing"
                        return "Other"

                    df["GradeType"] = df["Grades"].apply(categorize_grade)
                    grade_type_counts = df["GradeType"].value_counts()

                    # Pie chart for incomplete grade types
                    fig_pie = px.pie(
                        values=grade_type_counts.values,
                        names=grade_type_counts.index,
                        title="Distribution of Incomplete Grade Types",
                        color_discrete_map={
                            "Incomplete": "#FFA500",
                            "Dropped": "#DC143C",
                            "Missing": "#808080"
                        }
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                    # Bar chart by faculty
                    faculty_counts = df["TeacherName"].value_counts().head(10)
                    fig_bar = px.bar(
                        x=faculty_counts.index,
                        y=faculty_counts.values,
                        title="Incomplete Grades by Faculty (Top 10)",
                        labels={"x": "Faculty", "y": "Number of Incomplete Grades"}
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)

                    # Detailed data table
                    st.subheader("Detailed Incomplete Grades Report")
                    display_df = df[["StudentID", "Name", "SubjectCodes", "Grades", "TeacherName", "SemesterName", "GradeType"]].copy()
                    st.dataframe(display_df, use_container_width=True)

                else:
                    grade_type_counts = pd.Series()
                    display_df = pd.DataFrame()
                    st.success("✅ No incomplete grades found for the selected filters")

                # Export options (always show)
                col1, col2, col3 = st.columns(3)
                with col1:
                    add_incomplete_grades_pdf_download_button(df, semester, faculty, total_incomplete, unique_students, unique_subjects, unique_teachers, grade_type_counts)
               
        else:
            st.info("👆 Click 'Apply Filters' to load incomplete grades data")
