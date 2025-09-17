import streamlit as st
import altair as alt
import pandas as pd 
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from datetime import datetime
from global_utils import load_pkl_data, pkl_data_to_df, result_records_to_dataframe
from pages.Faculty.faculty_data_helper import get_distinct_section_per_subject, get_semesters_list, get_subjects_by_teacher, get_student_grades_by_subject_and_semester, get_new_student_grades_by_subject_and_semester

def create_advanced_grade_pdf(df, faculty_name, semester_filter=None, subject_filter=None, is_new_curriculum=False):
    """Generate advanced PDF report with tables and charts"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    styles.add(ParagraphStyle(name="CenterHeading", fontSize=14, leading=16, alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="NormalLeft", fontSize=10, leading=12, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="TableCell", fontSize=9, leading=11, alignment=TA_LEFT, wordWrap='CJK'))  # Wrap text

    elements = []

    # Title
    title = f"Student Progress Tracking ({'New Curriculum' if is_new_curriculum else 'Old Curriculum'})"
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"<b>Faculty:</b> {faculty_name}", styles['Normal']))
    if semester_filter:
        elements.append(Paragraph(f"<b>Semester:</b> {semester_filter}", styles['Normal']))
    if subject_filter:
        elements.append(Paragraph(f"<b>Subject:</b> {subject_filter}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Process data similar to display_student_progress
    year_map = {
        1: "1st Year", 2: "2nd Year", 3: "3rd Year",
        4: "4th Year", 5: "5th Year",
    }

    # Apply filters
    filtered_df = df.copy()
    if semester_filter and semester_filter != " - All Semesters - ":
        filtered_df = filtered_df[filtered_df['semester'] + " - " + filtered_df['schoolYear'].astype(str) == semester_filter]
    
    if subject_filter and subject_filter != " - All Subjects - ":
        filtered_df = filtered_df[filtered_df['subjectCode'] + " - " + filtered_df['subjectDescription'] == subject_filter]
    
    if filtered_df.empty:
        elements.append(Paragraph("No data available for the selected filters.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # Process each group similar to display_student_progress
    for (semester, school_year, subject_code, subject_desc, NewCourse, SubjectYearLevel, section), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription','NewCourse', 'SubjectYearLevel', 'section']
    ):
        
        if is_new_curriculum:
            extra_info = f" | {NewCourse} - {year_map.get(SubjectYearLevel, '')}"
        else:
            extra_info = ""

        # Section Header
        section_title = f"{semester} - {school_year} | {subject_code}{section} - {subject_desc}{extra_info}"
        elements.append(Paragraph(section_title, styles['Heading2']))
        elements.append(Spacer(1, 12))

        # Prepare table data
        table_data = group[['StudentID', 'studentName', 'Course', 'YearLevel', 'grade']].copy()
        table_data.columns = ['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade']
        table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
        table_data['Student ID'] = table_data['Student ID'].astype(str)

        # Format Grade
        def grade_status(grade):
            if pd.isna(grade) or grade == 0:
                return "Not Set"
            else:
                return f"{grade:.1f}"
        table_data['Grade'] = table_data['Grade_num'].apply(grade_status)

        # Add performance category
        def performance_indicator(grade):
            if pd.isna(grade) or grade == 0:
                return "⚪ Not Set"
            elif grade >= 95:
                return "🥇 Stable High"
            elif grade >= 85:
                return "🥈 Improving"
            elif grade >= 75:
                return "🥉 Consistent"
            else:
                return "📚 Needs Attention"
        table_data['Performance'] = table_data['Grade_num'].apply(performance_indicator)

        # Final display DataFrame
        display_df = table_data[['Student ID', 'Student Name', 'Course', 'Year Level', 'Grade', 'Performance']]

        # Convert for PDF
        pdf_table_data = [list(display_df.columns)] + display_df.values.tolist()

        table = Table(pdf_table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('BOX', (0,0), (-1,-1), 0.25, colors.black),
        ]))
        
        valid_grades = table_data["Grade_num"][(table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)]

        # Performance counts
        excellent_count = len(table_data[table_data['Grade_num'] >= 95])
        very_good_count = len(table_data[(table_data['Grade_num'] >= 85) & (table_data['Grade_num'] < 95)])
        good_count = len(table_data[(table_data['Grade_num'] >= 75) & (table_data['Grade_num'] < 85)])
        needs_improvement_count = len(table_data[(table_data['Grade_num'] > 0) & (table_data['Grade_num'] < 75)])
        not_set_count = len(table_data[(table_data['Grade_num'].isna()) | (table_data['Grade_num'] == 0)])

        # Basic Statistics
        if not valid_grades.empty:
            avg_val = f"{valid_grades.mean():.1f}"
            median_val = f"{valid_grades.median():.1f}"
            max_val = f"{valid_grades.max():.0f}"
            min_val = f"{valid_grades.min():.0f}"
        else:
            avg_val = median_val = max_val = min_val = "Not Set"

        stats_data = [
            ["Total Students", "Class Average", "Class Median", "Highest Grade", "Lowest Grade"],
            [len(table_data), avg_val, median_val, max_val, min_val]
        ]

        stats_table = Table(stats_data, colWidths=[1.2*inch]*5, hAlign="CENTER")
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))

        elements.append(Paragraph("📊 Basic Statistics", styles['Normal']))
        elements.append(stats_table)
        elements.append(Spacer(1, 20))

        # Performance Breakdown
        excellent_rate = f"{(excellent_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
        very_good_rate = f"{(very_good_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
        good_rate = f"{(good_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
        needs_improvement_rate = f"{(needs_improvement_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
        not_set_rate = f"{(not_set_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"

        perf_data = [
            ["🥇 Stable High (95+)", "🥈 Improving (85-94)", "🥉 Consistent (75-84)", "📚 Needs Attention (<75)", "⚪ Not Set"],
            [f"{excellent_count} ({excellent_rate})", 
             f"{very_good_count} ({very_good_rate})", 
             f"{good_count} ({good_rate})", 
             f"{needs_improvement_count} ({needs_improvement_rate})", 
             f"{not_set_count} ({not_set_rate})"]
        ]

        perf_table = Table(perf_data, colWidths=[1.4*inch]*5, hAlign="CENTER")
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))

        elements.append(Paragraph("🎯 Performance Breakdown", styles['Normal']))
        elements.append(perf_table)
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("📋 Student Progress Table", styles['Normal']))
        elements.append(table)
        elements.append(Spacer(1, 20))

        # === Add charts matching display_student_progress ===
        def add_chart(fig, caption):
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format="png", bbox_inches="tight", dpi=150)
            img_buffer.seek(0)
            from reportlab.platypus import Image
            img = Image(img_buffer, width=6*inch, height=3*inch)
            elements.append(img)
            elements.append(Paragraph(caption, styles['NormalLeft']))
            elements.append(Spacer(1, 12))
            plt.close(fig)

        # Prepare progress data (similar to display_progress_charts)
        progress_data = table_data.copy()
        progress_data = progress_data[progress_data['Grade_num'].notna() & (progress_data['Grade_num'] > 0)]
        
        if not progress_data.empty:
            progress_data = progress_data.reset_index(drop=True)
            progress_data['Student_Index'] = progress_data.index + 1
            
            # Define grade ranges and colors
            def get_grade_range_color(grade):
                if grade >= 95:
                    return '#28a745'  # Green
                elif grade >= 85:
                    return '#17a2b8'  # Blue
                elif grade >= 75:
                    return '#ffc107'  # Yellow
                else:
                    return '#dc3545'  # Red
            
            colors_list = [get_grade_range_color(grade) for grade in progress_data['Grade_num']]

            # 1. Grade Progression Line Chart
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Plot line with points
            ax.plot(progress_data['Student_Index'], progress_data['Grade_num'], 
                   marker='o', linestyle='-', linewidth=2, markersize=6, 
                   color='steelblue', alpha=0.8)
            
            # Color points by performance level
            scatter = ax.scatter(progress_data['Student_Index'], progress_data['Grade_num'], 
                               c=colors_list, s=50, alpha=0.8, edgecolors='black', linewidth=0.5)
            
            # Add average line
            if not progress_data['Grade_num'].empty:
                avg_grade = progress_data['Grade_num'].mean()
                ax.axhline(y=avg_grade, color='orange', linestyle='--', linewidth=2, 
                          alpha=0.7, label=f'Average: {avg_grade:.1f}')
                ax.legend()
            
            ax.set_xlabel('Student Sequence')
            ax.set_ylabel('Grade')
            ax.set_title(f'Grade Progression for {subject_desc}')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)
            
            add_chart(fig, "📊 Grade Progression Line Chart - Shows grade progression across students with performance color coding")

            # 2. Grade Distribution Scatter Plot
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Create scatter plot with color coding
            scatter = ax.scatter(progress_data['Student_Index'], progress_data['Grade_num'], 
                               c=colors_list, s=80, alpha=0.7, edgecolors='black', linewidth=0.5)
            
            # Add reference lines for grade boundaries
            ref_grades = [75, 85, 95]
            ref_labels = ['Consistent (75)', 'Improving (85)', 'Stable High (95)']
            ref_colors = ['#ffc107', '#17a2b8', '#28a745']
            
            for grade, label, color in zip(ref_grades, ref_labels, ref_colors):
                ax.axhline(y=grade, color=color, linestyle=':', alpha=0.6, linewidth=1)
                ax.text(0.02, grade + 1, label, transform=ax.get_yaxis_transform(), 
                       fontsize=8, alpha=0.7, color=color)
            
            ax.set_xlabel('Student Sequence')
            ax.set_ylabel('Grade')
            ax.set_title(f'Grade Distribution for {subject_desc}')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 100)
            
            add_chart(fig, "🎯 Grade Distribution Scatter Plot - Shows individual student grades with performance boundaries")

            # 3. Grade Distribution Histogram
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Create histogram with color coding based on grade ranges
            bins = range(0, 101, 5)  # 5-point intervals
            n, bins, patches = ax.hist(progress_data['Grade_num'], bins=bins, 
                                     edgecolor='black', alpha=0.7)
            
            # Color histogram bars based on grade ranges
            for i, patch in enumerate(patches):
                bin_center = (bins[i] + bins[i+1]) / 2
                patch.set_facecolor(get_grade_range_color(bin_center))
            
            ax.set_xlabel('Grade Range')
            ax.set_ylabel('Number of Students')
            ax.set_title('Grade Distribution Overview')
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#28a745', label='Stable High (95+)'),
                Patch(facecolor='#17a2b8', label='Improving (85-94)'),
                Patch(facecolor='#ffc107', label='Consistent (75-84)'),
                Patch(facecolor='#dc3545', label='Needs Attention (<75)')
            ]
            ax.legend(handles=legend_elements, loc='upper left', fontsize=8)
            
            add_chart(fig, "📈 Grade Distribution Overview - Histogram showing the distribution of grades across all students")

        elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_advanced_pdf_download_button(df, faculty_name, semester_filter=None, subject_filter=None, is_new_curriculum=False):
    """Add a download button for advanced PDF export with charts"""
    if df is None or df.empty:
        st.warning("No data available to export to Advanced PDF.")
        return
    
    try:
        pdf_data = create_advanced_grade_pdf(df, faculty_name, semester_filter, subject_filter, is_new_curriculum)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "New" if is_new_curriculum else "Old"
        filename = f"Student_Progress_Report_{curriculum_type}_{timestamp}.pdf"
        
        st.download_button(
            label="📊 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report with tables and charts",
            key="download_pdf_tab2" 
        )
        
    except Exception as e:
        st.error(f"Error generating advanced PDF: {str(e)}")
        st.info("Please ensure all required data and charts are properly loaded before generating the PDF.")
        


current_faculty = st.session_state.get('user_data', {}).get('Name', '')

# Initialize session state variables for persistence
if 'grades_data_cache' not in st.session_state:
    st.session_state.grades_data_cache = {}

if 'last_loaded_filters' not in st.session_state:
    st.session_state.last_loaded_filters = {
        'semester': None,
        'subject': None,
        'curriculum': None
    }

if 'grades_df' not in st.session_state:
    st.session_state.grades_df = pd.DataFrame()

if 'current_faculty' not in st.session_state:
    st.session_state.current_faculty = ''

def display_student_progress(is_new_curriculum, df, semester_filter = None, subject_filter = None):
    """Display student progress tracking with line/scatter charts"""
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
    
    st.session_state.filtered_grades_df = filtered_df
    
    year_map = {
        1: "1st Year", 2: "2nd Year", 3: "3rd Year",
        4: "4th Year", 5: "5th Year",
    }
    
    for (semester, school_year, subject_code, subject_desc, NewCourse, SubjectYearLevel, section), group in filtered_df.groupby(
        ['semester', 'schoolYear', 'subjectCode', 'subjectDescription','NewCourse', 'SubjectYearLevel', 'section']
    ):
        # Create unique key for this group for session state
        group_key = f"{semester}_{school_year}_{subject_code}_{NewCourse}_{SubjectYearLevel}_{section}"
        
        # Check if this group should be expanded (default True for first load)
        expanded_key = f"expander_{group_key}"
        if expanded_key not in st.session_state:
            st.session_state[expanded_key] = True
            
        if is_new_curriculum:
            extra_info = f" | &nbsp;&nbsp; {NewCourse} &nbsp;&nbsp; - {year_map.get(SubjectYearLevel, '')}"
        else:
            extra_info = ""

        with st.expander(
            f"{semester} - {school_year} &nbsp;&nbsp; | &nbsp;&nbsp; {subject_code}{section} "
            f"&nbsp;&nbsp; - &nbsp;&nbsp; {subject_desc}{extra_info}",
            expanded=st.session_state[expanded_key]
        ):
            
            table_data = group[['StudentID', 'studentName', 'NewCourse', 'YearLevel', 'grade', 'Course']].copy()
            table_data.columns = ['Student ID', 'Student Name', 'NewCourse', 'Year Level', 'Grade', 'Course']
            
            table_data['Grade_num'] = pd.to_numeric(table_data['Grade'], errors='coerce')
            table_data['Student ID'] = table_data['Student ID'].astype(str)
            
            # Store original grade data in session state for potential export
            grade_export_key = f"grades_export_{group_key}"
            st.session_state[grade_export_key] = table_data.copy()
            
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
                
            def grade_status(grade):
                if pd.isna(grade) or grade == 0:
                    return "Not Set"
                else:
                    return f"{grade:.1f}"

            table_data['Grade'] = table_data['Grade_num'].apply(grade_status)
            table_data['Grade (GPA)'] = table_data['Grade']
            
            # Add performance indicators
            def performance_indicator(grade):
                if pd.isna(grade) or grade == 0:
                    return "⚪ Not Set"
                elif grade >= 95:
                    return "🥇 Stable High"
                elif grade >= 85:
                    return "🥈 Improving"
                elif grade >= 75:
                    return "🥉 Consistent"
                else:
                    return "📚 Needs Attention"
            
            table_data['Performance'] = table_data['Grade_num'].apply(performance_indicator)
            table_data['Overall Trend'] = table_data['Performance']
            
            if is_new_curriculum:
                display_df = table_data[['Student ID', 'Student Name', 'Grade (GPA)', 'Overall Trend']]
            else:
                display_df = table_data[['Student ID', 'Student Name', f"{course_column}", f"{year_column}", 'Grade (GPA)', 'Overall Trend']]
            
            def color_performance(val):
                if "Stable High" in val:
                    return 'color: #28a745; font-weight: bold'
                elif "Improving" in val:
                    return 'color: #17a2b8; font-weight: bold'
                elif "Consistent" in val:
                    return 'color: #ffc107; font-weight: bold'
                elif "Needs Attention" in val:
                    return 'color: #dc3545; font-weight: bold'
                else:
                    return 'color: gray'
                    
            styled_df = (display_df.style.applymap(color_performance, subset=['Overall Trend']))
            
            # Enhanced statistics with performance categories
            valid_grades = table_data["Grade_num"][
                (table_data["Grade_num"].notna()) & (table_data["Grade_num"] > 0)
            ]
            
            # Performance breakdown
            excellent_count = len(table_data[table_data['Grade_num'] >= 95])
            very_good_count = len(table_data[(table_data['Grade_num'] >= 85) & (table_data['Grade_num'] < 95)])
            good_count = len(table_data[(table_data['Grade_num'] >= 75) & (table_data['Grade_num'] < 85)])
            needs_improvement_count = len(table_data[(table_data['Grade_num'] > 0) & (table_data['Grade_num'] < 75)])
            not_set_count = len(table_data[(table_data['Grade_num'].isna()) | (table_data['Grade_num'] == 0)])

            # Display metrics in tabs for better organization
            metric_tab1, metric_tab2 = st.tabs(["📊 Basic Statistics", "🎯 Performance Breakdown"])
            
            with metric_tab1:
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Students", len(table_data))
                with col2:
                    avg_val = f"{valid_grades.mean():.1f}" if not valid_grades.empty else "Not Set"
                    st.metric("Class Average", avg_val)
                with col3:
                    median_val = f"{valid_grades.median():.1f}" if not valid_grades.empty else "Not Set"
                    st.metric("Class Median", median_val)
                with col4:
                    max_val = f"{valid_grades.max():.0f}" if not valid_grades.empty else "Not Set"
                    st.metric("Highest Grade", max_val)
                with col5:
                    min_val = f"{valid_grades.min():.0f}" if not valid_grades.empty else "Not Set"
                    st.metric("Lowest Grade", min_val)
            
            with metric_tab2:
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    excellent_rate = f"{(excellent_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
                    st.metric("🥇 Stable High (95+)", excellent_count, delta=excellent_rate)
                with col2:
                    very_good_rate = f"{(very_good_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
                    st.metric("🥈 Improving (85-94)", very_good_count, delta=very_good_rate)
                with col3:
                    good_rate = f"{(good_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
                    st.metric("🥉 Consistent (75-84)", good_count, delta=good_rate)
                with col4:
                    needs_improvement_rate = f"{(needs_improvement_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
                    st.metric("📚 Needs Attention (<75)", needs_improvement_count, delta=needs_improvement_rate)
                with col5:
                    not_set_rate = f"{(not_set_count/len(table_data)*100):.1f}%" if len(table_data) > 0 else "0%"
                    st.metric("⚪ Not Set", not_set_count, delta=not_set_rate)

            st.subheader("📋 Student Progress Table")
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Show progress visualizations only if enabled
            display_progress_charts(table_data, subject_code, subject_desc,section)
    
    st.subheader("📄 Export Report")
    add_advanced_pdf_download_button(df, current_faculty, semester_filter, subject_filter, is_new_curriculum)

def display_progress_charts(table_data, subject_code, subject_desc,section):
    """Display progress tracking charts"""
    
    # Prepare data for progress tracking
    progress_data = table_data.copy()
    progress_data = progress_data[progress_data['Grade_num'].notna() & (progress_data['Grade_num'] > 0)]
    
    if progress_data.empty:
        st.info("No valid grade data available for progress visualization.")
        return
    
    # Create student index for x-axis (simulating time progression)
    progress_data = progress_data.reset_index(drop=True)
    progress_data['Student_Index'] = progress_data.index + 1
    
    # Add grade ranges for color coding
    def get_grade_range(grade):
        if grade >= 95:
            return "Stable High (95-100)"
        elif grade >= 85:
            return "Improving (85-94)"
        elif grade >= 75:
            return "Consistent (75-84)"
        else:
            return "Needs Attention (<75)"
    
    progress_data['Grade_Range'] = progress_data['Grade_num'].apply(get_grade_range)
    
# Create charts based on selection
    st.subheader("**📊 Grade Progression Line Chart**")
    
    line_chart = alt.Chart(progress_data).mark_line(
        point=True,
        strokeWidth=2
    ).encode(
        x=alt.X('Student_Index:O', title='Student Sequence', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Grade_num:Q', title='Grade', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color(
            'Grade_Range:N',
            title="Performance Level",
            scale=alt.Scale(
                domain=["Stable High (95-100)", "Improving (85-94)", "Consistent (75-84)", "Needs Attention (<75)"],
                range=["#28a745", "#17a2b8", "#ffc107", "#dc3545"]
            )
        ),
        tooltip=['Student Name:N', 'Grade_num:Q', 'Course:N', 'Grade_Range:N']
    ).properties(
        height=400,
        title=f"Grade Progression for {subject_desc}"
    )
    
    # Add average line
    avg_grade = progress_data['Grade_num'].mean()
    avg_line = alt.Chart(pd.DataFrame({'y': [avg_grade]})).mark_rule(
        color='orange',
        strokeWidth=2,
        strokeDash=[5, 5]
    ).encode(
        y='y:Q',
        size=alt.value(2)
    )
    
    combined_line = line_chart + avg_line
    st.altair_chart(combined_line, use_container_width=True)

    st.subheader("**🎯 Grade Distribution Scatter Plot**")
    
    base_data = progress_data
    highlight_data = pd.DataFrame()
    
    # Base scatter plot
    scatter_base = alt.Chart(base_data).mark_circle(
        size=100,
        opacity=0.7
    ).encode(
        x=alt.X('Student_Index:O', title='Student Sequence'),
        y=alt.Y('Grade_num:Q', title='Grade', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color(
            'Grade_Range:N',
            title="Performance Level",
            scale=alt.Scale(
                domain=["Stable High (95-100)", "Improving (85-94)", "Consistent (75-84)", "Needs Attention (<75)"],
                range=["#28a745", "#17a2b8", "#ffc107", "#dc3545"]
            )
        ),
        tooltip=['Student Name:N', 'Grade_num:Q', 'Course:N', 'Grade_Range:N']
    )
    
    # Highlighted students
    scatter_highlight = alt.Chart(highlight_data).mark_circle(
        size=200,
        stroke='black',
        strokeWidth=3
    ).encode(
        x=alt.X('Student_Index:O'),
        y=alt.Y('Grade_num:Q'),
        color=alt.Color('Grade_Range:N'),
        tooltip=['Student Name:N', 'Grade_num:Q', 'Course:N', 'Grade_Range:N']
    )
    
    # Add reference lines
    ref_lines = alt.Chart(pd.DataFrame({
        'grade': [75, 85, 95],
        'label': ['Consistent (75)', 'Improving (85)', 'Stable High (95)']
    })).mark_rule(
        strokeDash=[3, 3],
        opacity=0.5
    ).encode(
        y='grade:Q',
        color=alt.value('gray')
    )
    
    if not highlight_data.empty:
        combined_scatter = scatter_base + scatter_highlight + ref_lines
    else:
        combined_scatter = scatter_base + ref_lines
        
    combined_scatter = combined_scatter.properties(
        height=400,
        title=f"Grade Distribution for {subject_desc}"
    )
    
    st.altair_chart(combined_scatter, use_container_width=True)
        
    
    # Grade distribution histogram
    st.subheader("**📈 Grade Distribution Overview**")
    
    hist_chart = alt.Chart(progress_data).mark_bar(
        opacity=0.7
    ).encode(
        x=alt.X('Grade_num:Q', bin=alt.Bin(maxbins=20), title='Grade Range'),
        y=alt.Y('count():Q', title='Number of Students'),
        color=alt.Color(
            'Grade_Range:N',
            scale=alt.Scale(
                domain=["Stable High (95-100)", "Improving (85-94)", "Consistent (75-84)", "Needs Attention (<75)"],
                range=["#28a745", "#17a2b8", "#ffc107", "#dc3545"]
            )
        ),
        tooltip=['count():Q']
    ).properties(
        height=300,
        title="Grade Distribution Histogram"
    )
    
    st.altair_chart(hist_chart, use_container_width=True)

def show_faculty_tab2_info(new_curriculum):
    """Main function for student progress tracking"""
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    
    if not current_faculty:
        st.error("No faculty information found. Please ensure you are logged in properly.")
        return
    
    st.markdown("Track and visualize student academic progress across semesters and subjects.")
    
    try:
        # Load data
        with st.spinner("Loading semester and subject data..."):
            semesters = get_semesters_list(new_curriculum)
            subjects = get_subjects_by_teacher(current_faculty, new_curriculum)
        if not semesters:
            st.warning("No semesters found.")
            return
            
        if not subjects:
            st.warning(f"No subjects found for {current_faculty}.")
            return
        
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters]
            selected_semester_display = st.selectbox(
                "📅 Select Semester",
                semester_options,
                key="tab2_semester",
                help="Choose a semester to track student progress"
            )
        
        with col2:
            subject_options = [f"{subj['_id']} - {subj['Description']}" for subj in subjects]
            selected_subject_display = st.selectbox(
                "📚 Select Subject",
                subject_options,
                key="tab2_subject", 
                help="Choose a subject to track student progress"
            )
            
        
        # Find selected IDs
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
                
        selected_section_label = None
        selected_section_value = None
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
                        key="tab2_subject_section",
                        help="Choose a section to track student progress"
                    )

                    # Get the actual section value back
                    selected_section_value = next(
                        (opt["value"] for opt in section_options if opt["label"] == selected_section_label),
                        None
                    )

                else:
                    selected_section_value = None

        load_button = st.button(
            "📊 Load Progress Data",
            type="secondary",
            key="tab2_load_button",
            use_container_width=False,
            help="Click to load student progress data for the selected filters"
        )
        
        if load_button:
            with st.spinner("Loading student progress data..."):
                try:
                    # Store current filters in session state
                    st.session_state.last_loaded_filters = {
                        'semester': selected_semester_display,
                        'subject': selected_subject_display,
                        'curriculum': new_curriculum
                    }
                    
                    # Load grades based on curriculum
                    if new_curriculum:
                        results = get_new_student_grades_by_subject_and_semester(
                            current_faculty=current_faculty,
                            semester_id=selected_semester_id,
                            subject_code=selected_subject_code
                        )
                        results = [res for res in results if res["section"] == selected_section_value]
                        
                    else:
                        results = get_student_grades_by_subject_and_semester(
                            current_faculty=current_faculty,
                            semester_id=selected_semester_id,
                            subject_code=selected_subject_code
                        )
                    
                    if results:
                        df = result_records_to_dataframe(results)
                        
                        st.session_state.grades_df = df
                        st.session_state.current_faculty = current_faculty
                        
                        st.success(f"✅ Successfully loaded progress data for {len(results)} students under {current_faculty} - {selected_subject_display} - {selected_section_label}")
                        
                        display_student_progress(
                            new_curriculum, 
                            df, 
                            selected_semester_display, 
                            selected_subject_display
                        )
                        
                    else:
                        st.warning(f"⚠️ No student progress data found for {current_faculty} with the selected filters.")
                        st.info("💡 Try adjusting your semester or subject filters.")
                        
                except Exception as e:
                    st.error(f"❌ An error occurred while loading progress data: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ An error occurred while initializing the progress tracker: {str(e)}")

# Export functions
__all__ = ['create_advanced_grade_pdf', 'add_advanced_pdf_download_button', 'display_student_progress_with_advanced_pdf']