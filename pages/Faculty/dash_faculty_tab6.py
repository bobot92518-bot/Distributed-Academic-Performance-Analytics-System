import streamlit as st
import altair as alt
import pandas as pd 
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.textlabels import Label
from io import BytesIO
from datetime import datetime
from global_utils import load_pkl_data, pkl_data_to_df, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

current_faculty = st.session_state.get('user_data', {}).get('Name', '')

def display_grades_table(is_new_curriculum, df, semester_filter=None, subject_filter=None, status_filter = None, student_name_filter=None, min_grade=None, max_grade=None):
    """Display grades in Streamlit format with additional filters"""
    if df.empty:
        st.warning("No grades found for the selected criteria.")
        return
    
    filtered_df = df.copy()
    if semester_filter and semester_filter != " - All Semesters - ":
        filtered_df = filtered_df[filtered_df['semester'] + " - " + filtered_df['schoolYear'].astype(str) == semester_filter]
    
    if subject_filter and subject_filter != " - All Subjects - ":
        filtered_df = filtered_df[filtered_df['subjectCode'] + " - " + filtered_df['subjectDescription'] == subject_filter]
    
    if student_name_filter:
        filtered_df = filtered_df[
            filtered_df['studentName'].str.contains(student_name_filter, case=False, na=False)
        ]
    
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
    
    for (semester, school_year, subject_code, subject_desc, SubjectYearLevel), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel']
    ):
        st.markdown(f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code} &nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc} &nbsp;&nbsp; {subject_year_map.get(SubjectYearLevel, "")}")
            
        table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
        table_data.columns = ['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade']
        
        table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
        table_data['Student ID'] = table_data['Student ID'].astype(str)
        
        
        if status_filter is not None:
            if status_filter == "Not Set":
                valid_grades_by_status = (table_data['Grade_num'].isna()) | (table_data['Grade_num'] == 0)
                table_data = table_data[valid_grades_by_status]

            elif status_filter == "Failed - Below 75":
                valid_grades_by_status = (table_data['Grade_num'].notna()) & (table_data['Grade_num'] < 75)
                table_data = table_data[valid_grades_by_status]

            elif status_filter == "Passed - Above 75":
                valid_grades_by_status = (table_data['Grade_num'].notna()) & (table_data['Grade_num'] >= 75)
                table_data = table_data[valid_grades_by_status]
            
        if min_grade is not None and max_grade is not None:
            valid_grades_in_range = (table_data['Grade_num'] >= min_grade) & (table_data['Grade_num'] <= max_grade)
            no_grades = (table_data['Grade_num'].isna()) | (table_data['Grade_num'] == 0)
            table_data = table_data[valid_grades_in_range]
        
        
        
        if table_data.empty:
            st.info("No students match the current grade range filter.")
            continue
        
        course_column = ""
        year_column = ""
        if is_new_curriculum:
            year_column = "Year Taken"
            table_data[f"{year_column}"] = year_map.get(SubjectYearLevel, "")
            course_column = "Year-Course"
            table_data[f"{course_column}"] = (table_data["Year Level"].map(year_map).fillna("") + " - " + table_data["Course"])
        else:
            course_column = "Course"
            year_column = "Year Level"
            table_data[f"{year_column}"] = table_data["Year Level"].map(year_map).fillna("")
        
        def pass_fail(g):
            if pd.isna(g) or g == 0:
                return "Not Set"
            return "Passed" if g >= 75 else "Failed"

        table_data['Pass/Fail'] = table_data['Grade_num'].apply(pass_fail)
        
        def grade_with_star(grade):
            if pd.isna(grade) or grade == 0:
                return "Not Set"
            else:
                if grade < 75:
                    return f"🛑 {grade}"
                else:
                    return f"⭐ {grade}"   

        table_data['Grade'] = table_data['Grade_num'].apply(grade_with_star)
        display_df = table_data[['Student ID', 'Student Name', f"{course_column}", f"{year_column}", 'Grade', 'Pass/Fail']]
        
        def color_status(val):
            if val == 'Passed':
                return 'color: green'
            elif val == 'Failed':
                return 'color: red'
            else:
                return 'color: gray'
        styled_df = (display_df.style.applymap(color_status, subset=['Pass/Fail']))

        # Quick stats
        valid_grades = table_data["Grade_num"][
            (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
        ]

        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.markdown("**Grades Summary**")
        freq_data = table_data["Grade_num"].value_counts().reset_index()
        freq_data.columns = ["Grade", "Frequency"]

        freq_data["Grade Status"] = freq_data["Grade"].apply(
            lambda g: "Not Set" if pd.isna(g) or g == 0
            else ("Pass" if g >= 75 else "Fail")
        )

        chart2 = (
            alt.Chart(freq_data)
            .mark_bar()
            .encode(
                x=alt.X("Grade:O", title="Grades", sort="ascending"),
                y=alt.Y("Frequency:Q", title="Number of Students"),
                color=alt.Color(
                    "Grade Status",
                    title="Grade Status",
                    scale=alt.Scale(
                        domain=["Pass", "Fail"],
                        range=["green", "red"]
                    )
                ),
                tooltip=["Grade", "Frequency"]
            )
        )

        st.altair_chart(chart2, use_container_width=True)
        
        st.divider()
        st.markdown("**Pass vs. Fail**")
        table_data["Grade Status"] = table_data["Grade_num"].apply(
            lambda g: "Not Set" if pd.isna(g) or g == 0
            else ("Pass" if g >= 75 else "Fail")
        )
        pass_fail_data = table_data["Grade Status"].value_counts().reset_index()
        pass_fail_data.columns = ["Grade Status", "Number of Students"]

        bars = (
            alt.Chart(pass_fail_data)
            .mark_bar()
            .encode(
                x=alt.X("Grade Status:N", title="Grade Category", sort=["Pass", "Fail", "Not Set"]),
                y=alt.Y("Number of Students:Q", title="Number of Students"),
                color=alt.Color(
                    "Grade Status",
                    scale=alt.Scale(
                        domain=["Pass", "Fail", "Not Set"],
                        range=["green", "red", "gray"]
                    )
                ),
                tooltip=["Grade Status", "Number of Students"]
            )
        )

        labels = (
            alt.Chart(pass_fail_data)
            .mark_text(dy=-10, fontSize=14, color="black")
            .encode(
                x="Grade Status:N",
                y="Number of Students:Q",
                text="Number of Students:Q"
            )
        )

        chart3 = bars + labels

        st.altair_chart(chart3, use_container_width=True)
        
        st.divider()
        st.markdown("**Pass vs. Fail (Pie Chart)**")
        
        pie = (
            alt.Chart(pass_fail_data)
            .mark_arc(innerRadius=0) 
            .encode(
                theta=alt.Theta("Number of Students:Q", title=""),
                color=alt.Color(
                    "Grade Status:N",
                    scale=alt.Scale(
                        domain=["Pass", "Fail", "Not Set"],
                        range=["green", "red", "gray"]
                    ),
                    legend=alt.Legend(title="Grade Status")
                ),
                tooltip=["Grade Status", "Number of Students"]
            )
        )

        st.altair_chart(pie, use_container_width=True)
    
    if not df.empty:
        pdf_bytes = generate_grades_pdf(
            current_faculty, is_new_curriculum, df,
            semester_filter, subject_filter,status_filter, student_name_filter,
            min_grade, max_grade
        )
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "NewCurr" if is_new_curriculum else "OldCurr"
        filename = f"Class_List_Custom_Query_{curriculum_type}_{timestamp}.pdf"

        st.divider()
        st.subheader("📄 Export Report")
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download Custom Query Build",
            key="download_pdf_tab6" 
        )

