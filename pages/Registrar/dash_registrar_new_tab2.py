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



def create_curriculum_pdf(curr_df, selected_course, selected_year, group_by_sem, student_info=None, completed_subjects=None):
    """Generate PDF report for curriculum data with optional student evaluation"""

    buffer = BytesIO()
    # Adjust margins to better fit content on letter size
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=50, leftMargin=50,
                          topMargin=50, bottomMargin=50)

    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=10,
        alignment=TA_LEFT,
        textColor=colors.black
    )

    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=4,
        alignment=TA_LEFT
    )

    # Title
    if student_info is not None:
        elements.append(Paragraph("📋 Student Curriculum Evaluation Report", title_style))
    else:
        elements.append(Paragraph("📚 Curriculum Report", title_style))
    elements.append(Spacer(1, 10))

    # Student Information (if provided)
    if student_info is not None:
        student_info_text = f"""
        <b>Student ID:</b> {student_info.get('_id', 'N/A')}<br/>
        <b>Name:</b> {student_info.get('Name', 'N/A')}<br/>
        <b>Course:</b> {student_info.get('Course', 'N/A')}<br/>
        <b>Year Level:</b> {student_info.get('YearLevel', 'N/A')}
        """
        elements.append(Paragraph(student_info_text, info_style))
        elements.append(Spacer(1, 10))

    # Report Information
    report_info = f"""
    <b>Generated on:</b> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Program Filter:</b> {selected_course if selected_course != "All" else "All Programs"}<br/>
    <b>Curriculum Year Filter:</b> {selected_year if selected_year != "All" else "All Years"}<br/>
    <b>Grouped by Semester:</b> {"Yes" if group_by_sem else "No"}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 15))

    # Apply filters
    filtered = curr_df.copy()
    if selected_course != "All":
        try:
            cc, cn = selected_course.split(" - ", 1)
            filtered = filtered[(filtered["courseCode"].astype(str) == cc) & (filtered["courseName"].astype(str) == cn)]
        except (ValueError, AttributeError):
            # If selected_course is not in expected format, try to match directly
            filtered = filtered[(filtered["courseCode"].astype(str) == str(selected_course)) |
                              (filtered["courseName"].astype(str).str.contains(str(selected_course), case=False, na=False))]
    if selected_year != "All":
        filtered = filtered[filtered["curriculumYear"].astype(str) == selected_year]

    if filtered.empty:
        elements.append(Paragraph("No curriculum data found for the selected filters.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # Get student year level for future subjects evaluation
    student_year = int(str(student_info.get('YearLevel', 1)).strip()) if student_info is not None and str(student_info.get('YearLevel', 1)).strip().isdigit() else 1

    # Iterate through matching curriculums
    for _, row in filtered.iterrows():
        elements.append(Paragraph(f"{row.get('courseCode', '')} - {row.get('courseName', '')} ({row.get('curriculumYear', '')})", header_style))
        elements.append(Spacer(1, 10))

        subjects = row.get("subjects", []) or []
        if not subjects:
            elements.append(Paragraph("No subjects found in this curriculum.", styles['Normal']))
            elements.append(Spacer(1, 10))
            continue

        subj_df = pd.DataFrame(subjects)
        # Normalize expected columns
        expected_cols = [
            "subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"
        ]
        for c in expected_cols:
            if c not in subj_df.columns:
                subj_df[c] = None

        # Add year level numeric column for filtering
        subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")

        # Separate past/current and future subjects
        if student_info is not None and completed_subjects is not None:
            past_current_subj_df = subj_df[subj_df["_yl_num"] <= student_year].copy()
            future_subj_df = subj_df[subj_df["_yl_num"] > student_year].copy()
        else:
            past_current_subj_df = subj_df.copy()
            future_subj_df = pd.DataFrame()

        # Process Past/Current Subjects
        if not past_current_subj_df.empty:
            elements.append(Paragraph("📚 Past & Current Year Subjects", styles['Heading3']))
            elements.append(Spacer(1, 6))

            # Display grouped by YearLevel (and Semester optionally)
            if group_by_sem and "semester" in past_current_subj_df.columns:
                group_cols = ["yearLevel", "semester"]
            else:
                group_cols = ["yearLevel"]

            try:
                grouped = past_current_subj_df.groupby(group_cols)
            except Exception:
                # Fallback if grouping fails due to types
                past_current_subj_df["yearLevel"] = past_current_subj_df["yearLevel"].astype(str)
                if "semester" in past_current_subj_df.columns:
                    past_current_subj_df["semester"] = past_current_subj_df["semester"].astype(str)
                grouped = past_current_subj_df.groupby(group_cols)

            total_units_overall = 0
            for grp_key, grp in grouped:
                if isinstance(grp_key, tuple):
                    title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                else:
                    title = f"Year {grp_key}"
                elements.append(Paragraph(title, styles['Heading4']))
                elements.append(Spacer(1, 4))

                # Enhanced display with student evaluation data
                if student_info is not None and completed_subjects is not None:
                    display_data = []
                    completed_codes = {subj["subject_code"] for subj in completed_subjects}

                    for _, subject in grp.iterrows():
                        subj_code = str(subject["subjectCode"])

                        # Check if this subject is completed
                        grade_display = ""
                        status = ""
                        is_completed = False

                        for comp_subj in completed_subjects:
                            if comp_subj["subject_code"] == subj_code:
                                grade_display = f"{comp_subj['grade']}"
                                is_completed = True
                                break

                        # Determine status
                        if is_completed:
                            try:
                                grade_val = float(grade_display)
                                if grade_val >= 75:
                                    status = "✅ Passed"
                                else:
                                    status = "❌ Failed"
                            except (ValueError, TypeError):
                                status = "✅ Passed"
                        else:
                            status = "❌ Not Completed"
                            grade_display = "N/A"

                        display_data.append({
                            "Subject Code": subject["subjectCode"],
                            "Subject Name": subject["subjectName"],
                            "Lec": subject["lec"],
                            "Lab": subject["lab"],
                            "Units": subject["units"],
                            "Grade": grade_display,
                            "Status": status,
                            "Prerequisite": subject["prerequisite"]
                        })

                    show_df = pd.DataFrame(display_data)
                else:
                    display_cols = [
                        "subjectCode", "subjectName", "lec", "lab", "units", "prerequisite"
                    ]
                    show_df = grp[display_cols].rename(columns={
                        "subjectCode": "Subject Code",
                        "subjectName": "Subject Name",
                        "lec": "Lec",
                        "lab": "Lab",
                        "units": "Units",
                        "prerequisite": "Prerequisite"
                    })

                # Create table
                table_data = [show_df.columns.tolist()] + show_df.values.tolist()
                t = Table(table_data, repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 7),  # Smaller font for better fit
                ]))
                elements.append(t)
                elements.append(Spacer(1, 8))

                # Enhanced totals with student evaluation
                units_sum = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                lec_sum = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                lab_sum = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                total_units_overall += units_sum

                if student_info is not None and completed_subjects is not None:
                    # Calculate semester statistics
                    semester_grades = []
                    completed_count = 0
                    for _, subject in grp.iterrows():
                        subj_code = str(subject["subjectCode"])
                        for comp_subj in completed_subjects:
                            if comp_subj["subject_code"] == subj_code:
                                try:
                                    semester_grades.append(float(comp_subj['grade']))
                                    completed_count += 1
                                except (ValueError, TypeError):
                                    pass
                                break

                    avg_grade = sum(semester_grades) / len(semester_grades) if semester_grades else 0
                    excellent_count = len([g for g in semester_grades if g >= 90])

                    totals_text = f"""Total Units: {int(units_sum)}, Total Lec Hours: {int(lec_sum)}, Total Lab Hours: {int(lab_sum)}<br/>
                    Completed: {completed_count}/{len(grp)}, Average Grade: {avg_grade:.1f}, Excellent (≥90): {excellent_count}"""
                else:
                    totals_text = f"Total Units: {int(units_sum)}, Total Lec Hours: {int(lec_sum)}, Total Lab Hours: {int(lab_sum)}"

                elements.append(Paragraph(totals_text, info_style))
                elements.append(Spacer(1, 8))

            overall_text = f"Overall Units in Past/Current Subjects: {int(total_units_overall)}"
            elements.append(Paragraph(overall_text, styles['Heading4']))
            elements.append(Spacer(1, 15))

        # Process Future Subjects with Enrollment Evaluation
        if not future_subj_df.empty and student_info is not None and completed_subjects is not None:
            elements.append(Paragraph("📝 Future Subjects - Enrollment Evaluation", styles['Heading3']))
            elements.append(Spacer(1, 6))

            # Display grouped by YearLevel (and Semester optionally)
            if group_by_sem and "semester" in future_subj_df.columns:
                group_cols = ["yearLevel", "semester"]
            else:
                group_cols = ["yearLevel"]

            try:
                grouped = future_subj_df.groupby(group_cols)
            except Exception:
                # Fallback if grouping fails due to types
                future_subj_df["yearLevel"] = future_subj_df["yearLevel"].astype(str)
                if "semester" in future_subj_df.columns:
                    future_subj_df["semester"] = future_subj_df["semester"].astype(str)
                grouped = future_subj_df.groupby(group_cols)

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

            for grp_key, grp in grouped:
                if isinstance(grp_key, tuple):
                    title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                else:
                    title = f"Year {grp_key}"
                elements.append(Paragraph(f"Future {title}", styles['Heading4']))
                elements.append(Spacer(1, 4))

                display_data = []

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
                            grade_display = f"Prereqs: {', '.join(met_prereqs)}" if met_prereqs else "No Prerequisites"
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
                        "Grade/Prereq": grade_display,
                        "Enroll?": enroll,
                        "Prerequisite": subject["prerequisite"]
                    })

                show_df = pd.DataFrame(display_data)

                # Create table
                table_data = [show_df.columns.tolist()] + show_df.values.tolist()
                t = Table(table_data, repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 6),  # Even smaller font for future subjects table
                ]))
                elements.append(t)
                elements.append(Spacer(1, 8))

                # Future subjects totals
                units_sum = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                lec_sum = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                lab_sum = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                ready_to_enroll = len([d for d in display_data if d["Enroll?"].startswith("Yes")])
                already_passed = len([d for d in display_data if "Already Passed" in d["Status"]])
                missing_prereqs = len([d for d in display_data if "Prerequisites Not Met" in d["Status"]])

                totals_text = f"""Total Units: {int(units_sum)}, Total Lec Hours: {int(lec_sum)}, Total Lab Hours: {int(lab_sum)}<br/>
                Ready to Enroll: {ready_to_enroll}, Already Passed: {already_passed}, Missing Prereqs: {missing_prereqs}"""

                elements.append(Paragraph(totals_text, info_style))
                elements.append(Spacer(1, 8))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_curriculum_pdf_download_button(curr_df, selected_course, selected_year, group_by_sem, student_info=None, completed_subjects=None):
    """Add a download button for curriculum PDF export with optional student evaluation"""

    if curr_df is None or curr_df.empty:
        st.warning("No curriculum data available to export to PDF.")
        return

    try:
        pdf_data = create_curriculum_pdf(curr_df, selected_course, selected_year, group_by_sem, student_info, completed_subjects)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if student_info is not None:
            student_name = student_info.get('Name', 'Unknown').replace(' ', '_')
            filename = f"Student_Evaluation_Report_{student_name}_{timestamp}.pdf"
        else:
            filename = f"Curriculum_Report_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of the displayed curriculum",
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
                
                # Display subjects based on student's year level
                if student_year == 1:
                    st.subheader("📚 1st Year Subjects - Pass/Fail Status")
                    st.markdown("For 1st year students: Shows 1st year 1st sem and 1st year 2nd sem subjects with pass/fail status.")
                    additional_elements.append(Paragraph("📚 1st Year Subjects - Pass/Fail Status", styles["Heading2"]))
                    additional_elements.append(Spacer(1, 10))
                else:
                    st.subheader("📚 Past & Current Year Subjects - Completed & Not Completed")
                    st.markdown("Shows subjects from semesters the student has already passed through.")
                    additional_elements.append(Paragraph("📚 Past & Current Year Subjects - Completed & Not Completed", styles["Heading2"]))
                    additional_elements.append(Spacer(1, 10))
                
                # Get curriculum data to organize subjects from past/current semesters
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
                    
                    # Process each matching curriculum
                    for _, crow in filtered_curr.iterrows():
                        st.markdown(f"### {crow.get('courseCode', '')} - {crow.get('courseName', '')} ({crow.get('curriculumYear', '')})")
                        subjects = crow.get("subjects", []) or []
                        
                        if not subjects:
                            st.info("No subjects found in this curriculum.")
                            continue
                        
                        subj_df = pd.DataFrame(subjects)
                        # Ensure columns
                        for c in ["subjectCode", "subjectName", "yearLevel", "semester", "units", "lec", "lab", "prerequisite"]:
                            if c not in subj_df.columns:
                                subj_df[c] = None
                        
                        # Filter subjects based on student's year level
                        subj_df["_yl_num"] = pd.to_numeric(subj_df["yearLevel"], errors="coerce")
                        
                        if student_year == 1:
                            # For 1st year students: show only 1st year subjects (both semesters)
                            past_current_subj_df = subj_df[subj_df["_yl_num"] == 1].copy()
                            if past_current_subj_df.empty:
                                st.info("No 1st year subjects found in this curriculum.")
                                continue
                        else:
                            # For other years: show subjects from past and current year
                            past_current_subj_df = subj_df[subj_df["_yl_num"] <= student_year].copy()
                            if past_current_subj_df.empty:
                                st.info("No past or current year subjects found in this curriculum.")
                                continue
                        
                        # Group by year level and semester
                        group_cols = ["yearLevel", "semester"] if "semester" in past_current_subj_df.columns else ["yearLevel"]
                        try:
                            grouped = past_current_subj_df.groupby(group_cols)
                        except Exception:
                            past_current_subj_df["yearLevel"] = past_current_subj_df["yearLevel"].astype(str)
                            if "semester" in past_current_subj_df.columns:
                                past_current_subj_df["semester"] = past_current_subj_df["semester"].astype(str)
                            grouped = past_current_subj_df.groupby(group_cols)
                            
                        # Process each year/semester group
                        for grp_key, grp in grouped:
                            if isinstance(grp_key, tuple):
                                title = " - ".join([f"Year {grp_key[0]}"] + ([f"Sem {grp_key[1]}"] if len(grp_key) > 1 else []))
                            else:
                                title = f"Year {grp_key}"
                            st.subheader(f"📘 {title}")
                            additional_elements.append(Paragraph(f"📘 {title}", styles["Heading3"]))
                            additional_elements.append(Spacer(1, 5))

                            # Create display data for subjects
                            display_data = []
                            
                            for _, subject in grp.iterrows():
                                subj_code = str(subject["subjectCode"])
                                
                                # Check if this subject is completed
                                grade_display = ""
                                is_completed = False
                                
                                for comp_subj in completed_subjects:
                                    if comp_subj["subject_code"] == subj_code:
                                        grade_display = f"{comp_subj['grade']}"
                                        is_completed = True
                                        break
                                
                                # Determine status based on student year level
                                if student_year == 1:
                                    # For 1st year students: all subjects are considered "done" but check pass/fail
                                    if is_completed:
                                        try:
                                            grade_val = float(grade_display)
                                            if grade_val >= 90:
                                                status = "🏆 Excellent"
                                            elif grade_val >= 85:
                                                status = "✅ Very Good"
                                            elif grade_val >= 80:
                                                status = "✅ Good"
                                            elif grade_val >= 75:
                                                status = "✅ Passed"
                                            elif 0 <= grade_val < 75:
                                                status = "❌ Failed"
                                            else:
                                                status = "⏳ Not Yet Taken"
                                        except (ValueError, TypeError):
                                            status = "⏳ Not Yet Taken"
                                    else:
                                        # For 1st year students, show as "Not Yet Taken" instead of "Not Completed"
                                        status = "⏳ Not Yet Taken"
                                        grade_display = "N/A"
                                else:
                                    # For other years: normal completed/not completed logic
                                    if is_completed:
                                        try:
                                            grade_val = float(grade_display)
                                            if grade_val >= 90:
                                                status = "🏆 Excellent"
                                            elif grade_val >= 85:
                                                status = "✅ Very Good"
                                            elif grade_val >= 80:
                                                status = "✅ Good"
                                            elif grade_val >= 75:
                                                status = "✅ Passed"
                                            else:
                                                status = "❌ Failed"
                                        except (ValueError, TypeError):
                                            status = "✅ Passed"
                                    else:
                                        status = "❌ Not Completed"
                                        grade_display = "N/A"
                                
                                display_data.append({
                                    "Subject Code": subject["subjectCode"],
                                    "Subject Name": subject["subjectName"],
                                    "Units": subject["units"],
                                    "Lec": subject["lec"],
                                    "Lab": subject["lab"],
                                    "Grade": grade_display,
                                    "Status": status,
                                    "Prerequisite": subject["prerequisite"]
                                })
                            
                            # Display the dataframe for this semester
                            display_df = pd.DataFrame(display_data)
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            # Calculate totals for this semester
                            total_units = pd.to_numeric(grp["units"], errors="coerce").fillna(0).sum()
                            total_lec = pd.to_numeric(grp["lec"], errors="coerce").fillna(0).sum()
                            total_lab = pd.to_numeric(grp["lab"], errors="coerce").fillna(0).sum()
                            
                            # Calculate average grade for this semester (only for completed subjects)
                            semester_grades = []
                            for _, subject in grp.iterrows():
                                subj_code = str(subject["subjectCode"])
                                for comp_subj in completed_subjects:
                                    if comp_subj["subject_code"] == subj_code:
                                        try:
                                            semester_grades.append(float(comp_subj['grade']))
                                        except (ValueError, TypeError):
                                            pass
                                        break
                            
                            avg_grade = sum(semester_grades) / len(semester_grades) if semester_grades else 0
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Units", f"{int(total_units)}")
                            with col2:
                                st.metric("Total Lec Hours", f"{int(total_lec)}")
                            with col3:
                                st.metric("Total Lab Hours", f"{int(total_lab)}")
                            with col4:
                                st.metric("Average Grade", f"{avg_grade:.1f}")

                            additional_elements.append(Paragraph(f"Total Units: {int(total_units)}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Total Lec Hours: {int(total_lec)}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Total Lab Hours: {int(total_lab)}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Average Grade: {avg_grade:.1f}", styles["Normal"]))
                            additional_elements.append(Spacer(1, 10))

                            st.markdown("---")
                            
                        # Overall summary for subjects
                        if student_year == 1:
                            st.subheader("📊 1st Year Subjects Summary")
                            additional_elements.append(Paragraph("📊 1st Year Subjects Summary", styles["Heading2"]))
                            additional_elements.append(Spacer(1, 10))
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                completed_count = len(completed_subjects)
                                st.metric("Completed", completed_count)
                            with col2:
                                total_subjects = len(past_current_subj_df)
                                not_taken_count = total_subjects - completed_count
                                st.metric("Not Yet Taken", not_taken_count)
                            with col3:
                                all_grades = [float(comp_subj['grade']) for comp_subj in completed_subjects]
                                overall_avg = sum(all_grades) / len(all_grades) if all_grades else 0
                                st.metric("Overall Average", f"{overall_avg:.1f}")
                            with col4:
                                excellent_count = len([g for g in all_grades if g >= 90])
                                st.metric("Excellent (≥90)", excellent_count)
                            additional_elements.append(Paragraph(f"Completed: {completed_count}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Not Yet Taken: {not_taken_count}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Overall Average: {overall_avg:.1f}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Excellent (≥90): {excellent_count}", styles["Normal"]))
                            additional_elements.append(Spacer(1, 10))
                        else:
                            st.subheader("📊 Past & Current Year Subjects Summary")
                            additional_elements.append(Paragraph("📊 Past & Current Year Subjects Summary", styles["Heading2"]))
                            additional_elements.append(Spacer(1, 10))
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                completed_count = len(completed_subjects)
                                st.metric("Completed", completed_count)
                            with col2:
                                total_subjects = len(past_current_subj_df)
                                not_completed_count = total_subjects - completed_count
                                st.metric("Not Completed", not_completed_count)
                            with col3:
                                all_grades = [float(comp_subj['grade']) for comp_subj in completed_subjects]
                                overall_avg = sum(all_grades) / len(all_grades) if all_grades else 0
                                st.metric("Overall Average", f"{overall_avg:.1f}")
                            with col4:
                                excellent_count = len([g for g in all_grades if g >= 90])
                                st.metric("Excellent (≥90)", excellent_count)
                            additional_elements.append(Paragraph(f"Completed: {completed_count}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Not Completed: {not_completed_count}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Overall Average: {overall_avg:.1f}", styles["Normal"]))
                            additional_elements.append(Paragraph(f"Excellent (≥90): {excellent_count}", styles["Normal"]))
                            additional_elements.append(Spacer(1, 10))
                        
                        st.markdown("---")
                else:
                    # Fallback: simple table if no curriculum data
                    completed_df = pd.DataFrame(completed_subjects)
                    if not completed_df.empty:
                        display_completed = completed_df[["subject_code", "subject_name", "grade"]].copy()
                        display_completed.columns = ["Subject Code", "Subject Name", "Grade"]
                        st.dataframe(display_completed, use_container_width=True, hide_index=True)
                    else:
                        st.info("No completed subjects found.")
                
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
                                    "Prerequisite": subject["prerequisite"]
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

                # Add PDF download button at the end
                if 'filtered_curr' in locals() and not filtered_curr.empty:
                    add_curriculum_pdf_download_button(filtered_curr, student_course, "All", True, student_info, completed_subjects)

        else:
            st.info("Please enter a student name to begin evaluation.")
