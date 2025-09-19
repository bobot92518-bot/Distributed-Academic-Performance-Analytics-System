import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import time
import json
import matplotlib.pyplot as plt
from reportlab.platypus import Image
import tempfile
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

def get_enrollment_trends(data, filters):
    """Get enrollment trends by semester and course"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if grades_df.empty or semesters_df.empty:
        return pd.DataFrame()

    # Merge grades with students and semesters
    merged = grades_df.merge(students_df, left_on="StudentID", right_on="_id", how="left")
    merged = merged.merge(semesters_df, left_on="SemesterID", right_on="_id", how="left")

    # Apply course filter
    if filters.get("Course") != "All":
        merged = merged[merged["Course"] == filters["Course"]]

    # Drop duplicates to ensure unique students per semester
    merged = merged.drop_duplicates(subset=['StudentID', 'SemesterID'])

    # Count students per semester and course
    enrollment = merged.groupby(['Semester', 'SchoolYear', 'Course']).size().reset_index(name='Count')
    enrollment = enrollment.sort_values(['SchoolYear', 'Semester'])

    return enrollment

def create_enrollment_trends_pdf(
    enrollment_df,
    total_enrollment,
    avg_per_semester,
    max_enrollment,
    unique_semesters,
    course_filter=None,
    yoy_analysis=False
):
    """Generate PDF report for enrollment trends"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
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

    # --- Title ---
    elements.append(Paragraph("📉 Enrollment Trends Analysis Report", title_style))
    elements.append(Spacer(1, 12))

    # --- Report Information ---
    filter_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Course Filter:</b> {course_filter if course_filter and course_filter != "All" else "All Courses"}<br/>
    <b>Analysis Type:</b> {"Year-over-Year" if yoy_analysis else "Overall Trends"}
    """
    elements.append(Paragraph(filter_info, info_style))
    elements.append(Spacer(1, 20))

    # --- Overall Summary Statistics ---
    elements.append(Paragraph("Overall Enrollment Summary", header_style))
    elements.append(Spacer(1, 6))

    overall_stats_data = [
        ["Metric", "Value"],
        ["Total Enrollment", f"{total_enrollment:,}"],
        ["Average per Semester", f"{avg_per_semester:.0f}"],
        ["Peak Enrollment", f"{max_enrollment:,}"],
        ["Semesters Tracked", unique_semesters]
    ]
    overall_table = Table(overall_stats_data, repeatRows=1)
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(overall_table)
    elements.append(Spacer(1, 20))

    # Key Insights Section
    # Move Key Insights to the bottom of the PDF
    # Remove from here and append later after all other content

    # ===================== YOY ANALYSIS =====================
    if yoy_analysis:
        elements.append(Paragraph("Year-over-Year Enrollment Trends", header_style))
        elements.append(Spacer(1, 6))

        # Table with SchoolYear + Semester + Course + Count
        yoy_data = [enrollment_df.columns.tolist()] + enrollment_df.values.tolist()
        yoy_table = Table(yoy_data, repeatRows=1)
        yoy_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(yoy_table)
        elements.append(Spacer(1, 20))

        # --- Line Chart (YoY Trends) ---
        
        fig, ax = plt.subplots(figsize=(8, 4))

        for year, group in enrollment_df.groupby("SchoolYear"):
            ax.plot(group["Semester"], group["Count"], marker="o", label=str(year))

        ax.set_title("Enrollment Trends by School Year", fontsize=14, fontweight="bold")
        ax.set_xlabel("Semester")
        ax.set_ylabel("Enrollment Count")
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(title="School Year")

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=6.5*inch, height=3.5*inch))
        elements.append(Spacer(1, 20))

        # --- Enrollment by Course (Table + Pie) ---
        elements.append(Paragraph("Enrollment by Course", header_style))
        elements.append(Spacer(1, 6))

        course_breakdown = enrollment_df.groupby("Course")["Count"].sum().reset_index().sort_values("Count", ascending=False)

        # Table
        course_data = [course_breakdown.columns.tolist()] + course_breakdown.values.tolist()
        course_table = Table(course_data, repeatRows=1)
        course_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(course_table)
        elements.append(Spacer(1, 12))

        # Pie chart
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(course_breakdown["Count"],
               labels=course_breakdown["Course"],
               autopct='%1.1f%%',
               startangle=90)
        ax.set_title("Enrollment Distribution by Course")

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=4.5*inch, height=4.5*inch))
        elements.append(Spacer(1, 20))

    # ===================== OVERALL ANALYSIS =====================
    else:
        elements.append(Paragraph("Overall Enrollment by Semester", header_style))
        elements.append(Spacer(1, 6))

        overall_enrollment = enrollment_df.groupby("Semester")["Count"].sum().reset_index()
        overall_enrollment = overall_enrollment.sort_values("Semester")

        # Table
        table_data = [overall_enrollment.columns.tolist()] + overall_enrollment.values.tolist()
        enrollment_table = Table(table_data, repeatRows=1)
        enrollment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(enrollment_table)
        elements.append(Spacer(1, 20))

        # --- Line Chart (Overall) ---
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(overall_enrollment["Semester"], overall_enrollment["Count"],
                marker="o", color="blue", label="Overall Enrollment")
        ax.set_title("Overall Enrollment Trends", fontsize=14, fontweight="bold")
        ax.set_xlabel("Semester")
        ax.set_ylabel("Enrollment Count")
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend()

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=6.5*inch, height=3.5*inch))
        elements.append(Spacer(1, 20))

        # --- Bar Chart (Overall per Semester) ---
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(overall_enrollment["Semester"], overall_enrollment["Count"], color="skyblue")
        ax.set_title("Enrollment by Semester", fontsize=14, fontweight="bold")
        ax.set_xlabel("Semester")
        ax.set_ylabel("Enrollment Count")
        ax.grid(True, axis="y", linestyle="--", alpha=0.6)

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=6.5*inch, height=3.5*inch))
        elements.append(Spacer(1, 20))

        # --- Enrollment by Course (Table + Pie) ---
        elements.append(Paragraph("Enrollment by Course", header_style))
        elements.append(Spacer(1, 6))

        course_breakdown = enrollment_df.groupby("Course")["Count"].sum().reset_index().sort_values("Count", ascending=False)

        # Table
        course_data = [course_breakdown.columns.tolist()] + course_breakdown.values.tolist()
        course_table = Table(course_data, repeatRows=1)
        course_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(course_table)
        elements.append(Spacer(1, 12))

        # Pie chart
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(course_breakdown["Count"],
               labels=course_breakdown["Course"],
               autopct='%1.1f%%',
               startangle=90)
        ax.set_title("Enrollment Distribution by Course")

        img_bytes = BytesIO()
        plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        img_bytes.seek(0)

        elements.append(Image(img_bytes, width=4.5*inch, height=4.5*inch))
        elements.append(Spacer(1, 20))

    # Key Insights Section (moved to bottom)
    elements.append(Paragraph("🔍 Key Insights", header_style))
    elements.append(Spacer(1, 6))

    total = total_enrollment
    avg = avg_per_semester
    peak = max_enrollment
    semesters = unique_semesters

    insights_text = f"""
<b>Enrollment Trends Overview:</b><br/>
• Total enrollment across all semesters: {total:,} students.<br/>
• Average enrollment per semester: {avg:.0f} students, indicating {'stable' if avg > 50 else 'moderate'} enrollment levels.<br/>
• Peak enrollment reached {peak:,} students, showing {'strong demand' if peak > 100 else 'steady growth'} in certain periods.<br/>
• Data tracked across {semesters} semesters, providing {'comprehensive' if semesters > 10 else 'initial'} trend analysis.<br/>
<br/>
<b>Trend Analysis:</b><br/>
• {'Increasing trends suggest growing popularity and effective marketing.' if avg > 50 else 'Stable enrollment indicates consistent demand for programs.'}<br/>
• {'High peak periods may require additional resources during those semesters.' if peak > 100 else 'Enrollment patterns are manageable with current capacity.'}<br/>
• Year-over-year analysis helps identify seasonal patterns and long-term growth.<br/>
<br/>
<b>Recommendations:</b><br/>
• Monitor enrollment patterns to optimize resource allocation.<br/>
• Use trend data for strategic planning and capacity management.<br/>
• Focus on high-demand courses to maximize enrollment potential.
"""

    elements.append(Paragraph(insights_text, info_style))
    elements.append(Spacer(1, 20))

    # --- Build PDF ---
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_enrollment_trends_pdf_download_button(enrollment_df, total_enrollment, avg_per_semester, max_enrollment, unique_semesters, course_filter=None, yoy_analysis=False):
    """Add a download button for enrollment trends PDF export"""

    if enrollment_df is None or enrollment_df.empty:
        st.warning("No enrollment trends data available to export to PDF.")
        return

    try:
        pdf_data = create_enrollment_trends_pdf(enrollment_df, total_enrollment, avg_per_semester, max_enrollment, unique_semesters, course_filter, yoy_analysis)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Enrollment_Trends_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of enrollment trends",
            key="download_pdf_tab8"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab8_info(data, students_df, semesters_df):
    st.subheader("📉 Enrollment Trend Analysis")
    st.markdown("Track student enrollment patterns across semesters and courses")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
        course = st.selectbox("Course", course_options, key="enrollment_course")
    with col2:
        yoy = st.checkbox("Show Year-over-Year Analysis", value=False, key="enrollment_yoy")

    if st.button("Apply Filters", key="enrollment_apply"):
        with st.spinner("Loading enrollment trends data..."):
            # Get enrollment trends data
            students_df_local = data['students']
            grades_df_local = data['grades']
            semesters_df_local = data['semesters']

            if grades_df_local.empty or semesters_df_local.empty:
                df = pd.DataFrame()
            else:
                # Merge grades with students and semesters
                merged = grades_df_local.merge(students_df_local, left_on="StudentID", right_on="_id", how="left")
                merged = merged.merge(semesters_df_local, left_on="SemesterID", right_on="_id", how="left")

                # Apply course filter
                if course != "All":
                    merged = merged[merged["Course"] == course]

                # Count students per semester and course
                df = merged.groupby(['Semester', 'SchoolYear', 'Course']).size().reset_index(name='Count')
                df = df.sort_values(['SchoolYear', 'Semester'])

                # Get unique students count
                unique_students = merged.drop_duplicates('StudentID').shape[0]

            if not df.empty:
                # === Summary statistics ===
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_enrollment = unique_students
                    st.metric("Total Enrollment", f"{total_enrollment:,}")
                with col2:
                    avg_per_semester = df["Count"].mean()
                    st.metric("Avg per Semester", f"{avg_per_semester:.0f}")
                with col3:
                    max_enrollment = df["Count"].max()
                    st.metric("Peak Enrollment", f"{max_enrollment:,}")
                with col4:
                    unique_semesters = len(df["Semester"].unique())
                    st.metric("Semesters Tracked", unique_semesters)

                # === Charts and Tables ===
                if yoy:
                    # Year-over-year analysis
                    st.subheader("Year-over-Year Enrollment Data")
                    st.dataframe(df, use_container_width=True)

                    fig_line = px.line(
                        df,
                        x="Semester",
                        y="Count",
                        color="SchoolYear",
                        title="Enrollment Trends by School Year",
                        markers=True
                    )
                    fig_line.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    # Overall enrollment trend
                    overall_enrollment = df.groupby("Semester")["Count"].sum().reset_index()
                    overall_enrollment = overall_enrollment.sort_values("Semester")

                    # Data table
                    st.subheader("Enrollment Data by Semester")
                    st.dataframe(overall_enrollment, use_container_width=True)

                    fig_line = px.line(
                        overall_enrollment,
                        x="Semester",
                        y="Count",
                        title="Overall Enrollment Trends",
                        markers=True
                    )
                    fig_line.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_line, use_container_width=True)

                    # Area chart for cumulative enrollment
                    overall_enrollment["Cumulative"] = overall_enrollment["Count"].cumsum()
                    fig_area = px.area(
                        overall_enrollment,
                        x="Semester",
                        y="Cumulative",
                        title="Cumulative Enrollment Over Time"
                    )
                    st.plotly_chart(fig_area, use_container_width=True)

                    # Bar chart for semester comparison
                    fig_bar = px.bar(
                        overall_enrollment,
                        x="Semester",
                        y="Count",
                        title="Enrollment by Semester",
                        color="Count",
                        color_continuous_scale="Blues"
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)

                # Course breakdown
                if course == "All":
                    course_breakdown = df.groupby("Course")["Count"].sum().reset_index().sort_values("Count", ascending=False)

                    st.subheader("Enrollment by Course")
                    st.dataframe(course_breakdown, use_container_width=True)

                    fig_pie = px.pie(
                        course_breakdown,
                        values="Count",
                        names="Course",
                        title="Enrollment Distribution by Course"
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                st.subheader("📄 Export Report")
                add_enrollment_trends_pdf_download_button(df, total_enrollment, avg_per_semester, max_enrollment, unique_semesters, course, yoy)

            else:
                st.warning("No enrollment data available")
    else:
        st.info("👆 Click 'Apply Filters' to load enrollment trends data")
