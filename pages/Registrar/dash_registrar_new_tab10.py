import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.Get_Academic_Helper import get_academic_standing
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from reportlab.lib import colors
from datetime import datetime
import io

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

def get_retention_dropout(data, filters):
    """Get retention and dropout rates by year level using academic standing logic"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if students_df.empty or grades_df.empty or semesters_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Get latest semester
    latest_sem = semesters_df.sort_values(by=["SchoolYear", "Semester"], ascending=False).iloc[0]

    # Use get_academic_standing to get academic standing data
    academic_filters = {
        "Semester": latest_sem["Semester"],
        "SchoolYear": str(latest_sem["SchoolYear"])
    }
    if filters.get("Course") != "All":
        academic_filters["Course"] = filters["Course"]

    academic_df = get_academic_standing(academic_filters)

    # Apply course filter to students
    filtered_students = students_df.copy()
    if filters.get("Course") != "All":
        filtered_students = filtered_students[filtered_students["Course"] == filters["Course"]]

    # Ensure YearLevel is scalar
    filtered_students["YearLevel"] = filtered_students["YearLevel"].apply(
        lambda x: x[0] if isinstance(x, list) and x else x
    )

    # Merge with academic standing
    merged = filtered_students.merge(academic_df, left_on="Name", right_on="Name", how="left")

    # Determine status based on academic standing and activity
    def determine_status(row):
        status = row.get("Status", "")
        # Check if student has any grades at all
        any_grades = grades_df[grades_df["StudentID"] == row["_id"]]
        if any_grades.empty:
            return "Dropped"  # No grades ever

        if pd.isna(status) or status == "":
            # Has grades but no GPA data for latest semester
            return "Retained"
        elif status == "Good Standing":
            return "Retained"
        else:  # Probation or other
            return "At Risk"

    merged["Status"] = merged.apply(determine_status, axis=1)

    # Summary by status
    summary = merged["Status"].value_counts().reset_index()
    summary.columns = ["Status", "Count"]

    # Summary by year level
    year_level_summary = merged.groupby(["YearLevel", "Status"]).size().reset_index(name="Count")

    # Ensure that pivot always has Retained/Dropped/At Risk columns
    if not year_level_summary.empty:
        pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
        for col in ["Retained", "Dropped", "At Risk"]:
            if col not in pivot.columns:
                pivot[col] = 0
        year_level_summary = pivot.reset_index().melt(id_vars="YearLevel", value_vars=["Retained", "Dropped", "At Risk"],
                                                     var_name="Status", value_name="Count")
    return summary, year_level_summary

def create_retention_pdf(summary, year_level_summary, course_filter, total_students, retained_count,
                         at_risk_count, dropped_count, retention_rate, charts=None):
    """Generate PDF report for retention and dropout rates including charts."""

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    from datetime import datetime
    import numpy as np
    import pandas as pd
    import plotly.io as pio

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

    # Styles
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
    elements.append(Paragraph("🔄 Student Status Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Info
    report_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Course Filter:</b> {course_filter if course_filter != "All" else "All Courses"}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))

    # Summary Statistics Table
    elements.append(Paragraph("Summary Statistics", header_style))
    elements.append(Spacer(1, 6))
    summary_data = [
        ["Metric", "Value"],
        ["Total Students", f"{total_students:,}"],
        ["Retained", f"{retained_count:,}"],
        ["At Risk", f"{at_risk_count:,}"],
        ["Dropped", f"{dropped_count:,}"],
        ["Retention Rate", f"{retention_rate:.1f}%"]
    ]
    summary_table = Table(summary_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Overall Summary Table
    elements.append(Paragraph("Overall Student Status Summary", header_style))
    elements.append(Spacer(1, 6))
    summary_display = summary.copy()
    summary_display["Percentage"] = (summary_display["Count"] / total_students * 100).round(1)
    summary_display.columns = ["Status", "Count", "Percentage (%)"]
    overall_data = [summary_display.columns.tolist()] + summary_display.values.tolist()
    overall_table = Table(overall_data, repeatRows=1)
    overall_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(overall_table)
    elements.append(Spacer(1, 20))

    # Year Level Analysis
    if not year_level_summary.empty:
        elements.append(Paragraph("Student Status Analysis by Year Level", header_style))
        elements.append(Spacer(1, 6))

        year_level_pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
        for col in ["Retained", "At Risk", "Dropped"]:
            if col not in year_level_pivot.columns:
                year_level_pivot[col] = 0
        year_level_pivot = year_level_pivot[["Retained", "At Risk", "Dropped"]]
        year_level_pivot["Total"] = year_level_pivot.sum(axis=1)
        year_level_pivot["Retention_Rate"] = np.where(
            year_level_pivot["Total"] > 0,
            (year_level_pivot["Retained"] / year_level_pivot["Total"] * 100).round(1),
            0
        )

        display_df = year_level_pivot[["Retained", "At Risk", "Dropped", "Total", "Retention_Rate"]].copy()
        display_df.columns = ["Retained", "At Risk", "Dropped", "Total", "Retention Rate (%)"]

        year_level_data = [display_df.columns.tolist()] + display_df.values.tolist()
        year_level_table = Table(year_level_data, repeatRows=1)
        year_level_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(year_level_table)
        elements.append(Spacer(1, 20))

    # Add Charts as Images
    if charts:
        for i, (title, fig) in enumerate(charts):
            # Add a page break between charts if needed
            if i > 0:
                elements.append(PageBreak())

            elements.append(Paragraph(f"📊 {title}", header_style))
            elements.append(Spacer(1, 6))

            # Convert Plotly figure to image (PNG)
            img_bytes = pio.to_image(fig, format="png", scale=2)
            img_buffer = BytesIO(img_bytes)
            elements.append(Image(img_buffer, width=400, height=300))
            elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_retention_pdf_download_button(summary, year_level_summary, course_filter, total_students, retained_count, at_risk_count, dropped_count, retention_rate, charts=None):
    """Add a download button for retention PDF export"""

    if summary is None or summary.empty:
        st.warning("No retention data available to export to PDF.")
        return

    try:
        pdf_data = create_retention_pdf(summary, year_level_summary, course_filter, total_students, retained_count, at_risk_count, dropped_count, retention_rate, charts)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Student_Status_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of student status",
            key="download_pdf_tab10"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab10_info(data, students_df, semesters_df):
    st.subheader("🔄 Retention and Dropout Rates")
    st.markdown("Analyze student retention and dropout patterns by year level and course")
    
    # Filters
    course_options = ["All"] + list(students_df["Course"].unique()) if not students_df.empty else ["All"]
    course = st.selectbox("Course", course_options, key="retention_course")
    
    if st.button("Apply Filters", key="retention_apply"):
        with st.spinner("Loading retention & dropout data..."):
            summary, year_level_summary = get_retention_dropout(data, {"Course": course})
            
            if not summary.empty:
                charts = []  # Collect charts for PDF
                
                # Calculate metrics
                total_students = summary["Count"].sum()
                retained_count = summary[summary["Status"] == "Retained"]["Count"].iloc[0] if "Retained" in summary["Status"].values else 0
                at_risk_count = summary[summary["Status"] == "At Risk"]["Count"].iloc[0] if "At Risk" in summary["Status"].values else 0
                dropped_count = summary[summary["Status"] == "Dropped"]["Count"].iloc[0] if "Dropped" in summary["Status"].values else 0
                retention_rate = (retained_count / total_students * 100) if total_students > 0 else 0

                # Summary metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Students", f"{total_students:,}")
                with col2:
                    st.metric("Retained", f"{retained_count:,}")
                with col3:
                    st.metric("At Risk", f"{at_risk_count:,}")
                with col4:
                    st.metric("Dropped", f"{dropped_count:,}")
                with col5:
                    st.metric("Retention Rate", f"{retention_rate:.1f}%")

                # Overall pie chart
                fig_pie = px.pie(
                    values=summary["Count"].values,
                    names=summary["Status"].values,
                    title="Overall Student Status",
                    color_discrete_map={"Retained": "#2E8B57", "At Risk": "#FFA500", "Dropped": "#DC143C"}
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                charts.append(("Overall Student Status", fig_pie))

                # Year level analysis
                if not year_level_summary.empty:
                    year_level_pivot = year_level_summary.pivot(index="YearLevel", columns="Status", values="Count").fillna(0)
                    for col in ["Retained", "At Risk", "Dropped"]:
                        if col not in year_level_pivot.columns:
                            year_level_pivot[col] = 0
                    year_level_pivot = year_level_pivot[["Retained", "At Risk", "Dropped"]]

                    # Bar chart
                    fig_bar = px.bar(
                        year_level_pivot.reset_index(),
                        x="YearLevel",
                        y=["Retained", "At Risk", "Dropped"],
                        title="Student Status by Year Level",
                        color_discrete_map={"Retained": "#2E8B57", "At Risk": "#FFA500", "Dropped": "#DC143C"},
                        barmode="group"
                    )
                    fig_bar.update_layout(xaxis_title="Year Level", yaxis_title="Number of Students")
                    st.plotly_chart(fig_bar, use_container_width=True)
                    charts.append(("Student Status by Year Level", fig_bar))

                    # Retention Rate (Retained vs others)
                    year_level_pivot["Total"] = year_level_pivot["Retained"] + year_level_pivot["At Risk"] + year_level_pivot["Dropped"]
                    year_level_pivot["Retention_Rate"] = np.where(
                        year_level_pivot["Total"] > 0,
                        (year_level_pivot["Retained"] / year_level_pivot["Total"] * 100).round(1),
                        0
                    )

                    fig_line = px.line(
                        year_level_pivot.reset_index(),
                        x="YearLevel",
                        y="Retention_Rate",
                        title="Retention Rate by Year Level",
                        markers=True
                    )
                    fig_line.update_layout(
                        xaxis_title="Year Level",
                        yaxis_title="Retention Rate (%)",
                        yaxis=dict(range=[0, 100])
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
                    charts.append(("Retention Rate by Year Level", fig_line))

                    # Data table
                    st.subheader("Student Status Analysis by Year Level")
                    display_df = year_level_pivot[["Retained", "At Risk", "Dropped", "Total", "Retention_Rate"]].copy()
                    display_df.columns = ["Retained", "At Risk", "Dropped", "Total", "Retention Rate (%)"]
                    st.dataframe(display_df, use_container_width=True)
                
                # Overall summary table
                st.subheader("Overall Retention Summary")
                summary_display = summary.copy()
                summary_display["Percentage"] = (summary_display["Count"] / total_students * 100).round(1)
                summary_display.columns = ["Status", "Count", "Percentage (%)"]
                st.dataframe(summary_display, use_container_width=True)

                # PDF Export
                st.subheader("📄 Export Report")
                add_retention_pdf_download_button(summary, year_level_summary, course, total_students, retained_count, at_risk_count, dropped_count, retention_rate, charts)

            else:
                st.warning("No retention data available")
    else:
        st.info("👆 Click 'Apply Filters' to load retention & dropout data")
