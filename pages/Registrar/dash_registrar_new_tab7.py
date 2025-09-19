import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.pdf_helper import generate_pdf
import time
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from reportlab.lib import colors
from datetime import datetime
import textwrap

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

def get_pass_fail_distribution(data, filters):
    """Get pass/fail distribution by subject"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']
    subjects_df = data['subjects']

    if grades_df.empty:
        return pd.DataFrame()

    # Merge with students for course filtering
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")

    # Apply filters
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            merged = merged[merged["SemesterID"] == sem_id_arr[0]]

    if filters.get("SchoolYear") != "All":
        try:
            school_year_value = int(filters["SchoolYear"])
            sem_ids_by_year = semesters_df[semesters_df["SchoolYear"] == school_year_value]["_id"].tolist()
            if sem_ids_by_year:
                merged = merged[merged["SemesterID"].isin(sem_ids_by_year)]
        except (ValueError, TypeError):
            pass

    if filters.get("Course") != "All" and not merged.empty:
        merged = merged[merged["Course"] == filters["Course"]]

    # Calculate pass/fail for each grade entry
    def process_grades(grades, subject_codes):
        results = []
        if isinstance(grades, list) and isinstance(subject_codes, list):
            for i, grade in enumerate(grades):
                if i < len(subject_codes) and isinstance(grade, (int, float)) and not pd.isna(grade):
                    subject_code = subject_codes[i] if i < len(subject_codes) else "Unknown"
                    status = "Pass" if grade >= 75 else "Fail"
                    results.append({
                        'SubjectCode': subject_code,
                        'Grade': grade,
                        'Status': status
                    })
        return results

    # Expand grades into individual records
    expanded_data = []
    for _, row in merged.iterrows():
        grade_results = process_grades(row['Grades'], row['SubjectCodes'])
        for result in grade_results:
            expanded_data.append({
                'StudentID': row['StudentID'],
                'StudentName': row['Name'],
                'Course': row['Course'],
                'SubjectCode': result['SubjectCode'],
                'Grade': result['Grade'],
                'Status': result['Status']
            })

    if not expanded_data:
        return pd.DataFrame()

    df = pd.DataFrame(expanded_data)
    
    # Map subject codes to descriptions
    if not subjects_df.empty:
        subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"]))
        df['Subject'] = df['SubjectCode'].map(subjects_dict).fillna(df['SubjectCode'])
    else:
        df['Subject'] = df['SubjectCode']

    return df
def create_pass_fail_distribution_pdf(
    subject_summary_df,
    total_records,
    pass_count,
    fail_count,
    pass_rate,
    course_filter=None,
    school_year_filter=None,
    semester_filter=None
):
    """Generate PDF report for pass/fail distribution by subject"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=18
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
    elements.append(Paragraph("📈 Subject Pass/Fail Distribution Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Info
    filter_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Course Filter:</b> {course_filter if course_filter and course_filter != "All" else "All Courses"}<br/>
    <b>School Year Filter:</b> {school_year_filter if school_year_filter and school_year_filter != "All" else "All Years"}<br/>
    <b>Semester Filter:</b> {semester_filter if semester_filter and semester_filter != "All" else "All Semesters"}
    """
    elements.append(Paragraph(filter_info, info_style))
    elements.append(Spacer(1, 20))

    # --- Overall Summary
    elements.append(Paragraph("Overall Performance Summary", header_style))
    elements.append(Spacer(1, 6))

    overall_stats_data = [
        ["Metric", "Value"],
        ["Total Records", f"{total_records:,}"],
        ["Pass Count", f"{pass_count:,}"],
        ["Fail Count", f"{fail_count:,}"],
        ["Overall Pass Rate (%)", f"{pass_rate:.1f}%"]
    ]
    overall_table = Table(overall_stats_data, repeatRows=1)
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(overall_table)
    elements.append(Spacer(1, 20))

    # --- Subject-wise Summary
    elements.append(Paragraph("Subject-wise Pass/Fail Distribution", header_style))
    elements.append(Spacer(1, 6))

    subj_table_data = [subject_summary_df.columns.tolist()] + subject_summary_df.values.tolist()
    subj_table = Table(subj_table_data, repeatRows=1)
    subj_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(subj_table)
    elements.append(Spacer(1, 20))

    # --- Bar Chart (Dashboard-style)
    elements.append(Paragraph("Pass/Fail Distribution by Subject", header_style))
    elements.append(Spacer(1, 6))

    if not subject_summary_df.empty:
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot Pass and Fail grouped (like Plotly dashboard)
        bar_width = 0.35
        x = np.arange(len(subject_summary_df["Subject"]))

        ax.bar(x - bar_width/2, subject_summary_df["Pass"], bar_width, label="Pass", color="#2E8B57")
        ax.bar(x + bar_width/2, subject_summary_df["Fail"], bar_width, label="Fail", color="#DC143C")

        ax.set_xticks(x)
        ax.set_xticklabels(subject_summary_df["Subject"], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Number of Students")
        ax.set_title("Pass/Fail Distribution by Subject", fontsize=14, fontweight="bold")
        ax.legend()

        plt.tight_layout()
        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=7.5*inch, height=4.5*inch))
        elements.append(Spacer(1, 12))

    # --- Pie Chart
    elements.append(Paragraph("Overall Pass/Fail Distribution", header_style))
    elements.append(Spacer(1, 6))

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie([pass_count, fail_count], labels=['Pass', 'Fail'],
           autopct='%1.1f%%', colors=['#2E8B57', '#DC143C'])
    ax.set_title("Overall Pass/Fail Distribution")

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format="png")
    plt.close(fig)
    img_bytes.seek(0)
    elements.append(Image(img_bytes, width=4.5*inch, height=4.5*inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
def add_pass_fail_distribution_pdf_download_button(subject_summary_df, total_records, pass_count, fail_count, pass_rate, course_filter=None, school_year_filter=None, semester_filter=None):
    """Add a download button for pass/fail distribution PDF export"""

    if subject_summary_df is None or subject_summary_df.empty:
        st.warning("No pass/fail distribution data available to export to PDF.")
        return

    try:
        pdf_data = create_pass_fail_distribution_pdf(subject_summary_df, total_records, pass_count, fail_count, pass_rate, course_filter, school_year_filter, semester_filter)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Pass_Fail_Distribution_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of subject pass/fail distribution",
            key="download_pdf_tab7"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab7_info(data, students_df, semesters_df):
        st.subheader("📈 Subject Pass/Fail Distribution")
        st.markdown("Analyze pass/fail rates by subject with detailed breakdowns and visualizations")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
            course = st.selectbox("Course", course_options, key="passfail_course")
        with col2:
            year_options = ["All"] + list(semesters_df["SchoolYear"].unique()) if not semesters_df.empty else ["All"]
            year = st.selectbox("School Year", year_options, key="passfail_year")
        with col3:
            if year != "All" and not semesters_df.empty:
                sems_by_year = semesters_df[semesters_df["SchoolYear"] == year]["Semester"].unique().tolist()
                semester_options = ["All"] + sems_by_year
            else:
                semester_options = ["All"] + (list(semesters_df["Semester"].unique()) if not semesters_df.empty else [])
            semester = st.selectbox("Semester", semester_options, key="passfail_semester")

        if st.button("Apply Filters", key="passfail_apply"):
            with st.spinner("Loading pass/fail distribution data..."):
                df = get_pass_fail_distribution(data, {"Semester": semester, "Course": course, "SchoolYear": year})

                if not df.empty:
                    # === Summary statistics ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_records = len(df)
                        st.metric("Total Records", f"{total_records:,}")
                    with col2:
                        pass_count = len(df[df["Status"] == "Pass"])
                        st.metric("Pass Count", f"{pass_count:,}")
                    with col3:
                        fail_count = len(df[df["Status"] == "Fail"])
                        st.metric("Fail Count", f"{fail_count:,}")
                    with col4:
                        pass_rate = (pass_count / total_records * 100) if total_records > 0 else 0
                        st.metric("Pass Rate", f"{pass_rate:.1f}%")

                    # === Pass/Fail distribution by subject (calculated summary) ===
                    subject_summary = df.groupby(["Subject", "Status"]).size().unstack(fill_value=0).reset_index()
                    subject_summary["Total"] = subject_summary["Pass"] + subject_summary["Fail"]
                    subject_summary["Pass Rate (%)"] = (subject_summary["Pass"] / subject_summary["Total"] * 100).round(2)
                    subject_summary["Fail Rate (%)"] = (subject_summary["Fail"] / subject_summary["Total"] * 100).round(2)
                    summary_table = subject_summary[["Subject", "Pass Rate (%)", "Fail Rate (%)"]]

                    # === Pass/Fail Rate Table ===
                    st.subheader("📊 Pass/Fail Rates by Subject")
                    st.dataframe(summary_table, use_container_width=True)

                    # === Bar Chart ===
                    fig_bar = px.bar(
                        subject_summary,
                        x="Subject",
                        y=["Pass", "Fail"],
                        title="Pass/Fail Distribution by Subject",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"},
                        barmode="group"
                    )
                    fig_bar.update_layout(
                        xaxis_tickangle=-45,
                        yaxis_title="Number of Students",
                        xaxis_title="Subject"
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                    # === Pie Chart ===
                    status_counts = df["Status"].value_counts()
                    fig_pie = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Overall Pass/Fail Distribution",
                        color_discrete_map={"Pass": "#2E8B57", "Fail": "#DC143C"}
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                    st.subheader("📄 Export Report")
                    add_pass_fail_distribution_pdf_download_button(subject_summary, total_records, pass_count, fail_count, pass_rate, course, year, semester)

                else:
                    st.warning("No data available for the selected filters")
        else:
            st.info("👆 Click 'Apply Filters' to load pass/fail distribution data")
