import streamlit as st
import streamlit.components.v1 as components
### Ensure we scroll back to the teacher evaluation section if hash is present
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache
from pages.Registrar.pdf_helper import generate_pdf
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester
from global_utils import result_records_to_dataframe
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from io import BytesIO
from datetime import datetime
import altair as alt
import time
import json

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

@st.cache_data(ttl=300)
def load_curriculums_df():
    """Load curriculums from pickle and return a DataFrame with expected columns."""
    if not os.path.exists(curriculums_cache):
        return pd.DataFrame()
    data = pd.read_pickle(curriculums_cache)
    df = pd.DataFrame(data) if isinstance(data, list) else data
    for col in ["courseCode", "courseName", "curriculumYear", "subjects"]:
        if col not in df.columns:
            df[col] = None
    return df

# def show_registrar_new_tab1_info(data, students_df, semesters_df, teachers_df):
#     grades_df = data['grades']
#     subjects_df = data['subjects']

#     st.subheader("👩‍🏫 Class List per Teacher")
#     st.markdown("Select a teacher, then pick a subject to see the class roster.")

#     cc1, cc2 = st.columns(2)
#     with cc1:
#         cl_teacher_opts = teachers_df["Teacher"].dropna().unique().tolist() if not teachers_df.empty else []
#         cl_teacher = st.selectbox("Teacher", cl_teacher_opts, key="cls1_teacher")
#     with cc2:
#         st.write("")

#     # Build expanded roster for teacher and subject selection
#     def _expand_rows_cls1(gr):
#         out = []
#         grades_list = gr.get("Grades", [])
#         subjects_list = gr.get("SubjectCodes", [])
#         teachers_list = gr.get("Teachers", [])
#         grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
#         subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
#         teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
#         n = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
#         for i in range(n):
#             out.append({
#                 "StudentID": gr.get("StudentID"),
#                 "SemesterID": gr.get("SemesterID"),
#                 "TeacherID": teachers_list[i] if i < len(teachers_list) else None,
#                 "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
#             })
#         return out

#     # Merge necessary student info
#     cl_merged = grades_df.merge(students_df[["_id", "Name", "Course", "YearLevel"]], left_on="StudentID", right_on="_id", how="left")

#     # No term filters in Tab 1 (use all records for teacher/subject)

#     # Expand rows
#     cls_expanded = []
#     for _, rr in cl_merged.iterrows():
#         cls_expanded.extend(_expand_rows_cls1(rr))

#     if not cls_expanded:
#         st.info("No records found. Adjust filters above.")
#     else:
#         cl_df = pd.DataFrame(cls_expanded)
#         # Maps
#         tmap = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
#         smap = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
#         semmap = dict(zip(semesters_df["_id"], semesters_df["Semester"])) if not semesters_df.empty else {}
#         name_map = dict(zip(students_df["_id"], students_df["Name"])) if not students_df.empty else {}
#         course_map = dict(zip(students_df["_id"], students_df["Course"])) if not students_df.empty else {}
#         year_map = dict(zip(students_df["_id"], students_df["YearLevel"])) if not students_df.empty else {}

#         cl_df["Teacher"] = cl_df["TeacherID"].map(tmap).fillna(cl_df["TeacherID"].astype(str))
#         cl_df["Subject"] = cl_df["SubjectCode"].map(smap).fillna(cl_df["SubjectCode"].astype(str))
#         cl_df["Semester"] = cl_df["SemesterID"].map(semmap).fillna(cl_df["SemesterID"].astype(str))
#         cl_df["StudentName"] = cl_df["StudentID"].map(name_map).fillna(cl_df["StudentID"].astype(str))
#         cl_df["Course"] = cl_df["StudentID"].map(course_map)
#         cl_df["YearLevel"] = cl_df["StudentID"].map(year_map)

#         # Filter by teacher
#         if cl_teacher != "All":
#             cl_df = cl_df[cl_df["Teacher"] == cl_teacher]

