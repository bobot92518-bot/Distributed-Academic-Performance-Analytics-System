import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import numpy as np
import time
import os
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

def create_teacher_evaluation_pdf(summary_df, sel_teacher, subj_break_df, pass_count, fail_count, total_count, pass_rate, df_t, subjects_df):
    """Generate PDF report for teacher evaluation"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)

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
    elements.append(Paragraph("👨‍🏫 Teacher Evaluation Report", title_style))
    elements.append(Spacer(1, 12))

    # Report Information
    report_info = f"""
    <b>Generated on:</b> {pd.Timestamp.now().strftime("%B %d, %Y at %I:%M %p")}<br/>
    <b>Teacher:</b> {sel_teacher}<br/>
    <b>Total Students:</b> {total_count}
    """
    elements.append(Paragraph(report_info, info_style))
    elements.append(Spacer(1, 20))

    # Summary Table
    elements.append(Paragraph("Summary Table", header_style))
    elements.append(Spacer(1, 6))

    summary_table_data = [summary_df.columns.tolist()] + summary_df.values.tolist()
    summary_table = Table(summary_table_data, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Detailed Pass/Fail for selected teacher
    elements.append(Paragraph(f"Detailed Pass/Fail for {sel_teacher}", header_style))
    elements.append(Spacer(1, 6))

    # Overall Metrics
    elements.append(Paragraph("Overall Performance Metrics", header_style))
    elements.append(Spacer(1, 6))

    metrics_data = [
        ["Metric", "Value"],
        ["Pass Count", str(pass_count)],
        ["Fail Count", str(fail_count)],
        ["Total Students", str(total_count)],
        ["Pass Rate (%)", f"{pass_rate}%"]
    ]
    metrics_table = Table(metrics_data, repeatRows=1)
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 20))

    # Grade Distribution Chart
    try:
        vc = df_t["Grade"].round(0).astype(int).value_counts().sort_index().reset_index()
        vc.columns = ["Grade", "Count"]
        fig_dist = px.bar(vc, x="Grade", y="Count", title="Grade Distribution (Rounded)")
        fig_dist.update_layout(xaxis_title="Grade", yaxis_title="Students")
        image_bytes = pio.to_image(fig_dist, format='png', width=500, height=300)
        img_buffer = BytesIO(image_bytes)
        img_dist = Image(img_buffer)
        elements.append(img_dist)
        elements.append(Spacer(1, 20))
    except Exception as e:
        pass

    # Pass/Fail Counts Chart
    try:
        pf = df_t["Status"].value_counts().reindex(["Pass", "Fail"], fill_value=0).reset_index()
        pf.columns = ["Status", "Count"]
        fig_pf = px.bar(pf, x="Status", y="Count", title="Pass/Fail Counts")
        fig_pf.update_layout(xaxis_title="Status", yaxis_title="Students")
        image_bytes_pf = pio.to_image(fig_pf, format='png', width=500, height=300)
        img_buffer_pf = BytesIO(image_bytes_pf)
        img_pf = Image(img_buffer_pf)
        elements.append(img_pf)
        elements.append(Spacer(1, 20))
    except Exception as e:
        pass

    # Per-Subject Breakdown
    elements.append(Paragraph("Per-Subject Breakdown", header_style))
    elements.append(Spacer(1, 6))

    subj_table_data = [subj_break_df.columns.tolist()] + subj_break_df.values.tolist()
    subj_table = Table(subj_table_data, repeatRows=1)
    subj_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(subj_table)
    elements.append(Spacer(1, 20))

    # Pass Rate by Subject Chart
    try:
        plot_t = subj_break_df.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(15)
        fig_t = px.bar(plot_t, x="SubjectCode", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title=f"Pass Rate by Subject - {sel_teacher}")
        fig_t.update_layout(xaxis_title="Subject", yaxis_title="Pass Rate (%)")
        image_bytes_t = pio.to_image(fig_t, format='png', width=500, height=300)
        img_buffer_t = BytesIO(image_bytes_t)
        img_t = Image(img_buffer_t)
        elements.append(img_t)
        elements.append(Spacer(1, 20))
    except Exception as e:
        pass

    # Overall Pass Rate by Teacher Chart
    elements.append(Paragraph("Overall Pass Rate by Teacher (Top 20 by Volume)", header_style))
    elements.append(Spacer(1, 6))

    try:
        plot_df = summary_df.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(20)
        fig = px.bar(plot_df, x="Teacher", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title="Pass Rate by Teacher (Top 20 by Volume)")
        fig.update_layout(xaxis_title="Teacher", yaxis_title="Pass Rate (%)")
        image_bytes_overall = pio.to_image(fig, format='png', width=500, height=400)
        img_buffer_overall = BytesIO(image_bytes_overall)
        img_overall = Image(img_buffer_overall)
        elements.append(img_overall)
        elements.append(Spacer(1, 20))
    except Exception as e:
        pass

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def add_teacher_evaluation_pdf_download_button(summary_df, sel_teacher, subj_break_df, pass_count, fail_count, total_count, pass_rate, df_t, subjects_df):
    """Add a download button for teacher evaluation PDF export"""

    if summary_df is None or summary_df.empty or subj_break_df is None or subj_break_df.empty:
        st.warning("No teacher evaluation data available to export to PDF.")
        return

    try:
        pdf_data = create_teacher_evaluation_pdf(summary_df, sel_teacher, subj_break_df, pass_count, fail_count, total_count, pass_rate, df_t, subjects_df)

        # Generate filename
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Teacher_Evaluation_{sel_teacher.replace(' ', '_')}_{timestamp}.pdf"

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download a comprehensive PDF report of the teacher evaluation",
            key="download_pdf_tab5"
        )

    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def show_registrar_new_tab5_info(data, students_df, semesters_df, teachers_df, grades_df):
    subjects_df = data['subjects']

    st.subheader("👨‍🏫 Teacher Evaluation (Pass/Fail per Teacher)")
    # Anchor to retain scroll position on this tab after re-runs
    st.markdown('<div id="teacher-eval-anchor"></div>', unsafe_allow_html=True)

    # Expand per-grade rows to include teacher association
    def _expand_teacher_rows(grade_row):
        rows = []
        grades_list = grade_row.get("Grades", [])
        subjects_list = grade_row.get("SubjectCodes", [])
        teachers_list = grade_row.get("Teachers", [])
        grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
        subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
        teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
        n = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
        for i in range(n):
            rows.append({
                "StudentID": grade_row.get("StudentID"),
                "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
                "Grade": grades_list[i] if i < len(grades_list) else None,
                "TeacherRaw": teachers_list[i] if i < len(teachers_list) else None,
            })
        return rows

    # Resolve teacher names whether TeacherRaw holds id or name
    teacher_id_to_name = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
    known_teacher_names = set(teachers_df["Teacher"].dropna().astype(str).tolist()) if not teachers_df.empty else set()

    def resolve_teacher_name(value):
        if pd.isna(value):
            return "Unknown"
        if value in teacher_id_to_name:
            return teacher_id_to_name[value]
        s = str(value)
        return s

    # Build expanded dataframe
    exp_rows = []
    for _, gr in grades_df.iterrows():
        exp_rows.extend(_expand_teacher_rows(gr))

    if not exp_rows:
        st.info("No grade records available.")
    else:
        df = pd.DataFrame(exp_rows)
        df["Teacher"] = df["TeacherRaw"].apply(resolve_teacher_name)
        df = df[pd.to_numeric(df["Grade"], errors="coerce").notna()].copy()
        df["Grade"] = pd.to_numeric(df["Grade"], errors="coerce")
        df["Status"] = df["Grade"].apply(lambda g: "Pass" if g >= 75 else "Fail")

        # Aggregate counts
        agg = df.groupby("Teacher")["Status"].value_counts().unstack(fill_value=0)
        if "Pass" not in agg.columns:
            agg["Pass"] = 0
        if "Fail" not in agg.columns:
            agg["Fail"] = 0
        agg["Total"] = agg["Pass"] + agg["Fail"]
        agg["Pass Rate (%)"] = (agg["Pass"] / agg["Total"].replace(0, pd.NA) * 100).round(1)
        summary = agg.reset_index().sort_values(["Pass Rate (%)", "Total", "Pass"], ascending=[False, False, False])

        st.subheader("Summary Table")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        # Ensure we remain scrolled to this section after interactions
        components.html('<script>location.hash = "#teacher-eval-anchor";</script>', height=0)

        # Filter by teacher for detailed pass/fail analysis (no "All")
        teacher_filter_options = summary["Teacher"].astype(str).tolist()
        sel_teacher_for_detail = st.selectbox("Filter by Teacher for detailed analysis", teacher_filter_options, key="teacher_eval_filter")

        if sel_teacher_for_detail:
            df_t = df[df["Teacher"].astype(str) == sel_teacher_for_detail]
            if df_t.empty:
                st.info("No records for the selected teacher.")
            else:
                st.subheader(f"Detailed Pass/Fail for {sel_teacher_for_detail}")

                # Overall metrics for this teacher
                pass_count = int((df_t["Status"] == "Pass").sum())
                fail_count = int((df_t["Status"] == "Fail").sum())
                total_count = pass_count + fail_count
                pass_rate = round(pass_count / total_count * 100, 1) if total_count > 0 else 0.0

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Pass", pass_count)
                with c2:
                    st.metric("Fail", fail_count)
                with c3:
                    st.metric("Total", total_count)
                with c4:
                    st.metric("Pass Rate (%)", pass_rate)

                # Grade distribution (bar chart)
                vc = df_t["Grade"].round(0).astype(int).value_counts().sort_index().reset_index()
                vc.columns = ["Grade", "Count"]
                fig_dist = px.bar(vc, x="Grade", y="Count", title="Grade Distribution (Rounded)")
                fig_dist.update_layout(xaxis_title="Grade", yaxis_title="Students")
                st.plotly_chart(fig_dist, use_container_width=True)

                # Pass/Fail counts (bar chart)
                pf = df_t["Status"].value_counts().reindex(["Pass", "Fail"], fill_value=0).reset_index()
                pf.columns = ["Status", "Count"]
                fig_pf = px.bar(pf, x="Status", y="Count", title="Pass/Fail Counts")
                fig_pf.update_layout(xaxis_title="Status", yaxis_title="Students")
                st.plotly_chart(fig_pf, use_container_width=True)

                # Per subject breakdown for this teacher
                subj_break = df_t.groupby("SubjectCode")["Status"].value_counts().unstack(fill_value=0)
                if "Pass" not in subj_break.columns:
                    subj_break["Pass"] = 0
                if "Fail" not in subj_break.columns:
                    subj_break["Fail"] = 0
                subj_break["Total"] = subj_break["Pass"] + subj_break["Fail"]
                subj_break["Pass Rate (%)"] = (subj_break["Pass"] / subj_break["Total"].replace(0, pd.NA) * 100).round(1)
                subj_break = subj_break.reset_index().sort_values(["Pass Rate (%)", "Total", "Pass"], ascending=[False, False, False])

                st.markdown("### Per-Subject Breakdown")
                st.dataframe(subj_break, use_container_width=True, hide_index=True)

                # Chart for this teacher's per-subject pass rate (top 15 by volume)
                plot_t = subj_break.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(15)
                fig_t = px.bar(plot_t, x="SubjectCode", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title=f"Pass Rate by Subject - {sel_teacher_for_detail}")
                fig_t.update_layout(xaxis_title="Subject", yaxis_title="Pass Rate (%)")
                st.plotly_chart(fig_t, use_container_width=True)

        # Bar chart
        plot_df = summary.sort_values(["Total", "Pass Rate (%)"], ascending=[False, False]).head(20)
        fig = px.bar(plot_df, x="Teacher", y="Pass Rate (%)", color="Pass", hover_data=["Fail", "Total"], title="Pass Rate by Teacher (Top 20 by Volume)")
        fig.update_layout(xaxis_title="Teacher", yaxis_title="Pass Rate (%)")
        st.plotly_chart(fig, use_container_width=True)

        # PDF Export at the bottom
        if sel_teacher_for_detail:
            st.subheader("📄 Export Report")
            add_teacher_evaluation_pdf_download_button(summary, sel_teacher_for_detail, subj_break, pass_count, fail_count, total_count, pass_rate, df_t, subjects_df)
        