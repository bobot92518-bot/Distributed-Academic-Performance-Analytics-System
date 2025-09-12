import streamlit as st
import pandas as pd 
import altair as alt
import math
import io
from datetime import datetime
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from global_utils import pkl_data_to_df, semesters_cache, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semester, get_semesters_list, get_subjects_by_teacher, get_semester_from_curriculum, get_active_curriculum,get_student_grades_by_subject_and_semester, get_new_student_grades_from_db_by_subject_and_semester
from pages.Faculty.faculty_data_manager import save_new_student_grades

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

year_map = {
    1: "1st Year",
    2: "2nd Year",
    3: "3rd Year",
    4: "4th Year",
    5: "5th Year",
}    

        
def display_grades_radio(df_students,new_curriculum):
    st.markdown("### 🎓 Student Grades")
    
    # --- Grade Submission Status Summary ---
    if not df_students.empty:
        # Get current faculty name for the header
        current_faculty = st.session_state.get('user_data', {}).get('Name', '')
        
        # Calculate submission statistics
        total_students = len(df_students)
        submitted_grades = len(df_students[~(pd.isna(df_students['grade']) | (df_students['grade'] == 0))])
        submission_rate = (submitted_grades / total_students * 100) if total_students > 0 else 0
        
        # Get unique subject information from the dataframe
        if 'SubjectCode' in df_students.columns and 'SubjectDescription' in df_students.columns:
            unique_subjects = df_students[['SubjectCode', 'SubjectDescription']].drop_duplicates()
        else:
            # Fallback if columns don't exist - try to extract from session state or use placeholder
            unique_subjects = pd.DataFrame({
                'SubjectCode': ['N/A'],
                'SubjectDescription': ['Selected Subject']
            })
        
        # Display header
        st.markdown(f"**Grade Submission Status — {current_faculty}**")
        
        # Create summary table
        summary_data = []
        for _, subject_row in unique_subjects.iterrows():
            # Filter students for this specific subject if multiple subjects
            if len(unique_subjects) > 1:
                subject_students = df_students[df_students['SubjectCode'] == subject_code]
            else:
                subject_students = df_students
                
            subject_total = len(subject_students)
            subject_submitted = len(subject_students[~(pd.isna(subject_students['grade']) | (subject_students['grade'] == 0))])
            subject_rate = (subject_submitted / subject_total * 100) if subject_total > 0 else 0
            
            subject_val = st.session_state.loaded_filters.get('subject', 'All')
            subjectCode = ""
            subjectDesc = ""
            # Split into code and description
            if subject_val is not None and  subject_val != "All":
                parts = [p.strip() for p in subject_val.split('-', 1)]  # split only at the first '-'
                subjectCode = parts[0] if len(parts) > 0 else ""
                subjectDesc = parts[1] if len(parts) > 1 else ""
            
            summary_data.append({
                'Course Code': subjectCode,
                'Course Description': subjectDesc,
                'Submitted Grades': subject_submitted,
                'Total Students': subject_total,
                'Submission Rate': f"{subject_rate:.0f}%"
            })
        
        # Display as DataFrame
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Course Code': st.column_config.TextColumn('Course Code', width="medium"),
                'Course Description': st.column_config.TextColumn('Course Description', width="large"),
                'Submitted Grades': st.column_config.NumberColumn('Submitted Grades', width="medium"),
                'Total Students': st.column_config.NumberColumn('Total Students', width="medium"),
                'Submission Rate': st.column_config.TextColumn('Submission Rate', width="medium"),
            }
        )
        
        st.markdown("---")  # Add separator
    

    # --- Persist selected student ---
    if "selected_student_id" not in st.session_state:
        st.session_state.selected_student_id = None

    # --- Pagination setup ---
    page_size = 10
    total_students = len(df_students)
    total_pages = (total_students - 1) // page_size + 1

    if "page" not in st.session_state:
        st.session_state.page = 1

    # Page selector
    page = st.number_input(
        "Page",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.page,
        step=1,
        key="pagination_input"  # Add unique key to prevent conflicts
    )
    st.session_state.page = page

    # Slice dataframe for current page
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df_students.iloc[start_idx:end_idx]

    # --- Radio options (IDs as values, pretty labels for display) ---
    student_choices = df_page["StudentID"].tolist()
    student_labels = [
        f"{row['StudentID']} - {row['studentName']} ({row['Course']}, Year {row['YearLevel']}, Grade: {"Not Set" if pd.isna(row['grade']) or row['grade'] == 0 else row['grade']})"
        for _, row in df_page.iterrows()
    ]

    selected = st.radio(
        "Select a student to view grades:",
        options=student_choices,
        format_func=lambda x: dict(zip(student_choices, student_labels))[x],
        key="student_radio_selection"   # Use a more descriptive key
    )

    # Save selection
    st.session_state.selected_student_id = selected

    # --- Show details if selected ---
    if st.session_state.selected_student_id:
        student_row = df_students[df_students["StudentID"] == st.session_state.selected_student_id].iloc[0]

        year_map = {
            1: "1st Year",
            2: "2nd Year",
            3: "3rd Year",
            4: "4th Year",
            5: "5th Year",
        }
        
        student_year = year_map.get(student_row["YearLevel"], str(student_row["YearLevel"]))

        st.markdown("""
        <style>
        .readonly-box {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 0.5rem 0.75rem;
            margin-bottom: 0.5rem;
            font-size: 0.95rem;
            color: #333;
        }
        .readonly-label {
            font-weight: 600;
            margin-bottom: 0.2rem;
            display: block;
            font-size: 0.85rem;
            color: #555;
        }
        </style>
        """, unsafe_allow_html=True)

        stud_grade = student_row["grade"]
        grade_status = "⚠️ PENDING" if pd.isna(stud_grade) or stud_grade == 0 else f" ✅ DONE - {stud_grade}"
        status_color = "orange" if grade_status == "⚠️ PENDING" else "green"
        save_label = "Save" if pd.isna(stud_grade) or stud_grade  == 0 else "Update"
        semester_df = get_semester(student_row["semester"], student_row["schoolYear"])
        SemesterID = int(semester_df["_id"].iloc[0])

        # Show details in readonly-style input boxes
        st.markdown(f"""#### 📄 Selected Student Info &nbsp; | &nbsp; &nbsp; Grade Submission Status: <span style='color:{status_color}; font-weight:bold;'>{grade_status}</span>""",unsafe_allow_html=True)

        st.markdown(f"<span class='readonly-label'>🆔 Student ID</span><div class='readonly-box'>{student_row['StudentID']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>👤 Name</span><div class='readonly-box'>{student_row['studentName']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>🎓 Course</span><div class='readonly-box'>{student_row['Course']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='readonly-label'>📘 Year Level</span><div class='readonly-box'>{student_year}</div>", unsafe_allow_html=True)


        # if new_curriculum:
            
        #     new_grade = st.number_input(
        #         "⭐ Grade",
        #         value=float(student_row["grade"]),
        #         min_value=0.0,
        #         max_value=100.0,
        #         step=0.1,
        #         format="%.1f",
        #         key="grade_input"  # Add unique key
        #     )

        #     if st.button(f"💾 {save_label} Grade", key="save_grade_btn"):
        #         with st.spinner("⏳ Saving grade, please wait..."):
        #             try:
        #                 result = save_new_student_grades(student_id=student_row["StudentID"], subject_code=student_row["subjectCode"], grade=new_grade, semester_id=SemesterID, teacher=current_faculty)
        #                 if result["success"]:
        #                     st.success(f"✅ {result['message']}")
        #                     st.rerun()  
        #                 else:
        #                     st.error(f"❌ {result['message']}")
        #             except Exception as e:
        #                 st.error(f"❌ Error saving grade: {str(e)}")
        # else:
        grade_display = stud_grade if not pd.isna(stud_grade)  else "No Grade"
        st.markdown(f"<span class='readonly-label'>⭐ Grade</span><div class='readonly-box'>{grade_display}</div>", unsafe_allow_html=True)


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
    
    col1, col2 = st.columns([1, 1])
    
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab5_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab5_subject"
        )
    search_name = st.text_input("🔍 Search Student Name", value="",key="tab5_search_name",placeholder="Type a student name...")
    
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
            
    if st.button("📊 Load Grades", type="secondary", key="tab5_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_from_db_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            else:
                results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
            
            if results:
                df = result_records_to_dataframe(results)
                if search_name.strip():
                    df = df[df["studentName"].str.contains(search_name, case=False, na=False)]
                
                # Store in session state for persistence
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                st.session_state.loaded_filters = {
                    'semester': selected_semester_display,
                    'subject': selected_subject_display,
                    'search_name': search_name
                }
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
                st.session_state.grades_df = None
    
    # Display grades if they exist in session state
    if st.session_state.grades_df is not None and not st.session_state.grades_df.empty:
        # Show current filter info
        if st.session_state.loaded_filters:
            st.info(f"📋 Showing grades for: **{st.session_state.loaded_filters.get('semester', 'All')}** | **{st.session_state.loaded_filters.get('subject', 'All')}**" + 
                   (f" | Search: **{st.session_state.loaded_filters.get('search_name')}**" if st.session_state.loaded_filters.get('search_name') else ""))
        
        display_grades_radio(st.session_state.grades_df,new_curriculum)
    elif st.session_state.grades_df is not None and st.session_state.grades_df.empty:
        st.warning("No students found matching the current filters.")
    else:
        st.info("👆 Select your filters and click 'Load Grades' to view student data.")
    
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

    pdf_bytes = generate_grades_pdf(
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
def generate_grades_pdf(faculty_name, df, filters, selected_student=None):
    # Use in-memory buffer instead of saving file
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
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
    styles.add(ParagraphStyle(name="CenterHeading", alignment=1, fontSize=14, spaceAfter=12))
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        alignment=TA_LEFT,
        textColor=colors.darkblue
    )
    # --- Title + filter info ---
    title = "📄 Student Grades Status Report"
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Faculty: {faculty_name}", styles['Normal']))

    if filters:
        sem = filters.get("semester", "All")
        subj = filters.get("subject", "All")
        search = filters.get("search_name", "")
        elements.append(Paragraph(f"Semester: {sem}", styles['Normal']))
        elements.append(Paragraph(f"Subject: {subj}", styles['Normal']))
        if search:
            elements.append(Paragraph(f"Search filter: {search}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # --- Grade Submission Status Summary ---
    if not df.empty:
        elements.append(Paragraph(f"Grade Submission Status — {faculty_name}", subtitle_style))
        
        subject_val = st.session_state.loaded_filters.get('subject', 'All')
        subject_code = ""
        subject_desc = ""
        # Split into code and description
        if subject_val is not None and  subject_val != "All":
            parts = [p.strip() for p in subject_val.split('-', 1)]  # split only at the first '-'
            subject_code = parts[0] if len(parts) > 0 else ""
            subject_desc = parts[1] if len(parts) > 1 else ""
        
        # Calculate submission statistics
        # Get unique subject information from the dataframe
        if 'SubjectCode' in df.columns and 'SubjectDescription' in df.columns:
            unique_subjects = df[['SubjectCode', 'SubjectDescription']].drop_duplicates()
        else:
            # Fallback - try to extract subject info from filters or use placeholder
            subject_from_filter = filters.get("subject", "N/A - Selected Subject")
            if " - " in subject_from_filter:
                code, desc = subject_from_filter.split(" - ", 1)
            else:
                code, desc = "N/A", subject_from_filter
            unique_subjects = pd.DataFrame({
                'SubjectCode': [code],
                'SubjectDescription': [desc]
            })
        
        # Create summary table
        summary_table_data = [["Course Code", "Course Title", "Submitted Grades", "Total Students", "Submission Rate"]]
        
        for _, subject_row in unique_subjects.iterrows():
            # Filter students for this specific subject if multiple subjects
            if len(unique_subjects) > 1:
                subject_students = df[df['SubjectCode'] == subject_code]
            else:
                subject_students = df
                
            subject_total = len(subject_students)
            subject_submitted = len(subject_students[~(pd.isna(subject_students['grade']) | (subject_students['grade'] == 0))])
            subject_rate = (subject_submitted / subject_total * 100) if subject_total > 0 else 0
            
            summary_table_data.append([
                subject_code,
                subject_desc,
                str(subject_submitted),
                str(subject_total),
                f"{subject_rate:.0f}%"
            ])

        summary_table = Table(summary_table_data, repeatRows=1, hAlign="LEFT")
        summary_style = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2E8B57")),  # Sea Green header
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.lightgrey])
        ])
        
        # Color code the submission rates
        for i in range(1, len(summary_table_data)):
            rate_text = summary_table_data[i][4]
            rate_value = float(rate_text.replace('%', ''))
            
            if rate_value == 100:
                summary_style.add("TEXTCOLOR", (4, i), (4, i), colors.green)
                summary_style.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")
            elif rate_value >= 80:
                summary_style.add("TEXTCOLOR", (4, i), (4, i), colors.blue)
                summary_style.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")
            elif rate_value >= 50:
                summary_style.add("TEXTCOLOR", (4, i), (4, i), colors.orange)
                summary_style.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")
            else:
                summary_style.add("TEXTCOLOR", (4, i), (4, i), colors.red)
                summary_style.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")

        summary_table.setStyle(summary_style)
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

    
    # --- Student Grades Table ---
    table_data = [["Student ID", "Name", "Course", "Year", "Grade", "Submission Status"]]
    for _, row in df.iterrows():
        year = year_map.get(row["YearLevel"], str(row["YearLevel"]))
        grade_display = "Not Set" if pd.isna(row["grade"]) or row["grade"] == 0 else str(row["grade"])
        grade_status = "PENDING" if pd.isna(row["grade"]) or row["grade"] == 0 else "DONE"
        table_data.append([
            row["StudentID"],
            row["studentName"],
            row["Course"],
            year,
            grade_display,
            grade_status
        ])

    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F81BD")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey])
    ])
    
    # ✅ Conditional coloring ONLY for "Submission Status" column (index = 5)
    for i, row in enumerate(table_data[1:], start=1):  # skip header
        status = row[5]
        if status == "PENDING":
            style.add("TEXTCOLOR", (5, i), (5, i), colors.red)
            style.add("FONTNAME", (5, i), (5, i), "Helvetica-Bold")
        elif status == "DONE":
            style.add("TEXTCOLOR", (5, i), (5, i), colors.green)
            style.add("FONTNAME", (5, i), (5, i), "Helvetica-Bold")

    table.setStyle(style)
    elements.append(table)

    # --- Selected student details ---
    if selected_student is not None:
        elements.append(PageBreak())
        elements.append(Paragraph("Selected Student Info", styles['Heading2']))

        stud_grade = selected_student.get("grade")
        grade_display = "Not Set" if pd.isna(stud_grade) or stud_grade == 0 else str(stud_grade)
        grade_status2 = "PENDING" if pd.isna(stud_grade) or stud_grade == 0 else f"DONE"

        detail_data = [
            ["🆔 Submission Status", grade_status2],
            ["🆔 Student ID", selected_student["StudentID"]],
            ["👤 Name", selected_student["studentName"]],
            ["🎓 Course", selected_student["Course"]],
            ["📘 Year Level", year_map.get(selected_student["YearLevel"], str(selected_student["YearLevel"]))],
            ["⭐ Grade", grade_display]
        ]
        detail_table = Table(detail_data, colWidths=[100, 300])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), colors.lightgrey),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("ALIGN", (0,0), (0,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BOX", (0,0), (-1,-1), 0.25, colors.black),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.grey),
        ]))
        elements.append(detail_table)
        

    # Build PDF into buffer
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes