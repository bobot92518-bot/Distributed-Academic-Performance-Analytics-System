import streamlit as st
import altair as alt
import pandas as pd 
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from global_utils import result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

def create_grade_pdf(df, faculty_name, semester_filter=None, subject_filter=None, is_new_curriculum=False):
    """Generate PDF report for grades data"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, 
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
    title_text = "Grade Report"
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
    grouped = filtered_df.groupby(['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel'])
    
    for i, ((semester, school_year, subject_code, subject_desc, subject_year_level), group) in enumerate(grouped):
        
        if i > 0:
            elements.append(PageBreak())
        
        # Subject header
        subject_header = f"{semester} - {school_year} | {subject_code} - {subject_desc}"
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
            alignment=TA_LEFT
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
        curriculum_type = "NewCurr" if is_new_curriculum else "OldCurr"
        filename = f"Grade_Report_{curriculum_type}_{timestamp}.pdf"
        
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

def display_grades_table(is_new_curriculum, df, semester_filter = None, subject_filter = None):
    """Display grades in Streamlit format with PDF export option"""
    
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
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
    for (semester, school_year, subject_code, subject_desc, SubjectYearLevel), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription', 'SubjectYearLevel']
    ):
        
        with st.expander(f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code} &nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc} &nbsp;&nbsp; {subject_year_map.get(SubjectYearLevel, "")}", expanded=True):
            
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
            
            st.markdown("**📈 Class Grade Distribution Histogram**")

            # Define grade ranges
            def grade_category(g):
                if pd.isna(g) or g == 0:
                    return "Not Set"
                elif g < 75:
                    return "Needs Improvement (<75)"
                elif 75 <= g <= 84:
                    return "Good (75-84)"
                elif 85 <= g <= 94:
                    return "Very Good (85-94)"
                else:
                    return "Excellent (95-100)"

            table_data["Grade_Range"] = table_data["Grade_num"].apply(grade_category)

            # Histogram using bins
            hist_chart = (
                alt.Chart(table_data[table_data["Grade_Range"] != "Not Set"])
                .mark_bar(opacity=0.8)
                .encode(
                    x=alt.X('Grade_num:Q',
                            bin=alt.Bin(maxbins=20),
                            title='Grade Range'),
                    y=alt.Y('count():Q', title='Number of Students'),
                    color=alt.Color(
                        'Grade_Range:N',
                        title="Grade Category",
                        scale=alt.Scale(
                            domain=[
                                "Excellent (95-100)",
                                "Very Good (85-94)",
                                "Good (75-84)",
                                "Needs Improvement (<75)"
                            ],
                            range=["#28a745", "#17a2b8", "#ffc107", "#dc3545"]
                        )
                    ),
                    tooltip=['count():Q']
                )
                .properties(
                    height=300,
                    title="Grade Distribution Histogram"
                )
            )

            st.altair_chart(hist_chart, use_container_width=True)
            
    st.subheader("📄 Export Report")
    add_pdf_download_button(df, current_faculty, semester_filter, subject_filter, is_new_curriculum)

def show_faculty_tab1_info(new_curriculum):
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
    # Initialize Tab 1 specific session state
    if 'tab1_grades_df' not in st.session_state:
        st.session_state.tab1_grades_df = None
    if 'tab1_current_faculty' not in st.session_state:
        st.session_state.tab1_current_faculty = current_faculty
    if 'tab1_loaded_filters' not in st.session_state:
        st.session_state.tab1_loaded_filters = {} 
    
    semesters = get_semesters_list(new_curriculum)
    subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
    
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
                results = get_new_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            else:
                results = get_student_grades_by_subject_and_semester(current_faculty=current_faculty, semester_id = selected_semester_id, subject_code = selected_subject_code)
            
            if results:
                df = result_records_to_dataframe(results)
                
                # Store in TAB 1 SPECIFIC session state keys
                st.session_state.tab1_grades_df = df
                st.session_state.tab1_current_faculty = current_faculty
                st.session_state.tab1_loaded_filters = {
                    'semester': selected_semester_display,
                    'subject': selected_subject_display
                }
                
            else:
                st.warning(f"No grades found for {current_faculty} in the selected semester.")
                st.session_state.tab1_grades_df = None
    
    # Display grades if they exist in Tab 1 session state
    if st.session_state.tab1_grades_df is not None and not st.session_state.tab1_grades_df.empty:
        # Show current filter info for Tab 1
        if st.session_state.tab1_loaded_filters:
            st.info(f"📋 Tab 1 - Showing grades for: **{st.session_state.tab1_loaded_filters.get('semester', 'All')}** | **{st.session_state.tab1_loaded_filters.get('subject', 'All')}**")
        
        st.divider()
        display_grades_table(new_curriculum, st.session_state.tab1_grades_df, 
                           st.session_state.tab1_loaded_filters.get('semester'),
                           st.session_state.tab1_loaded_filters.get('subject'))
        
    elif st.session_state.tab1_grades_df is not None and st.session_state.tab1_grades_df.empty:
        st.warning("No students found matching the current filters.")
    else:
        st.info("👆 Select your filters and click 'Load Class' to view student data.")