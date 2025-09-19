import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import os
import matplotlib.pyplot as plt
import json
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
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

def get_top_performers(data, filters):
    """Get top performers per program"""
    students_df = data['students']
    grades_df = data['grades']
    semesters_df = data['semesters']

    if grades_df.empty or students_df.empty:
        return pd.DataFrame()

    # Apply semester filter
    if filters.get("Semester") != "All":
        sem_id_arr = semesters_df[semesters_df["Semester"] == filters["Semester"]]["_id"].values
        if len(sem_id_arr) > 0:
            grades_df = grades_df[grades_df["SemesterID"] == sem_id_arr[0]]

    # Calculate GPA for each student
    gpa_data = {}
    for _, grade_row in grades_df.iterrows():
        student_id = grade_row["StudentID"]
        grades = grade_row.get("Grades", [])
        
        if isinstance(grades, list) and grades:
            # Filter numeric grades
            numeric_grades = [g for g in grades if isinstance(g, (int, float)) and not pd.isna(g)]
            if numeric_grades:
                avg_gpa = sum(numeric_grades) / len(numeric_grades)
                if student_id in gpa_data:
                    gpa_data[student_id].append(avg_gpa)
                else:
                    gpa_data[student_id] = [avg_gpa]

    # Create results dataframe
    results = []
    for student_id, gpa_list in gpa_data.items():
        student_info = students_df[students_df["_id"] == student_id]
        if not student_info.empty:
            student = student_info.iloc[0]
            final_gpa = sum(gpa_list) / len(gpa_list)
            year_level = student["YearLevel"]
            if isinstance(year_level, list):
                year_level = year_level[0] if year_level else 0
            results.append({
                "Name": student["Name"],
                "Course": student["Course"],
                "YearLevel": year_level,
                "GPA": round(final_gpa, 2)
            })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    
    # Get top 10 per program
    top_performers = df.sort_values(by="GPA", ascending=False).groupby("Course").head(10)
    
    return top_performers

def create_top_performers_pdf(df, semester_filter, total_performers, avg_gpa, max_gpa, unique_courses):
    """Generate PDF report for top performers"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(595.27, 841.89),  # A4 in points
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue,
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        alignment=TA_LEFT,
        textColor=colors.black,
    )

    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        alignment=TA_LEFT,
    )

    # Title
    elements.append(Paragraph("🏆 Top Performers Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Information
    report_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Semester Filter:</b> {semester_filter if semester_filter != "All" else "All Semesters"}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))

    # Summary Statistics
    elements.append(Paragraph("Summary Statistics", header_style))
    elements.append(Spacer(1, 6))

    summary_data = [
        ["Metric", "Value"],
        ["Total Top Performers", f"{total_performers:,}"],
        ["Average GPA", f"{avg_gpa:.2f}"],
        ["Highest GPA", f"{max_gpa:.2f}"],
        ["Programs Represented", unique_courses],
    ]
    summary_table = Table(summary_data, repeatRows=1)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Program Performance Comparison
    elements.append(Paragraph("Program Performance Comparison", header_style))
    elements.append(Spacer(1, 6))

    program_stats = df.groupby("Course").agg({"GPA": ["mean", "max", "count"]}).round(2)
    program_stats.columns = ["Average GPA", "Highest GPA", "Top Performers Count"]
    program_stats = program_stats.sort_values("Average GPA", ascending=False)

    program_data = [program_stats.columns.tolist()] + program_stats.reset_index().values.tolist()
    program_table = Table(program_data, repeatRows=1)
    program_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(program_table)
    elements.append(Spacer(1, 20))

    # 📊 Add GPA Distribution Chart (Boxplot)
    elements.append(Paragraph("📊 GPA Distribution by Program", header_style))
    fig, ax = plt.subplots(figsize=(8, 4))
    df.boxplot(column="GPA", by="Course", ax=ax, grid=False)

    ax.set_title("GPA Distribution by Program")
    ax.set_ylabel("GPA")
    plt.suptitle("")
    plt.xticks(rotation=45)
    ax.grid(True, which="major", linestyle="--", alpha=0.7, axis="y")

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    img_bytes.seek(0)
    elements.append(Image(img_bytes, width=6 * inch, height=3 * inch))
    elements.append(Spacer(1, 20))

    # 📈 Scatter Plot: Top Performers by Year Level and GPA
    elements.append(Paragraph("📈 Top Performers by Year Level and GPA", header_style))
    fig, ax = plt.subplots(figsize=(8, 4))

    for course, group in df.groupby("Course"):
        ax.scatter(
            group["YearLevel"],
            group["GPA"],
            s=group["GPA"] * 10,  # bubble size
            label=course,
            alpha=0.6,
        )

    ax.set_title("Top Performers by Year Level and GPA")
    ax.set_xlabel("Year Level")
    ax.set_ylabel("GPA")
    ax.legend(title="Course", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.7)

    img_bytes = BytesIO()
    plt.savefig(img_bytes, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    img_bytes.seek(0)
    elements.append(Image(img_bytes, width=6 * inch, height=3 * inch))
    elements.append(Spacer(1, 20))

    # Top Performers by Program
    elements.append(Paragraph("Top Performers by Program", header_style))
    elements.append(Spacer(1, 6))

    df_ranked = df.copy()
    df_ranked["Rank"] = (
        df_ranked.groupby("Course")["GPA"].rank(method="dense", ascending=False).astype(int)
    )
    df_ranked = df_ranked.sort_values(["Course", "Rank"])

    for course in df_ranked["Course"].unique():
        course_data = df_ranked[df_ranked["Course"] == course].head(10)
        elements.append(Paragraph(f"📚 {course}", header_style))
        elements.append(Spacer(1, 6))

        course_display = course_data[["Rank", "Name", "YearLevel", "GPA"]].copy()
        course_display.columns = ["Rank", "Student Name", "Year Level", "GPA"]

        course_table_data = [course_display.columns.tolist()] + course_display.values.tolist()
        course_table = Table(course_table_data, repeatRows=1)
        course_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgreen),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(course_table)
        elements.append(Spacer(1, 12))

    # Key Insights Section moved to bottom
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("🔍 Key Insights", header_style))
    elements.append(Spacer(1, 6))

    total = total_performers
    avg = avg_gpa
    highest = max_gpa
    programs = unique_courses

    insights_text = f"""