#         if cl_df.empty:
#             st.info("No classes for the selected teacher.")
#         else:
#             # Subject radio under selected teacher
#             subj_opts = sorted(cl_df["Subject"].dropna().unique().tolist())
#             sel_subj = st.radio("Subject", subj_opts, horizontal=False, key="cls1_subject_radio") if subj_opts else None

#             if not sel_subj:
#                 st.info("Choose a subject to view the class list.")
#             else:
#                 df_class = cl_df[cl_df["Subject"] == sel_subj]
#                 st.success(f"Found {df_class['StudentID'].nunique()} students for {sel_subj}.")
#                 show_cols = ["StudentID", "StudentName", "Course", "YearLevel", "Semester"]
#                 st.subheader("Students by Year Level and Semester")
#                 for year_level in sorted(df_class["YearLevel"].dropna().unique().tolist()):
#                     st.markdown(f"**Year Level: {year_level}**")
#                     df_year = df_class[df_class["YearLevel"] == year_level]
#                     for sem_name in sorted(df_year["Semester"].dropna().unique().tolist()):
#                         st.markdown(f"- Semester: {sem_name}")
#                         df_sem = df_year[df_year["Semester"] == sem_name]
#                         st.dataframe(
#                             df_sem[show_cols]
#                                 .sort_values(["StudentName"])
#                                 .reset_index(drop=True),
#                             use_container_width=True
#                         )

