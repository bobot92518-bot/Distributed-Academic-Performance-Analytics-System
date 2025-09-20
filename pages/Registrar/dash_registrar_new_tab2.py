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

import time
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime
import matplotlib.pyplot as plt
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

def create_student_evaluation_pdf(student_info, transcript_data, all_future_display_data):
    """Generate PDF report for student evaluation data"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO
    from datetime import datetime
    import pandas as pd

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=18
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=18, spaceAfter=30, alignment=1,
        textColor=colors.darkblue
    )
    header_style = ParagraphStyle(
        'CustomHeader', parent=styles['Heading2'],
        fontSize=14, spaceAfter=12, alignment=0,
        textColor=colors.black
    )
    info_style = ParagraphStyle(
        'InfoStyle', parent=styles['Normal'],
        fontSize=10, spaceAfter=6, alignment=0
    )
    table_cell_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontSize=8, alignment=TA_LEFT, wordWrap='CJK'
    )
    table_header_style = ParagraphStyle(
        'TableHeader', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold'
    )

    # Title
    elements.append(Paragraph("Student Evaluation Report", title_style))
    elements.append(Spacer(1, 12))

    # Student Info
    report_info = f"""
    <b>Student ID:</b> {student_info.get('_id', 'N/A')}<br/>
    <b>Name:</b> {student_info.get('Name', 'N/A')}<br/>
    <b>Course:</b> {student_info.get('Course', 'N/A')}<br/>
    <b>Year Level:</b> {student_info.get('YearLevel', 'N/A')}<br/>
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))

    # Grades by Semester
    if transcript_data:
        elements.append(Paragraph("📊 Grades by Semester", header_style))
        elements.append(Spacer(1, 12))

        for semester, df in transcript_data.items():
            elements.append(Paragraph(f"📚 {semester}", styles['Heading3']))
            elements.append(Spacer(1, 6))

            if not df.empty:
                table_data = [[Paragraph('Subject Code', table_header_style),
                               Paragraph('Subject Name', table_header_style),
                               Paragraph('Units', table_header_style),
                               Paragraph('Teacher', table_header_style),
                               Paragraph('Grade', table_header_style),
                               Paragraph('Status', table_header_style)]]
                for _, row in df.iterrows():
                    table_data.append([
                        Paragraph(str(row.get('SUBJECTCODE', '')), table_cell_style),
                        Paragraph(str(row.get('SUBJECTNAME', '')), table_cell_style),
                        Paragraph(str(row.get('UNITS', '')), table_cell_style),
                        Paragraph(str(row.get('TEACHER', '')), table_cell_style),
                        Paragraph(str(row.get('GRADE', '')), table_cell_style),
                        Paragraph(str(row.get('STATUS', '')), table_cell_style)
                    ])
                table = Table(table_data, colWidths=[1*inch, 2*inch, 0.5*inch, 1.5*inch, 0.8*inch, 1*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))

    # Future Subjects Section
    if all_future_display_data:
        elements.append(PageBreak())
        elements.append(Paragraph("📝 Future Subjects Evaluation", header_style))
        elements.append(Spacer(1, 12))

        future_df = pd.DataFrame(all_future_display_data)
        # Ensure proper sorting
        if 'yearLevel' in future_df.columns:
            future_df['yearLevel'] = pd.to_numeric(future_df['yearLevel'], errors='coerce')
        if 'semester' in future_df.columns:
            future_df['semester'] = pd.to_numeric(future_df['semester'], errors='coerce')

        future_df = future_df.sort_values(by=['yearLevel', 'semester'], na_position='last')

        group_cols = []
        if 'yearLevel' in future_df.columns:
            group_cols.append('yearLevel')
        if 'semester' in future_df.columns:
            group_cols.append('semester')

        grouped = future_df.groupby(group_cols) if group_cols else [('All', future_df)]
        last_year = None
        semester_count = 0

        for grp_key, grp in grouped:
            # Add a page break when year changes (for clarity)
            current_year = grp_key[0] if isinstance(grp_key, tuple) else grp_key
            if last_year is not None and current_year != last_year:
                elements.append(PageBreak())
            last_year = current_year

            if isinstance(grp_key, tuple):
                title = f"Year {grp_key[0]} - Semester {grp_key[1]}"
            else:
                title = f"Year {grp_key}"

            elements.append(Paragraph(f"📘 {title}", styles['Heading3']))
            elements.append(Spacer(1, 6))

            table_data = [[Paragraph('Subject Code', table_header_style),
                           Paragraph('Subject Name', table_header_style),
                           Paragraph('Units', table_header_style),
                           Paragraph('Status', table_header_style),
                           Paragraph('Enroll?', table_header_style),
                           Paragraph('Prerequisite', table_header_style)]]

            for _, row in grp.iterrows():
                table_data.append([
                    Paragraph(str(row.get('Subject Code', '')), table_cell_style),
                    Paragraph(str(row.get('Subject Name', '')), table_cell_style),
                    Paragraph(str(row.get('Units', '')), table_cell_style),
                    Paragraph(str(row.get('Status', '')), table_cell_style),
                    Paragraph(str(row.get('Enroll?', '')), table_cell_style),
                    Paragraph(str(row.get('Prerequisite', '')), table_cell_style)
                ])

            table = Table(table_data, colWidths=[1*inch, 2*inch, 0.5*inch, 1.5*inch, 1*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ]))
            elements.append(table)
            semester_count += 1

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_pdf_download_button_tab2(student_info, transcript_data, all_future_display_data):
    """Add a download button for PDF export of student evaluation"""
    # Check if student_info is empty or None
    student_info_empty = student_info is None or (hasattr(student_info, 'empty') and student_info.empty) or (isinstance(student_info, dict) and not student_info)

    # Check if data is available
    transcript_empty = not transcript_data or (isinstance(transcript_data, dict) and not transcript_data)
    future_empty = not all_future_display_data or (isinstance(all_future_display_data, list) and not all_future_display_data)

    if student_info_empty or (transcript_empty and future_empty):
        st.warning("No data available to export to PDF.")
        return

    try:
        pdf_data = create_student_evaluation_pdf(student_info, transcript_data, all_future_display_data)

        # Generate filename
        student_id = student_info.get('_id', 'Unknown')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Student_Evaluation_{student_id}_{timestamp}.pdf"

        st.download_button(
            label="📄 Download Student Evaluation PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of the student evaluation",
            key="download_pdf_tab2"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab2_info(data, students_df, semesters_df, teachers_df):
        grades_df = data['grades']
        subjects_df = data['subjects']

        styles = getSampleStyleSheet()
        additional_elements = []

        st.subheader("📋 Evaluation Form")
        st.markdown("Enter a student name to evaluate their enrollment eligibility for future subjects.")
        additional_elements.append(Paragraph("📋 Evaluation Form", styles["Heading1"]))
        additional_elements.append(Spacer(1, 10))
        
        # Student dropdown (same as Tab 2)
        student_options = [] if students_df.empty else students_df[["_id", "Name", "Course", "YearLevel"]].copy()
        display_to_id = {}
        if not students_df.empty:
            student_options["display"] = student_options.apply(lambda r: f"{r['Name']} ({r['_id']}) - {r['Course']} - Year {r['YearLevel']}", axis=1)
            display_to_id = dict(zip(student_options["display"], student_options["_id"]))
            sel_student_display = st.selectbox("Student", ["-"] + student_options["display"].tolist(), key="eval_student_sel")
        else:
            sel_student_display = st.selectbox("Student", ["-"], key="eval_student_sel")
        
        # Year level filter
        # (Removed) Year level filter per request

        if sel_student_display and sel_student_display != "-":
            sel_student_id = display_to_id.get(sel_student_display)
            
            if not sel_student_id:
                st.warning("Could not identify selected student.")
                student_info = None
            else:
                student_row = students_df[students_df["_id"] == sel_student_id]
                if student_row.empty:
                    st.warning("Selected student record not found.")
                    student_info = None
                else:
                    student_info = student_row.iloc[0]
                    student_id = student_info.get('_id')
                    st.success(f"Selected student: {student_info.get('Name', 'Unknown')}")
                    
                    # Display student info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Student ID", student_info.get('_id', 'N/A'))
                    with col2:
                        st.metric("Name", student_info.get('Name', 'N/A'))
                    with col3:
                        st.metric("Year Level", student_info.get('YearLevel', 'N/A'))

                    additional_elements.append(Paragraph("Student Information", styles["Heading2"]))
                    additional_elements.append(Paragraph(f"Student ID: {student_info.get('_id', 'N/A')}", styles["Normal"]))
                    additional_elements.append(Paragraph(f"Name: {student_info.get('Name', 'N/A')}", styles["Normal"]))
                    additional_elements.append(Paragraph(f"Year Level: {student_info.get('YearLevel', 'N/A')}", styles["Normal"]))
                    additional_elements.append(Spacer(1, 10))

                    student_year = int(str(student_info.get('YearLevel', 1)).strip()) if str(student_info.get('YearLevel', 1)).strip().isdigit() else 1

                # Get student's grades and filter for passing grades
                student_grades = grades_df[grades_df["StudentID"] == student_id].copy()

                # Expand grades to individual subject records
                def expand_student_grades(grade_row):
                    results = []
                    grades_list = grade_row.get("Grades", [])
                    subjects_list = grade_row.get("SubjectCodes", [])
                    grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
                    subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]

                    for i, grade in enumerate(grades_list):
                        if i < len(subjects_list):
                            subject_code = subjects_list[i]
                            if isinstance(grade, (int, float)) and not pd.isna(grade) and grade >= 75:
                                results.append({
                                    "subject_code": subject_code,
                                    "grade": grade,
                                    "semester_id": grade_row.get("SemesterID")
                                })
                    return results

                completed_subjects = []
                for _, grade_row in student_grades.iterrows():
                    completed_subjects.extend(expand_student_grades(grade_row))

                # Get subject names from subjects_df
                subjects_dict = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
                for subj in completed_subjects:
                    subj["subject_name"] = subjects_dict.get(subj["subject_code"], subj["subject_code"])

                # --- Enhanced Grade Display Section (from dash_student.py tab1) ---
                st.subheader("📊 Student Grades by Semester")

                # Load curriculum subjects for merging
                curriculums = load_curriculums_df()
                if isinstance(curriculums, pd.DataFrame):
                    curriculums = curriculums.to_dict(orient="records")

                # Flatten all subjects from curriculum into one DataFrame
                all_subjects = []
                for curriculum in curriculums:
                    for subj in curriculum.get("subjects", []):
                        all_subjects.append(subj)
                curriculum_subjects_df = (
                    pd.DataFrame(all_subjects)
                    if all_subjects
                    else pd.DataFrame(columns=["subjectCode", "subjectName", "units"])
                )

                # Merge semester info with student grades
                student_grades_with_semester = student_grades.merge(
                    semesters_df,
                    left_on="SemesterID",
                    right_on="_id",
                    how="left"
                ).drop(columns=["_id"], errors="ignore")

                transcript_data = {}
                semester_avgs = []

                # Group by SchoolYear + Semester
                if "SchoolYear" in student_grades_with_semester.columns and "Semester" in student_grades_with_semester.columns:
                    grouped = student_grades_with_semester.groupby(["SchoolYear", "Semester"])

                    for (sy, sem), sem_df in grouped:
                        st.subheader(f"📚 {sy} - {sem}")

                        # Handle expanded grades
                        if sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                            expanded = pd.DataFrame({
                                "SubjectCode": sem_df["SubjectCodes"].explode().values,
                                "Teacher": sem_df["Teachers"].explode().values,
                                "Grade": sem_df["Grades"].explode().values
                            })
                        else:
                            expanded = sem_df[["SubjectCodes", "Teachers", "Grades"]].rename(
                                columns={"SubjectCodes": "SubjectCode", "Teachers": "Teacher", "Grades": "Grade"}
                            )

                        # Merge with curriculum subjects to get subjectName + units
                        expanded = expanded.merge(
                            curriculum_subjects_df[["subjectCode", "subjectName", "units"]],
                            left_on="SubjectCode",
                            right_on="subjectCode",
                            how="left"
                        ).drop(columns=["subjectCode"])

                        # Reorder columns
                        expanded = expanded[["SubjectCode", "subjectName", "units", "Teacher", "Grade"]]

                        # Add STATUS column
                        expanded["Status"] = expanded["Grade"].apply(
                            lambda x: "PASSED" if pd.to_numeric(x, errors="coerce") >= 75 else "FAILED"
                        )

                        # Rename columns to ALL CAPS
                        expanded.rename(columns=str.upper, inplace=True)

                        # Style: make FAILED red
                        def highlight_status(val):
                            if val == "FAILED":
                                return "color: red; font-weight: bold;"
                            return "color: blue;"

                        styled = expanded.style.applymap(highlight_status, subset=["STATUS"])

                        # Show styled table
                        st.dataframe(styled, use_container_width=True)

                        # Semester average
                        valid_grades = pd.to_numeric(expanded["GRADE"], errors="coerce").dropna()
                        if not valid_grades.empty:
                            avg = valid_grades.mean()
                            st.write(f"**Semester Average: {avg:.2f}**")
                            semester_avgs.append((f"{sy} - {sem}", avg))
                        else:
                            st.write("**Semester Average: N/A**")

                        # Semester total units
                        total_units = pd.to_numeric(expanded["UNITS"], errors="coerce").fillna(0).sum()
                        st.write(f"**Total Units: {int(total_units)}**")

                        transcript_data[f"{sy} - {sem}"] = expanded
                        st.markdown("---")
                   
                # Current & Future Subjects Evaluation Section
                if student_year == 1:
                    st.subheader("📝 2nd Year & Future Subjects - Prerequisite Check")
                    st.markdown("For 1st year students: Check if prerequisites are met for 2nd year and future subjects.")
                    additional_elements.append(Paragraph("📝 2nd Year & Future Subjects - Prerequisite Check", styles["Heading2"]))
                    additional_elements.append(Spacer(1, 10))
                else:
                    st.subheader("📝 Future Subjects - Enrollment Evaluation")
                    st.markdown("Evaluate enrollment eligibility for future subjects based on prerequisites and academic progress.")
                    additional_elements.append(Paragraph("📝 Future Subjects - Enrollment Evaluation", styles["Heading2"]))
                    additional_elements.append(Spacer(1, 10))

                # Get curriculum data for future subjects evaluation
                curr_df = load_curriculums_df()

                if not curr_df.empty:
                    # Filter curriculum by student's course
                    student_course = student_info.get("Course", "")
                    filtered_curr = curr_df.copy()
                    if "courseCode" in curr_df.columns:
                        filtered_curr = curr_df[curr_df["courseCode"].astype(str) == str(student_course)]
                        if filtered_curr.empty and "courseName" in curr_df.columns:
                            filtered_curr = curr_df[curr_df["courseName"].astype(str).str.contains(str(student_course), case=False, na=False)]
                    
                    if filtered_curr.empty:
                        st.warning("No curriculum found for student's course. Showing all curriculums.")
                        filtered_curr = curr_df
                    
                    # Process each matching curriculum for future subjects
                    all_future_display_data = []  # for download
                    for _, crow in filtered_curr.iterrows():
                        st.markdown(f"### {crow.get('courseCode', '')} - {crow.get('courseName', '')} ({crow.get('curriculumYear', '')})")
                        subjects = crow.get("subjects", []) or []
                        
                        if not subjects:
                            st.info("No subjects found in this curriculum.")
                            continue
                        
                        subj_df = pd.DataFrame(subjects)
                        for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                            if c not in subj_df.columns:
                                subj_df[c] = None
                        
                        # Filter to only future subjects (year_level > student's current year)
                        subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")
                        future_subj_df = subj_df[subj_df["_yl_num"] > student_year].copy()
                        if future_subj_df.empty:
                            st.info("No future subjects found in this curriculum.")
                            continue
                        
                        # Group by year level and semester
                        group_cols = ["yearLevel", "semester"] if "semester" in future_subj_df.columns else ["yearLevel"]
                        try:
                            grouped = future_subj_df.groupby(group_cols)
                        except Exception:
                            future_subj_df["yearLevel"] = future_subj_df["yearLevel"].astype(str)
                            if "semester" in future_subj_df.columns:
                                future_subj_df["semester"] = future_subj_df["semester"].astype(str)
                            grouped = future_subj_df.groupby(group_cols)
                        
                        # Process each year/semester group
                        for grp_key, grp in grouped:
                            if isinstance(grp_key, tuple):
                                title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                                year_level = grp_key[0]
                            else:
                                title = f"Year {grp_key}"
                                year_level = grp_key
                            
                            year_indicator = "📘 Future Year"
                            st.subheader(f"{year_indicator} - {title}")
                            additional_elements.append(Paragraph(f"{year_indicator} - {title}", styles["Heading3"]))
                            additional_elements.append(Spacer(1, 5))
                            
                            display_data = []
                            completed_codes = {subj["subject_code"] for subj in completed_subjects}
                            
                            def parse_prereq(prereq):
                                if not prereq or prereq in ["None", "N/A", ""]:
                                    return []
                                if isinstance(prereq, list):
                                    return [str(x).strip() for x in prereq if str(x).strip()]
                                return [str(prereq).strip()]
                            
                            def normalize_subject_code(code):
                                if not code:
                                    return ""
                                return str(code).replace(" ", "").upper()
                            
                            completed_codes_with_grades = {normalize_subject_code(subj["subject_code"]): subj["grade"] for subj in completed_subjects}
                            prereq_eligible_codes = set(completed_codes_with_grades.keys())
                            
                            for _, subject in grp.iterrows():
                                subj_code = str(subject["subjectCode"])
                                if subj_code in completed_codes:
                                    status = "✅ Already Passed"
                                    grade_display = ""
                                    enroll = "No - Already Passed"
                                    for comp_subj in completed_subjects:
                                        if comp_subj["subject_code"] == subj_code:
                                            grade_display = f"({comp_subj['grade']})"
                                            break
                                else:
                                    prerequisites = parse_prereq(subject.get("prerequisite", []))
                                    missing_prereqs = []
                                    met_prereqs = []
                                    for prereq in prerequisites:
                                        normalized_prereq = normalize_subject_code(prereq)
                                        if normalized_prereq in prereq_eligible_codes:
                                            prereq_grade = completed_codes_with_grades.get(normalized_prereq, "N/A")
                                            met_prereqs.append(f"{prereq}({prereq_grade})")
                                        else:
                                            missing_prereqs.append(prereq)
                                    if not missing_prereqs:
                                        status = "📝 Ready to Enroll"
                                        grade_display = f"Prereqs: {', '.join(met_prereqs)}"
                                        enroll = "Yes - Prerequisites Met"
                                    else:
                                        status = "⚠️ Prerequisites Not Met"
                                        grade_display = f"Missing: {', '.join(missing_prereqs)}"
                                        enroll = "No - Missing Prerequisites"

                                display_data.append({
                                    "Subject Code": subject["subjectCode"],
                                    "Subject Name": subject["subjectName"],
                                    "Units": subject["units"],
                                    "Lec": subject["lec"],
                                    "Lab": subject["lab"],
                                    "Status": status,
                                    "Grade": grade_display,
                                    "Enroll?": enroll,
                                    "Prerequisite": subject["prerequisite"],
                                    "yearLevel": year_level,
                                    "semester": subject.get("semester")
                                })
                            
                            all_future_display_data.extend(display_data)
                            
                            display_df = pd.DataFrame(display_data)
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            total_units = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                            total_lec = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                            total_lab = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                            ready_to_enroll = len([d for d in display_data if d["Enroll?"].startswith("Yes")])
                            already_passed = len([d for d in display_data if "Already Passed" in d["Status"]])
                            missing_prereqs = len([d for d in display_data if "Prerequisites Not Met" in d["Status"]])
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Units", f"{int(total_units)}")
                            with col2:
                                st.metric("Ready to Enroll", ready_to_enroll)
                            with col3:
                                st.metric("Already Passed", already_passed)
                            with col4:
                                st.metric("Missing Prereqs", missing_prereqs)

                            additional_elements.append(Paragraph(f"Total Units: {int(total_units)}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Ready to Enroll: {ready_to_enroll}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Already Passed: {already_passed}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Missing Prereqs: {missing_prereqs}", styles["Normal"]))
                            additional_elements.append(Spacer(1, 10))

                            st.markdown("---")

                    # PDF Download Section
                    st.subheader("📄 Export Report")
                    add_pdf_download_button_tab2(student_info, transcript_data, all_future_display_data)

                    # Download button for all displayed subjects (past, current, future)

                    # Collect past/current subjects grouped by year/semester
                    semester_tables = {}
                    if not filtered_curr.empty:
                        for _, crow in filtered_curr.iterrows():
                            subjects = crow.get("subjects", []) or []
                            subj_df = pd.DataFrame(subjects)
                            for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                                if c not in subj_df.columns:
                                    subj_df[c] = None
                            subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")
                            if student_year == 1:
                                relevant_subj_df = subj_df[subj_df["_yl_num"] == 1].copy()
                            else:
                                relevant_subj_df = subj_df[subj_df["_yl_num"] <= student_year].copy()
                            if relevant_subj_df.empty:
                                continue

                            # Group by year level and semester
                            group_cols = ["yearLevel", "semester"] if "semester" in relevant_subj_df.columns else ["yearLevel"]
                            try:
                                grouped = relevant_subj_df.groupby(group_cols)
                            except Exception:
                                relevant_subj_df["yearLevel"] = relevant_subj_df["yearLevel"].astype(str)
                                if "semester" in relevant_subj_df.columns:
                                    relevant_subj_df["semester"] = relevant_subj_df["semester"].astype(str)
                                grouped = relevant_subj_df.groupby(group_cols)

                            # Process each year/semester group
                            for grp_key, grp in grouped:
                                if isinstance(grp_key, tuple):
                                    table_key = f"Year {grp_key[0]} - Sem {grp_key[1]}" if len(grp_key) > 1 else f"Year {grp_key[0]}"
                                else:
                                    table_key = f"Year {grp_key}"

                                if table_key not in semester_tables:
                                    semester_tables[table_key] = []

                                for _, subject in grp.iterrows():
                                    subj_code = str(subject["subjectCode"])
                                    grade_display = ""
                                    status = "❌ Not Completed"
                                    for comp_subj in completed_subjects:
                                        if comp_subj["subject_code"] == subj_code:
                                            grade_display = f"{comp_subj['grade']}"
                                            status = "✅ Passed" if float(comp_subj['grade']) >= 75 else "❌ Failed"
                                            break
                                    semester_tables[table_key].append({
                                        "Subject Code": subject["subjectCode"],
                                        "Subject Name": subject["subjectName"],
                                        "Units": subject["units"],
                                        "Lec": subject["lec"],
                                        "Lab": subject["lab"],
                                        "Status": status,
                                        "Grade": grade_display,
                                        "Prerequisite": subject["prerequisite"]
                                    })

                    # Future subjects grouped by year/semester
                    future_semester_tables = {}
                    if all_future_display_data:
                        # Group future subjects by year/semester based on curriculum data
                        if not filtered_curr.empty:
                            for _, crow in filtered_curr.iterrows():
                                subjects = crow.get("subjects", []) or []
                                subj_df = pd.DataFrame(subjects)
                                for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                                    if c not in subj_df.columns:
                                        subj_df[c] = None
                                subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")
                                future_subj_df = subj_df[subj_df["_yl_num"] > student_year].copy()
                                if future_subj_df.empty:
                                    continue

                                # Group by year level and semester
                                group_cols = ["yearLevel", "semester"] if "semester" in future_subj_df.columns else ["yearLevel"]
                                try:
                                    grouped = future_subj_df.groupby(group_cols)
                                except Exception:
                                    future_subj_df["yearLevel"] = future_subj_df["yearLevel"].astype(str)
                                    if "semester" in future_subj_df.columns:
                                        future_subj_df["semester"] = future_subj_df["semester"].astype(str)
                                    grouped = future_subj_df.groupby(group_cols)

                                # Process each year/semester group for future subjects
                                for grp_key, grp in grouped:
                                    if isinstance(grp_key, tuple):
                                        table_key = f"Future Year {grp_key[0]} - Sem {grp_key[1]}" if len(grp_key) > 1 else f"Future Year {grp_key[0]}"
                                    else:
                                        table_key = f"Future Year {grp_key}"

                                    if table_key not in future_semester_tables:
                                        future_semester_tables[table_key] = []

                                    for _, subject in grp.iterrows():
                                        subj_code = str(subject["subjectCode"])
                                        # Find matching data from all_future_display_data
                                        for future_item in all_future_display_data:
                                            if future_item["Subject Code"] == subj_code:
                                                future_semester_tables[table_key].append(future_item)
                                                break



                else:
                    st.warning("No curriculum data available.")

        else:
            st.info("Please enter a student name to begin evaluation.")
