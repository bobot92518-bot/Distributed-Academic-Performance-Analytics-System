import streamlit as st
import pandas as pd
from dbconnect import * 
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io
import matplotlib.pyplot as plt

def generate_student_grades_report_pdf(student_name, student_id, df_grades, avg_grades_per_sem):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph(f"📊 Student Grade Report", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Name: {student_name}", styles['Normal']))
    elements.append(Paragraph(f"Student ID: {student_id}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # ✅ Overall General Average (all semesters)
    overall_avg = df_grades["Grade"].mean() if not df_grades["Grade"].isna().all() else None
    overall_avg_display = f"{overall_avg:.2f}" if overall_avg is not None else "N/A"
    elements.append(Paragraph(f"<b>🏆 Overall General Average: {overall_avg_display}</b>", styles['Heading2']))
    elements.append(Spacer(1, 12))

    # Add per semester grades
    semester_order = {"FirstSem": 1, "SecondSem": 2, "Summer": 3}
    df_grades["SemesterOrder"] = df_grades["Semester"].map(lambda x: semester_order.get(x, 99))
    df_grades.sort_values(by=["SchoolYear", "SemesterOrder", "Subject Code"], inplace=True)

    for (semester, school_year), group in df_grades.groupby(["Semester", "SchoolYear"], sort=False):
        gpa = group["Grade"].mean() if not group["Grade"].isna().all() else None
        gpa_display = f"{gpa:.2f}" if gpa is not None else "N/A"
        elements.append(Paragraph(f"<b>{semester} {school_year} (GPA: {gpa_display})</b>", styles['Heading3']))

        # Table data
        table_data = [["Subject Code", "Description", "Units", "Teacher", "Grade"]]
        for _, row in group.iterrows():
            table_data.append([
                row["Subject Code"],
                row["Subject Description"],
                row["Units"],
                row["Teacher"],
                row["Grade"] if pd.notna(row["Grade"]) else "N/A"
            ])
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # Add chart
    plt.figure(figsize=(6, 3))
    plt.plot(avg_grades_per_sem["SemesterLabel"], avg_grades_per_sem["Grade"], marker="o")
    plt.title("Average Grade per Semester")
    plt.xlabel("Semester")
    plt.ylabel("Average Grade")
    plt.xticks(rotation=45)
    plt.tight_layout()

    chart_buf = io.BytesIO()
    plt.savefig(chart_buf, format="PNG")
    plt.close()
    chart_buf.seek(0)

    elements.append(Image(chart_buf, width=400, height=200))
    doc.build(elements)
    buffer.seek(0)

    return buffer