def create_grade_pdf(df, faculty_name, semester_filter=None, subject_filter=None, is_new_curriculum=False):
    """Generate PDF report for grades data"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
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
    title_text = "Class List Report"
    if is_new_curriculum:
        title_text += " (New Curriculum)"
    else:
        title_text += " (Old Curriculum)"
    
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 12))
    
    # Report Information
    report_info = f"""
    <b>Faculty:</b> {faculty_name}<br/>
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Semester Filter:</b> {semester_filter if semester_filter and semester_filter != " - All Semesters - " else "All Semesters"}<br/>
    <b>Subject Filter:</b> {subject_filter if subject_filter and subject_filter != " - All Subjects - " else "All Subjects"}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))
    
    if df.empty:
        elements.append(Paragraph("No grades found for the selected criteria.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
    
    # Apply filters
    filtered_df = df.copy()
    if semester_filter and semester_filter != " - All Semesters - ":
        filtered_df = filtered_df[filtered_df['semester'] + " - " + filtered_df['schoolYear'].astype(str) == semester_filter]
    
    if subject_filter and subject_filter != " - All Subjects - ":
        filtered_df = filtered_df[filtered_df['subjectCode'] + " - " + filtered_df['subjectDescription'] == subject_filter]
    
    if filtered_df.empty:
        elements.append(Paragraph("No grades found for the selected filters.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
    
    year_map = {
        1: "1st Year",
        2: "2nd Year", 
        3: "3rd Year",
        4: "4th Year",
        5: "5th Year",
    }
    
    # Group by semester and subject
    grouped = filtered_df.groupby(['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel', 'section'])

    for i, ((semester, school_year, subject_code, subject_desc, subject_year_level, section), group) in enumerate(grouped):

        if i > 0:
            elements.append(PageBreak())

        # Subject header
        subject_header = f"{semester} - {school_year} | {subject_code} {section} - {subject_desc}"
        if subject_year_level and subject_year_level > 0:
            subject_header += f" ({year_map.get(subject_year_level, '')} Subject)"
        
        elements.append(Paragraph(subject_header, header_style))
        elements.append(Spacer(1, 12))
        
        # Prepare table data
        table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
        table_data['Grade_num'] = pd.to_numeric(table_data['grade'], errors='coerce')
        table_data['Student ID'] = table_data['StudentID'].astype(str)
        
        # Calculate statistics
        valid_grades = table_data["Grade_num"][(table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)]
        
        total_students = len(table_data)
        class_average = valid_grades.mean() if not valid_grades.empty else 0
        highest_grade = valid_grades.max() if not valid_grades.empty else "N/A"
        lowest_grade = valid_grades.min() if not valid_grades.empty else "N/A"
        
        # Statistics table
        stats_data = [
            ['Total Students', 'Class Average', 'Highest Grade', 'Lowest Grade'],
            [str(total_students), 
             f"{class_average:.1f}" if class_average > 0 else "N/A",
             str(highest_grade) if highest_grade != "N/A" else "N/A",
             str(lowest_grade) if lowest_grade != "N/A" else "N/A"]
        ]
        
        stats_table = Table(stats_data, colWidths=[1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 20))
        
        # Prepare grade data for main table
        def format_grade(grade):
            if pd.isna(grade) or grade == 0:
                return "Not Set"
            else:
                return f"{grade:.1f}"
        
        table_data['Formatted_Grade'] = table_data['Grade_num'].apply(format_grade)
        
        # Prepare main data table
        if is_new_curriculum:
            year_taken = year_map.get(subject_year_level, "")
            year_course = (table_data["YearLevel"].map(year_map).fillna("") + " - " + table_data["Course"])
            
            main_data = [['Student ID', 'Student Name', 'Year-Course', 'Year Taken', 'Grade']]
            for _, row in table_data.iterrows():
                main_data.append([
                    row['Student ID'],
                    row['studentName'],
                    f"{year_map.get(row['YearLevel'], '')} - {row['Course']}",
                    year_taken,
                    row['Formatted_Grade']
                ])
        else:
            main_data = [['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade']]
            for _, row in table_data.iterrows():
                main_data.append([
                    row['Student ID'],
                    row['studentName'],
                    row['Course'],
                    year_map.get(row['YearLevel'], ''),
                    row['Formatted_Grade']
                ])
        
        wrap_style = ParagraphStyle(
            'WrapStyle',
            fontSize=8,
            leading=10,
            alignment=0  # Left alignment
        )

        # Example: convert each cell into a Paragraph
        def wrap_text(cell):
            if isinstance(cell, str):
                return Paragraph(cell, wrap_style)
            return cell

        main_data_wrapped = [[wrap_text(cell) for cell in row] for row in main_data]
        # Create main table
        main_table = Table(main_data_wrapped, colWidths=[1*inch, 2*inch, 1.5*inch, 1*inch, 0.8*inch])
        
        # Style the main table
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Add conditional formatting for grades
        for row_idx, row_data in enumerate(main_data[1:], 1):
            grade_text = row_data[-1]
            if grade_text != "Not Set":
                try:
                    grade_value = float(grade_text)
                    if grade_value < 75:
                        table_style.append(('BACKGROUND', (-1, row_idx), (-1, row_idx), colors.lightcoral))
                    else:
                        table_style.append(('BACKGROUND', (-1, row_idx), (-1, row_idx), colors.lightgreen))
                except ValueError:
                    pass
        
        main_table.setStyle(TableStyle(table_style))
        elements.append(main_table)
        elements.append(Spacer(1, 20))
        
        # Add grade distribution summary
        if not valid_grades.empty:
            
            grade_brackets = {
                "95-100": (95, 100),
                "90-94": (90, 94),
                "85-89": (85, 89),
                "80-84": (80, 84),
                "75-79": (75, 79),
                "Below 75": (0, 74)
            }
            
            total_valid = len(valid_grades)
            bracket_stats = []
            for bracket, (min_g, max_g) in grade_brackets.items():
                if bracket == "Below 75":
                    count = len(valid_grades[valid_grades < 75])
                else:
                    count = len(valid_grades[(valid_grades >= min_g) & (valid_grades <= max_g)])
                percentage = (count / total_valid * 100) if total_valid > 0 else 0
                bracket_stats.append([bracket, str(count), f"{percentage:.1f}%"])
            
            dist_table = Table(
                [["Grade Bracket", "No. of Students", "Percentage"]] + bracket_stats,
                colWidths=[1.5*inch, 1.5*inch, 1.5*inch]
            )
            dist_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ]))
            
            elements.append(Paragraph("<b>📊 Grade Distribution by Brackets</b>", info_style))
            elements.append(Spacer(1, 6))
            elements.append(dist_table)
            elements.append(Spacer(1, 20))
            
            
            passing_count = len(valid_grades[valid_grades >= 75])
            failing_count = len(valid_grades[valid_grades < 75])
            
            distribution_text = f"""
            <b>Grade Distribution Summary:</b><br/>
            • Students with grades ≥ 75: {passing_count}<br/>
            • Students with grades &lt; 75: {failing_count}<br/>
            • Students without grades: {total_students - len(valid_grades)}
            """
            elements.append(Paragraph(distribution_text, info_style))
            
            # Define bins (100 down to min grade, step = 5)
            max_grade = 100
            min_grade = int(valid_grades.min())
            bins = list(range(max_grade, min_grade - 1, -5))  # descending

            # Use pd.cut with 5-point bins
            categories = pd.cut(
                valid_grades,
                bins=list(range(min_grade - (min_grade % 5), max_grade + 5, 5)),
                right=True,
                include_lowest=True
            )

            hist_counts = categories.value_counts().sort_index(ascending=False)

            # Chart
            drawing = Drawing(500, 250)
            bc = VerticalBarChart()
            bc.x = 50
            bc.y = 30
            bc.height = 180
            bc.width = 380
            bc.data = [list(hist_counts.values)]
            bc.categoryAxis.categoryNames = [
                f"{int(interval.left)}–{int(interval.right)}"
                for interval in hist_counts.index
            ]

            # Style
            bc.valueAxis.valueMin = 0
            bc.barWidth = 15
            bc.valueAxis.valueStep = 1

            # Add chart to PDF
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("<b>📈 Grade Distribution Histogram (5-point bins)</b>", info_style))
            drawing.add(bc)
            elements.append(drawing)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_pdf_download_button(df, faculty_name, semester_filter=None, subject_filter=None, is_new_curriculum=False):
    """Add a download button for PDF export"""
    
    if df is None or df.empty:
        st.warning("No data available to export to PDF.")
        return
    
    try:
        pdf_data = create_grade_pdf(df, faculty_name, semester_filter, subject_filter, is_new_curriculum)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "New" if is_new_curriculum else "Old"
        filename = f"Class_List_{curriculum_type}_{timestamp}.pdf"
        
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of the displayed grades",
            key="download_pdf_tab1" 
        )
        
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def display_grades_table(is_new_curriculum, df, semester_filter = None, subject_filter = None, selected_teacher=None):
    """Display grades in Streamlit format with PDF export option"""

    # Use selected teacher for faculty name in PDF, fallback to session user
    faculty_name = selected_teacher if selected_teacher else st.session_state.get('user_data', {}).get('Name', '')
    
    if df.empty:
        st.warning("No grades found for the selected criteria.")
        return
    
    # Apply filters
    filtered_df = df.copy()
    if semester_filter and semester_filter != " - All Semesters - ":
        filtered_df = filtered_df[filtered_df['semester'] + " - " + filtered_df['schoolYear'].astype(str) == semester_filter]
    
    if subject_filter and subject_filter != " - All Subjects - ":
        filtered_df = filtered_df[filtered_df['subjectCode'] + " - " + filtered_df['subjectDescription'] == subject_filter]
    
    if filtered_df.empty:
        st.warning("No grades found for the selected filters.")
        return
    
    year_map = {
        1: "1st Year",
        2: "2nd Year",
        3: "3rd Year",
        4: "4th Year",
        5: "5th Year",
    }
    subject_year_map = {
        0: "",
        1: "| &nbsp; &nbsp; 1st Year Subject",
        2: "| &nbsp; &nbsp; 2nd Year Subject",
        3: "| &nbsp; &nbsp; 3rd Year Subject",
        4: "| &nbsp; &nbsp; 4th Year Subject",
        5: "| &nbsp; &nbsp; 5th Year Subject",
    }
    
    # Group by semester and subject
    for (semester, school_year, subject_code, subject_desc, SubjectYearLevel, section), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel', 'section']
    ):
        
        with st.expander(f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code} {section} &nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc} &nbsp;&nbsp; {subject_year_map.get(SubjectYearLevel, "")}", expanded=True):
            
            table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
            table_data.columns = ['Student ID', 'Student Name', 'Course', 'YearLevel', 'Grade']
            
            table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
            table_data['Student ID'] = table_data['Student ID'].astype(str)
            
            course_column = ""
            year_column = ""
            if is_new_curriculum:
                year_column = "Year Taken"
                table_data[f"{year_column}"] = year_map.get(SubjectYearLevel, "")
                course_column = "Year-Course"
                table_data[f"{course_column}"] = (table_data["YearLevel"].map(year_map).fillna("") + " - " + table_data["Course"])
            else:
                course_column = "Course"
                year_column = "Year Level"
                table_data[f"{year_column}"] = table_data["YearLevel"].map(year_map).fillna("")
            
            def grade_with_star(grade):
                if pd.isna(grade) or grade == 0:
                    return "Not Set"
                else:
                    if grade < 75:
                        return f"🛑 {grade}"
                    else:
                        return f"⭐ {grade}"   

            table_data['Grade'] = table_data['Grade_num'].apply(grade_with_star)

            # Final display
            display_df = table_data[['Student ID', 'Student Name', f"{course_column}", f"{year_column}", 'Grade']]

            # Quick stats
            valid_grades = table_data["Grade_num"][
                (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
            ]

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Students", len(table_data))
            with col2:
                st.metric("Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "N/A")
            with col3:
                st.metric("Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "N/A")
            with col4:
                st.metric("Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "N/A")

            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            if not valid_grades.empty:
                st.markdown("**📊 Grade Distribution by Brackets**")
                
                # Define grade brackets
                grade_brackets = {
                    "95-100 (%)": (95, 100),
                    "90-94 (%)": (90, 94),
                    "85-89 (%)": (85, 89),
                    "80-84 (%)": (80, 84),
                    "75-79 (%)": (75, 79),
                    "Below 75 (%)": (0, 74)
                }
                
                # Calculate counts and percentages for each bracket
                total_valid = len(valid_grades)
                bracket_stats = {}
                
                for bracket_name, (min_grade, max_grade) in grade_brackets.items():
                    if bracket_name == "Below 75 (%)":
                        count = len(valid_grades[valid_grades < 75])
                    else:
                        count = len(valid_grades[(valid_grades >= min_grade) & (valid_grades <= max_grade)])
                    
                    percentage = (count / total_valid * 100) if total_valid > 0 else 0
                    bracket_stats[bracket_name] = f"{percentage:.1f}%"
                
                # Create a single row table for the brackets
                percentage_df = pd.DataFrame([{
                    "Subject Code": subject_code,
                    "Subject Name": subject_desc,
                    **bracket_stats,
                    "Total Students": len(table_data)
                }])
                
                st.dataframe(percentage_df, use_container_width=True, hide_index=True)
            
            st.markdown("**📈 Class Grade Distribution Histogram**")

            # Keep your grade_category function exactly as is
            def grade_category(g):
                if pd.isna(g) or g == 0:
                    return "Not Set"
                elif g >= 95:
                    return "95-100"
                elif g >= 90:
                    return "90-94"
                elif g >= 85:
                    return "85-89"
                elif g >= 80:
                    return "80-84"
                elif g >= 75:
                    return "75-79"
                else:
                    return "Below 75"

            table_data["Grade_Range"] = table_data["Grade_num"].apply(grade_category)

            # Histogram using bins
            hist_chart = (
                alt.Chart(table_data[table_data["Grade_Range"] != "Not Set"])
                .mark_bar(opacity=0.8)
                .encode(
                    x=alt.X(
                        'Grade_num:Q',
                        bin=alt.Bin(maxbins=20),
                        title='Grade Range'
                    ),
                    y=alt.Y('count():Q', title='Number of Students'),
                    color=alt.Color(
                        'Grade_Range:N',
                        title="Grade Category",
                        scale=alt.Scale(
                            domain=[
                                "95-100",
                                "90-94",
                                "85-89",
                                "80-84",
                                "75-79",
                                "Below 75"
                            ],
                            range=[
                                "#28a745",  # green
                                "#17a2b8",  # teal
                                "#007bff",  # blue
                                "#ffc107",  # yellow
                                "#fd7e14",  # orange
                                "#dc3545"   # red
                            ]
                        )
                    ),
                    tooltip=['count():Q', 'Grade_Range:N']
                )
                .properties(
                    height=300,
                    title="Grade Distribution Histogram"
                )
            )

            st.altair_chart(hist_chart, use_container_width=True)
            
    st.subheader("📄 Export Report")
    add_pdf_download_button(df, faculty_name, semester_filter, subject_filter, is_new_curriculum)

def show_registrar_new_tab1_info(data, students_df, semesters_df, teachers_df):
    new_curriculum = True  # Since using new data loaders

    # Initialize Tab 1 specific session state
    if 'tab1_grades_df' not in st.session_state:
        st.session_state.tab1_grades_df = None
    if 'tab1_current_faculty' not in st.session_state:
        st.session_state.tab1_current_faculty = None
    if 'tab1_loaded_filters' not in st.session_state:
        st.session_state.tab1_loaded_filters = {}

    st.subheader("👥 Class List per Teacher")
    st.markdown("Select a teacher, then pick a semester and subject to see the class roster.")

    # Select teacher first
    teacher_options = teachers_df["Teacher"].dropna().unique().tolist() if not teachers_df.empty else []
    selected_teacher = st.selectbox("👨‍🏫 Select Teacher", teacher_options, key="registrar_teacher_select")

    if selected_teacher:
        semesters = get_semesters_list(new_curriculum)
        subjects = get_subjects_by_teacher(selected_teacher, new_curriculum)

        col1, col2 = st.columns([1, 1])

        with col1:
            semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
            selected_semester_display = st.selectbox(
                "📅 Select Semester",
                semester_options,
                key="main_semester"
            )
        with col2:
            subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
            selected_subject_display = st.selectbox(
                "📚 Select Subject",
                subject_options,
                key="main_subject"
            )

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

        if st.button("📊 Load Class", type="secondary", key="tab1_load_button1"):
            with st.spinner("Loading grades data..."):

                if new_curriculum:
                    results = get_new_student_grades_by_subject_and_semester(current_faculty=selected_teacher, semester_id=selected_semester_id, subject_code=selected_subject_code)
                else:
                    results = get_student_grades_by_subject_and_semester(current_faculty=selected_teacher, semester_id=selected_semester_id, subject_code=selected_subject_code)

                if results:
                    df = result_records_to_dataframe(results)

                    # Store in TAB 1 SPECIFIC session state keys
                    st.session_state.tab1_grades_df = df
                    st.session_state.tab1_current_faculty = selected_teacher
                    st.session_state.tab1_loaded_filters = {
                        'semester': selected_semester_display,
                        'subject': selected_subject_display
                    }

                else:
                    st.warning(f"No grades found for {selected_teacher} in the selected semester.")
                    st.session_state.tab1_grades_df = None

    # Display grades if they exist in Tab 1 session state
    if st.session_state.tab1_grades_df is not None and not st.session_state.tab1_grades_df.empty:
        # Show current filter info for Tab 1
        if st.session_state.tab1_loaded_filters:
            st.info(f"📋 Tab 1 - Showing grades for: **{st.session_state.tab1_loaded_filters.get('semester', 'All')}** | **{st.session_state.tab1_loaded_filters.get('subject', 'All')}**")

        st.divider()
        display_grades_table(new_curriculum, st.session_state.tab1_grades_df,
                           st.session_state.tab1_loaded_filters.get('semester'),
                           st.session_state.tab1_loaded_filters.get('subject'),
                           st.session_state.tab1_current_faculty)

    elif st.session_state.tab1_grades_df is not None and st.session_state.tab1_grades_df.empty:
        st.warning("No students found matching the current filters.")
    else:
        st.info("👆 Select a teacher, then filters and click 'Load Class' to view student data.")
