import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.pdf_helper import generate_pdf
import time
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from io import BytesIO
from datetime import datetime

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

def get_academic_standing(data, filters):
    """Get academic standing data based on filters with proper GPA calculation"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']

    if students_df.empty or grades_df.empty:
        return pd.DataFrame()

    # Merge grades with students to get course information
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            sem_id_val = str(sem_id_arr[0])
            merged = merged[merged["SemesterID"].astype(str) == sem_id_val]

    if filters.get("SchoolYear") != "All":
        try:
            school_year_value = int(filters["SchoolYear"]) if isinstance(filters["SchoolYear"], str) else filters["SchoolYear"]
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"] == school_year_value]["_id"].astype(str).tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]
        except (ValueError, TypeError):
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"].astype(str) == str(filters["SchoolYear"])]["_id"].astype(str).tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].astype(str).isin(sem_ids_by_year)]

    # Filter by Course
    if filters.get("Course") != "All" and not merged.empty:
        merged = merged[merged["Course"] == filters["Course"]]

    # Aggregate grades per student per semester to avoid duplicates
    if merged.empty:
        return pd.DataFrame()

    # Define function to calculate GPA and total units per student per semester
    def calculate_gpa_and_units(group):
        grades = group["Grades"].tolist()
        # Flatten grades if nested lists
        flat_grades = []
        for g in grades:
            if isinstance(g, list):
                flat_grades.extend([x for x in g if isinstance(x, (int, float)) and not pd.isna(x)])
            elif isinstance(g, (int, float)) and not pd.isna(g):
                flat_grades.append(g)
        gpa = sum(flat_grades) / len(flat_grades) if flat_grades else 0
        total_units = len(flat_grades)
        return pd.Series({"GPA": gpa, "TotalUnits": total_units})

    agg = merged.groupby(["StudentID", "SemesterID"]).apply(calculate_gpa_and_units).reset_index()

    # Merge aggregated GPA and units back with student info
    student_info = students_df[["_id", "Name", "Course"]]
    agg = agg.merge(student_info, left_on="StudentID", right_on="_id", how="left")

    # Add semester and school year info
    semesters_dict = dict(zip(semesters_df["_id"], semesters_df["Semester"]))
    years_dict = dict(zip(semesters_df["_id"], semesters_df["SchoolYear"]))
    agg["Semester"] = agg["SemesterID"].map(semesters_dict)
    agg["SchoolYear"] = agg["SemesterID"].map(years_dict)

    # Determine academic status with proper thresholds
    def get_academic_status(gpa: float) -> str:
        if gpa >= 90:
            return "Dean's List"
        elif gpa >= 75:
            return "Good Standing"
        else:
            return "Probation"

    agg["Status"] = agg["GPA"].apply(get_academic_status)

    # Add Subject column as empty or placeholder since aggregation loses subject details
    agg["Subject"] = ""

    # Select and order columns
    result = agg[["StudentID", "Name", "Course", "GPA", "TotalUnits", "Status", "Semester", "SchoolYear", "Subject"]]

    return result

def create_academic_standing_pdf(df, course_filter=None, school_year_filter=None, semester_filter=None):
    """Generate comprehensive PDF report for academic standing data"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        wordWrap='CJK'
    )
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        alignment=0,  # Left alignment
        textColor=colors.black
    )

    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=0  # Left alignment
    )

    # Title
    elements.append(Paragraph("Student Academic Standing Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Information
    filter_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Course Filter:</b> {course_filter if course_filter and course_filter != "All" else "All Courses"}<br/>
    <b>School Year Filter:</b> {school_year_filter if school_year_filter and school_year_filter != "All" else "All Years"}<br/>
    <b>Semester Filter:</b> {semester_filter if semester_filter and semester_filter != "All" else "All Semesters"}
    """
    elements.append(Paragraph(filter_info, info_style))
    elements.append(Spacer(1, 20))

    if df.empty:
        elements.append(Paragraph("No academic standing data found for the selected criteria.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # Overall Summary Statistics
    total_students = df['StudentID'].nunique()
    deans_list_count = len(df[df["Status"] == "Dean's List"])
    good_standing_count = len(df[df["Status"] == "Good Standing"])
    probation_count = len(df[df["Status"] == "Probation"])

    # Overall Statistics Table
    overall_stats_data = [
        ['Metric', 'Count', 'Percentage'],
        ['Total Students', str(total_students), '100%'],
        ["Dean's List", str(deans_list_count), f"{(deans_list_count/total_students*100):.1f}%" if total_students > 0 else "0%"],
        ['Good Standing', str(good_standing_count), f"{(good_standing_count/total_students*100):.1f}%" if total_students > 0 else "0%"],
        ['Probation', str(probation_count), f"{(probation_count/total_students*100):.1f}%" if total_students > 0 else "0%"]
    ]

    overall_table = Table(overall_stats_data, colWidths=[2*inch, 1.2*inch, 1.2*inch])
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(Paragraph("<b>📊 Overall Academic Standing Summary</b>", header_style))
    elements.append(Spacer(1, 6))
    elements.append(overall_table)
    elements.append(Spacer(1, 20))

    # Group by School Year for detailed analysis
    if not df.empty and 'SchoolYear' in df.columns:
        school_years = sorted(df['SchoolYear'].dropna().unique())

        for school_year in school_years:
            year_df = df[df['SchoolYear'] == school_year]

            if year_df.empty:
                continue

            elements.append(PageBreak())

            # School Year Header
            elements.append(Paragraph(f"Academic Year: {school_year}", header_style))
            elements.append(Spacer(1, 12))

            # Year Statistics
            year_total = year_df['StudentID'].nunique()
            year_deans = len(year_df[year_df["Status"] == "Dean's List"])
            year_good = len(year_df[year_df["Status"] == "Good Standing"])
            year_probation = len(year_df[year_df["Status"] == "Probation"])

            year_stats_data = [
                ['Metric', 'Count', 'Percentage'],
                ['Total Students', str(year_total), '100%'],
                ["Dean's List", str(year_deans), f"{(year_deans/year_total*100):.1f}%" if year_total > 0 else "0%"],
                ['Good Standing', str(year_good), f"{(year_good/year_total*100):.1f}%" if year_total > 0 else "0%"],
                ['Probation', str(year_probation), f"{(year_probation/year_total*100):.1f}%" if year_total > 0 else "0%"]
            ]

            year_table = Table(year_stats_data, colWidths=[2*inch, 1.2*inch, 1.2*inch])
            year_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(year_table)
            elements.append(Spacer(1, 20))

            # Top 10 Students for this year
            top10_year = (
                year_df.sort_values("GPA", ascending=False)
                .head(10)
            )

            if not top10_year.empty:
                elements.append(Paragraph("<b>🏆 Top 10 Performing Students</b>", info_style))
                elements.append(Spacer(1, 6))

                top10_data = [['Rank', 'Student Name', 'Course', 'GPA', 'Status']]
                for i, (_, row) in enumerate(top10_year.iterrows(), 1):
                    top10_data.append([
                        str(i),
                        Paragraph(str(row.get('Name', 'N/A')), cell_style),
                        Paragraph(str(row.get('Course', 'N/A')), cell_style),
                        f"{row.get('GPA', 0):.1f}",
                        str(row.get('Status', 'N/A'))
                    ])

                top10_table = Table(top10_data, colWidths=[0.5*inch, 2*inch, 1.5*inch, 0.8*inch, 1.2*inch])
                top10_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))

                elements.append(top10_table)
                elements.append(Spacer(1, 15))

            # Probation Students for this year
            probation_year = (
                year_df[year_df["Status"] == "Probation"]
                .sort_values("GPA", ascending=True)
                .head(10)
            )

            if not probation_year.empty:
                elements.append(Paragraph("<b>⚠️ Top 10 Students on Academic Probation</b>", info_style))
                elements.append(Spacer(1, 6))

                probation_data = [['Student Name', 'Course', 'GPA', 'Total Units']]
                for _, row in probation_year.iterrows():
                    probation_data.append([
                        Paragraph(str(row.get('Name', 'N/A')), cell_style),
                        Paragraph(str(row.get('Course', 'N/A')), cell_style),
                        f"{row.get('GPA', 0):.1f}",
                        str(row.get('TotalUnits', 0))
                    ])

                probation_table = Table(probation_data, colWidths=[2*inch, 1.5*inch, 0.8*inch, 1*inch])
                probation_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightcoral),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))

                elements.append(probation_table)
                elements.append(Spacer(1, 15))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_academic_standing_pdf_download_button(df, course_filter=None, school_year_filter=None, semester_filter=None):
    """Add a download button for academic standing PDF export"""

    # Always show the button, but with different behavior based on data availability
    button_key = "download_academic_pdf_tab6_enabled" if not (df is None or df.empty) else "download_academic_pdf_tab6_disabled"

    if df is None or df.empty:
        # Show disabled button when no data
        st.download_button(
            label="📄 Download Academic Standing Report (PDF)",
            data=b"",  # Empty data
            file_name="Academic_Standing_Report.pdf",
            mime="application/pdf",
            disabled=True,
            help="Apply filters first to generate the report",
            key=button_key
        )
        st.info("💡 Apply filters above to load data and enable PDF export.")
    else:
        try:
            pdf_data = create_academic_standing_pdf(df, course_filter, school_year_filter, semester_filter)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Academic_Standing_Report_{timestamp}.pdf"

            st.download_button(
                label="📄 Download Academic Standing Report (PDF)",
                data=pdf_data,
                file_name=filename,
                mime="application/pdf",
                type="secondary",
                help="Download a comprehensive PDF report of student academic standing",
                key="download_academic_pdf_tab6_enabled"
            )

        except Exception as e:
            st.error(f"Error generating PDF: {str(e)}")
            st.download_button(
                label="📄 Download Academic Standing Report (PDF)",
                data=b"",
                file_name="Academic_Standing_Report.pdf",
                mime="application/pdf",
                disabled=True,
                help="PDF generation failed due to data issues",
                key="download_academic_pdf_tab6_error"
            )

def show_registrar_new_tab6_info(data, students_df, semesters_df):
        grades_df = data['grades']

        st.subheader("📊 Student Academic Standing Report")
        st.markdown("View top performers and probationary students by school year.")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="academic_course")
        with col2:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("School Year", year_options, key="academic_year")
        with col3:
            if year != "All" and not semesters_df.empty:
                sems_by_year = semesters_df[semesters_df["SchoolYear"] == year]["Semester"].unique().tolist()
                semester_options = ["All"] + sems_by_year
            else:
                semester_options = ["All"] + (list(semesters_df["Semester"].unique()) if not semesters_df.empty else [])
            semester = st.selectbox("Semester", semester_options, key="academic_semester")

        # Initialize df as empty DataFrame for PDF button visibility
        df = pd.DataFrame()

        if st.button("Apply Filters", key="academic_apply"):
            with st.spinner("Loading academic standing data..."):
                df = get_academic_standing(data, {"Semester": semester, "Course": course, "SchoolYear": year})

                if not df.empty:
                    # === Summary Metrics ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_students = df['StudentID'].nunique()
                        st.metric("Total Students", total_students)
                    with col2:
                        deans_list = len(df[df["Status"] == "Dean's List"])
                        st.metric("Dean's List", deans_list)
                    with col3:
                        good_standing = len(df[df["Status"] == "Good Standing"])
                        st.metric("Good Standing", good_standing)
                    with col4:
                        probation = len(df[df["Status"] == "Probation"])
                        st.metric("Probation", probation)

                    # Group by School Year for detailed analysis
                    if 'SchoolYear' in df.columns:
                        school_years = sorted(df['SchoolYear'].dropna().unique())

                        for school_year in school_years:
                            year_df = df[df['SchoolYear'] == school_year]

                            if year_df.empty:
                                continue

                            st.markdown(f"### Academic Year: {school_year}")

                            # Top 10 Students for this year
                            top10_year = (
                                year_df.sort_values("GPA", ascending=False)
                                .head(10)
                            )

                            if not top10_year.empty:
                                st.markdown("**🏆 Top 10 Performing Students**")
                                # Display as table with selected columns
                                display_top10 = top10_year[['Name', 'Course', 'GPA', 'Status']].copy()
                                display_top10.insert(0, 'Rank', range(1, len(display_top10) + 1))
                                st.table(display_top10)

                            # Probation Students for this year
                            probation_year = (
                                year_df[year_df["Status"] == "Probation"]
                                .sort_values("GPA", ascending=True)
                                .head(10)
                            )

                            if not probation_year.empty:
                                st.markdown("**⚠️ Top 10 Students on Academic Probation**")
                                # Display as table with selected columns
                                display_probation = probation_year[['Name', 'Course', 'GPA', 'TotalUnits']].copy()
                                st.table(display_probation)
                    
                    # === Generate PDF Report Button (Always Visible) ===
                    st.markdown("### 📄 Export Report")
                    add_academic_standing_pdf_download_button(df, course, year, semester)

                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load academic standing data")