def show_faculty_tab6_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
    # First row: Semester and Subject selection
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab6_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab6_subject"
        )
    with col3:
        subject_options = [" - All - "] + ["Passed - Above 75"] + ["Failed - Below 75"] +["Not Set"]
        selected_grade_status = st.selectbox(
            "📚 Student Grade Status", 
            subject_options,
            key="tab6_grade_status"
        )
    
    # Second row: Student name search and grade range
    col4, col5, col6 = st.columns([1, 1, 1])
    with col4:
        student_name_filter = st.text_input(
            "🔍 Search Student Name",
            placeholder="Enter student name to filter...",
            key="tab6_student_search"
        )
    with col5:
        min_grade = st.number_input("Min grade", value=0.0, step=1.0, min_value=0.0, max_value=100.0, key="tab6_min_grade")
    with col6:
        max_grade = st.number_input("Max grade", value=100.0, step=1.0, min_value=0.0, max_value=100.0, key="tab6_max_grade")
    
    if max_grade < min_grade:
        max_grade = min_grade
    
    # Load button below all filters
    load_clicked = st.button("📊 Load Class", type="secondary", key="tab6_load_button")
    
    # Get selected IDs
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
    
    # Only process data when button is clicked
    if load_clicked:
        with st.spinner("Loading grades data..."):
            st.markdown("---")
            if new_curriculum:
                results = get_new_student_grades_by_subject_and_semester(
                    current_faculty=current_faculty, 
                    semester_id=selected_semester_id, 
                    subject_code=selected_subject_code
                )
            else:
                results = get_student_grades_by_subject_and_semester(
                    current_faculty=current_faculty, 
                    semester_id=selected_semester_id, 
                    subject_code=selected_subject_code
                )
            
            if results:
                df = result_records_to_dataframe(results)
                
                # Store in session state for other tabs
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                
                # Display results with all filters applied
                # st.success(f"Found {len(results)} grade records for {current_faculty}")
                print(df.head(1))
                df['Grade_num'] = pd.to_numeric(df['grade'], errors='coerce')
                valid_grades = df["Grade_num"][(df["Grade_num"].notna()) & (df["Grade_num"] > 0)]

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Students", len(df))
                with col2:
                    st.metric("Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "Not Set")
                with col3:
                    st.metric("Class Median", f"{valid_grades.median():.1f}" if not valid_grades.empty else "Not Set")
                with col4:
                    st.metric("Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "Not Set")
                with col5:
                    st.metric("Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "Not Set")

                
                display_grades_table(
                    new_curriculum, 
                    df, 
                    selected_semester_display, 
                    selected_subject_display,
                    selected_grade_status,
                    student_name_filter,
                    min_grade,
                    max_grade
                )
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
    else:
        # Show instruction message when no data is loaded
        st.info("👆 Click 'Load Class' to fetch and display grade data with your selected filters.")
        

def generate_grades_pdf(
    faculty_name, is_new_curriculum, df,
    semester_filter=None, subject_filter=None,
    student_name_filter=None, min_grade=None, max_grade=None,
    status_filter=None  # ✅ new
):
    """Generate a PDF report of student grades with summary, filters, and charts"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CenterHeading', alignment=1, fontSize=14, spaceAfter=10))
    
    # ---- Title & Metadata ----
    title = f"Grade Report ({'New Curriculum' if is_new_curriculum else 'Old Curriculum'})"
    elements.append(Paragraph(title, styles['CenterHeading']))
    elements.append(Paragraph(f"Faculty: {faculty_name}", styles['Normal']))
    if semester_filter:
        elements.append(Paragraph(f"Semester: {semester_filter}", styles['Normal']))
    if subject_filter:
        elements.append(Paragraph(f"Subject: {subject_filter}", styles['Normal']))
    if student_name_filter:
        elements.append(Paragraph(f"Student Name Filter: {student_name_filter}", styles['Normal']))
    if status_filter:
        elements.append(Paragraph(f"Status Filter: {status_filter}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # ---- Prepare data ----
    df["Grade_num"] = pd.to_numeric(df["grade"], errors="coerce")

    # ✅ Apply status filter
    if status_filter is not None:
        if status_filter == "Not Set":
            mask = (df["Grade_num"].isna()) | (df["Grade_num"] == 0)
            df = df[mask]
        elif status_filter == "Failed - Below 75":
            mask = (df["Grade_num"].notna()) & (df["Grade_num"] < 75)
            df = df[mask]
        elif status_filter == "Passed - Above 75":
            mask = (df["Grade_num"].notna()) & (df["Grade_num"] >= 75)
            df = df[mask]

    # ---- Quick stats ----
    valid_grades = df["Grade_num"][(df["Grade_num"].notna()) & (df["Grade_num"] > 0)]
    stats_data = [
        ["Total Students", len(df)],
        ["Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "Not Set"],
        ["Class Median", f"{valid_grades.median():.1f}" if not valid_grades.empty else "Not Set"],
        ["Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "Not Set"],
        ["Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "Not Set"],
    ]
    stats_table = Table(stats_data, colWidths=[150, 150])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 12))

    # ---- Grades table ----
    table_data = [["Student ID", "Student Name", "Course", "Year Level", "Grade", "Pass/Fail"]]
    for _, row in df.iterrows():
        grade_val = pd.to_numeric(row["grade"], errors="coerce")
        if pd.isna(grade_val) or grade_val == 0:
            grade_display = "Not Set"
            grade_status = "Not Set"
        else:
            grade_display = str(grade_val)
            grade_status = "Passed" if grade_val >= 75 else "Failed"
        table_data.append([
            row.get("StudentID", ""),
            row.get("studentName", ""),
            row.get("Course", ""),
            row.get("YearLevel", ""),
            grade_display,
            grade_status
        ])

    grade_table = Table(table_data, repeatRows=1)
    grade_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
    ]))
    elements.append(grade_table)
    elements.append(Spacer(1, 12))

    # ---- Charts ----
    # Grades Summary (bar chart)
    freq_data = df["Grade_num"].value_counts().reset_index()
    freq_data.columns = ["Grade", "Frequency"]
    freq_data = freq_data.sort_values("Grade")

    if not freq_data.empty:
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.bar(freq_data["Grade"], freq_data["Frequency"], color="skyblue")
        ax.set_title("Grades Summary")
        ax.set_xlabel("Grade")
        ax.set_ylabel("Number of Students")
        chart_buf = BytesIO()
        plt.savefig(chart_buf, format="png", bbox_inches="tight")
        plt.close(fig)
        chart_buf.seek(0)
        elements.append(Image(chart_buf, width=300, height=200))
        elements.append(Spacer(1, 12))

    # Pass vs Fail (bar + pie)
    status_counts = df["Grade_num"].apply(
        lambda g: "Not Set" if pd.isna(g) or g == 0 else ("Pass" if g >= 75 else "Fail")
    ).value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    if not status_counts.empty:
        colors_map = {"Pass": "green", "Fail": "red", "Not Set": "gray"}

        # Bar
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.bar(status_counts["Status"], status_counts["Count"],
               color=[colors_map.get(s, "blue") for s in status_counts["Status"]])
        ax.set_title("Pass vs Fail (Bar Graph)")
        ax.set_xlabel("Status")
        ax.set_ylabel("Number of Students")
        for i, val in enumerate(status_counts["Count"]):
            ax.text(i, val + 0.2, str(val), ha="center", fontsize=9)
        chart_buf2 = BytesIO()
        plt.savefig(chart_buf2, format="png", bbox_inches="tight")
        plt.close(fig)
        chart_buf2.seek(0)
        elements.append(Image(chart_buf2, width=250, height=200))
        elements.append(Spacer(1, 12))

        # Pie
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            status_counts["Count"],
            labels=status_counts["Status"],
            autopct='%1.1f%%',
            startangle=90,
            colors=[colors_map.get(s, "blue") for s in status_counts["Status"]]
        )
        ax.set_title("Pass vs Fail (Pie Chart)")
        pie_buf = BytesIO()
        plt.savefig(pie_buf, format="png", bbox_inches="tight")
        plt.close(fig)
        pie_buf.seek(0)
        elements.append(Image(pie_buf, width=250, height=250))

    # ---- Build PDF ----
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf