import streamlit as st
import altair as alt
import pandas as pd 
import matplotlib.pyplot as plt
import io
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib.units import inch
from datetime import datetime
from global_utils import load_pkl_data, pkl_data_to_df, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_distinct_section_per_subject, get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

current_faculty = st.session_state.get('user_data', {}).get('Name', '')


def generate_grade_analytics_pdf(is_new_curriculum, df, semester_filter, subject_filter,selected_section_value):
    buffer = io.BytesIO()

    # Landscape PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=20, leftMargin=20,
        topMargin=20, bottomMargin=20
    )

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

    elements = []

    # Title
    title = f"Grade Analytics Report ({'New Curriculum' if is_new_curriculum else 'Old Curriculum'})"
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Teacher: {current_faculty}", styles['Normal']))
    elements.append(Paragraph(f"Semester: {semester_filter}", styles['Normal']))
    elements.append(Paragraph(f"Subject: {subject_filter}", styles['Normal']))
    elements.append(Paragraph(f"Subject Class: {selected_section_value}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Convert df for display
    df['Grade_num'] = pd.to_numeric(df['grade'], errors='coerce')
    df['Pass/Fail'] = df['Grade_num'].apply(
        lambda g: "Not Set" if pd.isna(g) or g == 0 else ("Pass" if g >= 75 else "Fail")
    )

    # Summary Table
    summary_data = [
        ["Total Students", len(df)],
        ["Class Average", f"{df['Grade_num'].mean():.1f}" if not df['Grade_num'].dropna().empty else "Not Set"],
        ["Class Median", f"{df['Grade_num'].median():.1f}" if not df['Grade_num'].dropna().empty else "Not Set"],
        ["Highest Grade", f"{df['Grade_num'].max()}" if not df['Grade_num'].dropna().empty else "Not Set"],
        ["Lowest Grade", f"{df['Grade_num'].min()}" if not df['Grade_num'].dropna().empty else "Not Set"]
    ]

    table = Table(summary_data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(Paragraph("Class Summary", styles['Heading2']))
    elements.append(table)
    elements.append(Spacer(1, 12))
    
    year_map = {
        1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year", 5: "5th Year"
    }

    df = df.copy()
    df['Grade_num'] = pd.to_numeric(df['grade'], errors='coerce')

    def pass_fail(g):
        if pd.isna(g) or g == 0:
            return "Not Set"
        return "Pass" if g >= 75 else "Fail"

    def grade_with_star(g):
        if pd.isna(g) or g == 0:
            return "Not Set"
        return f"⭐ {int(g)}" if g >= 75 else f"🛑 {int(g)}"

    df["Pass/Fail"] = df["Grade_num"].apply(pass_fail)
    df["Grade"] = df["Grade_num"].apply(grade_with_star)
    df["Year Level"] = df["YearLevel"].map(year_map).fillna("")

    display_df = df[["StudentID", "studentName", "Course", "Year Level", "Grade", "Pass/Fail"]].copy()
    display_df.columns = ["Student ID", "Student Name", "Course", "Year Level", "Grade", "Pass/Fail"]

    # Prepare table data
    table_data = [list(display_df.columns)] + display_df.astype(str).values.tolist()

    # Build PDF Table
    table = Table(table_data, repeatRows=1)
    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ])

    # Add colors for Pass/Fail column
    pass_fail_col_idx = list(display_df.columns).index("Pass/Fail")
    for row_idx, row in enumerate(table_data[1:], start=1):
        status = row[pass_fail_col_idx]
        if status == "Pass":
            table_style.add('TEXTCOLOR', (pass_fail_col_idx, row_idx), (pass_fail_col_idx, row_idx), colors.green)
        elif status == "Fail":
            table_style.add('TEXTCOLOR', (pass_fail_col_idx, row_idx), (pass_fail_col_idx, row_idx), colors.red)
        else:
            table_style.add('TEXTCOLOR', (pass_fail_col_idx, row_idx), (pass_fail_col_idx, row_idx), colors.grey)

    table.setStyle(table_style)

    elements.append(Paragraph("Class Grades Table", styles['Heading2']))
    elements.append(table)
    elements.append(Spacer(1, 12))


    # 📊 Grades Summary Chart (bar)
    freq_data = df['Grade_num'].value_counts().reset_index()
    freq_data.columns = ["Grade", "Frequency"]

    if not freq_data.empty:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(freq_data["Grade"], freq_data["Frequency"], color="skyblue")
        ax.set_title("Grades Summary")
        ax.set_xlabel("Grades")
        ax.set_ylabel("Number of Students")

        img_bytes = io.BytesIO()
        plt.savefig(img_bytes, format="png")
        plt.close(fig)
        img_bytes.seek(0)
        elements.append(Image(img_bytes, width=5*inch, height=3*inch))
        elements.append(Spacer(1, 12))

    # 📊 Pass vs Fail Bar Chart
    pass_fail_data = df["Pass/Fail"].value_counts().reset_index()
    pass_fail_data.columns = ["Grade Status", "Number of Students"]

    if not pass_fail_data.empty:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(pass_fail_data["Grade Status"], pass_fail_data["Number of Students"],
               color=["green" if x=="Pass" else "red" if x=="Fail" else "gray" for x in pass_fail_data["Grade Status"]])
        ax.set_title("Pass vs Fail")
        ax.set_xlabel("Grade Status")
        ax.set_ylabel("Number of Students")

        img_bytes = io.BytesIO()
        plt.savefig(img_bytes, format="png")
        plt.close(fig)
        img_bytes.seek(0)
        elements.append(Image(img_bytes, width=5*inch, height=3*inch))
        elements.append(Spacer(1, 12))

    # 📊 Pass vs Fail Pie Chart
    if not pass_fail_data.empty:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(
            pass_fail_data["Number of Students"],
            labels=pass_fail_data["Grade Status"],
            autopct="%1.1f%%",
            colors=["green" if x=="Pass" else "red" if x=="Fail" else "gray" for x in pass_fail_data["Grade Status"]]
        )
        ax.set_title("Pass vs Fail (Pie Chart)")

        img_bytes = io.BytesIO()
        plt.savefig(img_bytes, format="png")
        plt.close(fig)
        img_bytes.seek(0)
        elements.append(Image(img_bytes, width=4.5*inch, height=4.5*inch))
        elements.append(Spacer(1, 12))

    # Build PDF
    doc.build(elements)
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value

def display_grades_table(is_new_curriculum, df, semester_filter = None, subject_filter = None):
    """Display grades in Streamlit format"""
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
            table_data.columns = ['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade']
            
            table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
            table_data['Student ID'] = table_data['Student ID'].astype(str)
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
            # table_data['Year Level'] = table_data['Year Level'].map(year_map).fillna(table_data['Year Level'].astype(str))
            def pass_fail(g):
                if pd.isna(g) or g == 0:
                    return "Not Set"
                return "Pass" if g >= 75 else "Fail"

            table_data['Pass/Fail'] = table_data['Grade_num'].apply(pass_fail)
            # table_data['Pass/Fail'] = table_data['Grade_num'].apply(lambda g: 'Pass' if g >= 75 else 'Fail')
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
                if val == 'Pass':
                    return 'color: green'
                elif val == 'Fail':
                    return 'color: red'
                else:
                    return 'color: gray'
            styled_df = (display_df.style.applymap(color_status, subset=['Pass/Fail']))
            # Final display

            # Quick stats
            valid_grades = table_data["Grade_num"][
                (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
            ]

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Students", len(table_data))
            with col2:
                st.metric("Class Average", f"{valid_grades.mean():.1f}" if not valid_grades.empty else "Not Set")
            with col3:
                st.metric("Class Median", f"{valid_grades.median():.1f}" if not valid_grades.empty else "Not Set")
            with col4:
                st.metric("Highest Grade", f"{valid_grades.max()}" if not valid_grades.empty else "Not Set")
            with col5:
                st.metric("Lowest Grade", f"{valid_grades.min()}" if not valid_grades.empty else "Not Set")

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

            # Bar chart
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

            # Text labels on top of bars
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

def add_grade_analytics_pdf_generator(df, is_new_curriculum, semester_filter, subject_filter, selected_section_value):
    if df is None or df.empty:
        st.warning("No data available to export to PDF.")
        return
    try:
        pdf_bytes = generate_grade_analytics_pdf(is_new_curriculum, df, semester_filter, subject_filter, selected_section_value)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "New" if is_new_curriculum else "Old"
        filename = f"Grade_Analytics_{curriculum_type}_{timestamp}.pdf"

        st.divider()
        st.subheader("📄 Export Report")
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download Students Grade Analytics (LO1)",
            key="download_pdf_tab7"
        )
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")


def show_faculty_tab7_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab7_semester"
        )
    with col2:
        subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
        selected_subject_display = st.selectbox(
            "📚 Select Subject", 
            subject_options,
            key="tab7_subject"
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
    
    sections = []
    if selected_subject_code:
        sections = get_distinct_section_per_subject(selected_subject_code, current_faculty)
    
    if (new_curriculum):
        with col3:
            if sections:
                # Build section options with value/label mapping
                section_options = []
                for row in sections:
                    subj_code = row["SubjectCodes"]
                    for sec in row["section"]:
                        section_options.append({"value": sec, "label": f"{subj_code}{sec}"})

                # Use the labels for the selectbox display
                selected_section_label = st.selectbox(
                    "📝 Select Section",
                    [opt["label"] for opt in section_options],
                    key="tab7_subject_section",
                    help="Choose a section to track student progress"
                )

                # Get the actual section value back
                selected_section_value = next(
                    (opt["value"] for opt in section_options if opt["label"] == selected_section_label),
                    None
                )

            else:
                selected_section_value = None
            
    if st.button("📊 Load Class", type="secondary", key="tab7_load_button"):
        with st.spinner("Loading grades data..."):
            
            if new_curriculum:
                results = get_new_student_grades_by_subject_and_semester(
                    current_faculty=current_faculty, 
                    semester_id = selected_semester_id, 
                    subject_code = selected_subject_code
                )
                results = [res for res in results if res["section"] == selected_section_value]
            else:
                results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
            if results:
                df = result_records_to_dataframe(results)
                
                # Store in session state for other tabs
                st.session_state.grades_df = df
                st.session_state.current_faculty = current_faculty
                
                # Display results
                st.success(f"Found {len(results)} grade records for {current_faculty}")
                
                display_grades_table(new_curriculum, df, selected_semester_display, selected_subject_display)
                add_grade_analytics_pdf_generator(df, new_curriculum, selected_semester_display, selected_subject_display, selected_section_value)
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
                