<b>Academic Excellence Overview:</b><br/>
• Total top performers identified: {total:,} across all programs.<br/>
• Average GPA among top performers: {avg:.2f}, indicating high academic standards.<br/>
• Highest GPA achieved: {highest:.2f}, showcasing exceptional student performance.<br/>
• Programs with top performers: {programs}, demonstrating broad academic excellence.<br/>
<br/>
<b>Performance Analysis:</b><br/>
• {'Outstanding academic performance' if avg > 3.5 else 'Strong academic achievement' if avg > 3.0 else 'Good academic performance with room for excellence'}.<br/>
• {'Exceptional individual achievement with GPA above 3.8' if highest > 3.8 else 'Strong individual performance with GPA above 3.5' if highest > 3.5 else 'Solid individual achievement'}.<br/>
• {'Comprehensive academic excellence across multiple programs' if programs > 5 else 'Focused academic strength in key programs'}.<br/>
<br/>
<b>Recommendations:</b><br/>
• Recognize and reward top performers to motivate continued excellence.<br/>
• Study successful learning strategies of top performers for broader application.<br/>
• Develop advanced academic programs for high-achieving students.<br/>
• Share best practices across programs to elevate overall academic standards.
"""

    elements.append(Paragraph(insights_text, info_style))
    elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_top_performers_pdf_download_button(df, semester_filter, total_performers, avg_gpa, max_gpa, unique_courses):
    """Add a download button for top performers PDF export"""

    if df is None or df.empty:
        st.warning("No top performers data available to export to PDF.")
        return

    try:
        pdf_data = create_top_performers_pdf(df, semester_filter, total_performers, avg_gpa, max_gpa, unique_courses)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Top_Performers_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of top performers",
            key="download_pdf_tab11"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab11_info(data, students_df, semesters_df):
        st.subheader("🏆 Top Performers per Program")
        st.markdown("Identify and celebrate the highest achieving students across all programs")
        
        # Filters
        semester_options = ["All"] + list(semesters_df["Semester"].unique()) if not semesters_df.empty else ["All"]
        top_semester = st.selectbox("Semester (optional)", semester_options, key="top_semester_tab6")
        
        if st.button("Load Top Performers", key="top_apply_tab6"):
            with st.spinner("Loading top performers data..."):
                df = get_top_performers(data, {"Semester": top_semester})
                
                if not df.empty:
                    # === Summary statistics ===
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        total_performers = len(df)
                        st.metric("Total Top Performers", f"{total_performers:,}")
                    with col2:
                        avg_gpa = df["GPA"].mean()
                        st.metric("Average GPA", f"{avg_gpa:.2f}")
                    with col3:
                        max_gpa = df["GPA"].max()
                        st.metric("Highest GPA", f"{max_gpa:.2f}")
                    with col4:
                        unique_courses = df["Course"].nunique()
                        st.metric("Programs Represented", unique_courses)
                    
                    # === Leaderboard ===
                    st.subheader("🏅 Top Performers Leaderboard")
                    df_ranked = df.copy()
                    df_ranked["Rank"] = df_ranked.groupby("Course")["GPA"].rank(method="dense", ascending=False).astype(int)
                    df_ranked = df_ranked.sort_values(["Course", "Rank"])
                    
                    for course in df_ranked["Course"].unique():
                        course_data = df_ranked[df_ranked["Course"] == course].head(10)
                        st.subheader(f"📚 {course}")
                        display_data = course_data[["Rank", "Name", "YearLevel", "GPA"]].copy()
                        display_data.columns = ["Rank", "Student Name", "Year Level", "GPA"]
                        st.dataframe(display_data, use_container_width=True, hide_index=True)
                    
                    # === Charts ===
                    fig_box = px.box(
                        df, 
                        x="Course", 
                        y="GPA",
                        title="GPA Distribution by Program",
                        color="Course"
                    )
                    fig_box.update_layout(
                        xaxis_tickangle=-45,
                        xaxis_title="Program",
                        yaxis_title="GPA"
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
                    
                    fig_scatter = px.scatter(
                        df, 
                        x="YearLevel", 
                        y="GPA",
                        color="Course",
                        size="GPA",
                        title="Top Performers by Year Level and GPA",
                        hover_data=["Name", "Course", "GPA"]
                    )
                    fig_scatter.update_layout(
                        xaxis_title="Year Level",
                        yaxis_title="GPA"
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    # === Program comparison ===
                    program_stats = df.groupby("Course").agg({
                        "GPA": ["mean", "max", "count"]
                    }).round(2)
                    program_stats.columns = ["Average GPA", "Highest GPA", "Top Performers Count"]
                    program_stats = program_stats.sort_values("Average GPA", ascending=False)
                    
                    st.subheader("Program Performance Comparison")
                    st.dataframe(program_stats, use_container_width=True)

                    # PDF Export
                    st.subheader("📄 Export Report")
                    add_top_performers_pdf_download_button(df, top_semester, total_performers, avg_gpa, max_gpa, unique_courses)

                else:
                    st.warning("No top performers data available")
        else:
            st.info("👆 Click 'Load Top Performers' to view top performing students")
