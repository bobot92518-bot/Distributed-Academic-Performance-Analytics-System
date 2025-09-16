import streamlit as st
import pandas as pd
import os
import io
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib.pyplot as plt
from reportlab.lib.units import inch
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT


# ------------------ Paths to Pickle Files ------------------ #
student_cache = "pkl/students.pkl"
new_student_cache = "pkl/new_students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"

# ------------------ Helper Functions (minimal) ------------------ #
def get_student_info(student_name):
    if not os.path.exists(student_cache):
        st.error("Student cache file not found.")
        st.stop()
    students = pd.read_pickle(student_cache)
    students_df = pd.DataFrame(students) if isinstance(students, list) else students
    match = students_df[students_df["Name"] == student_name]
    return match.iloc[0].to_dict() if not match.empty else None

def get_student_grades(student_id):
    if not os.path.exists(grades_cache) or not os.path.exists(semesters_cache):
        st.error("Grades or semesters cache file not found.")
        st.stop()
    grades = pd.read_pickle(grades_cache)
    semesters = pd.read_pickle(semesters_cache)
    grades_df = pd.DataFrame(grades) if isinstance(grades, list) else grades
    sem_df = pd.DataFrame(semesters) if isinstance(semesters, list) else semesters
    student_grades = grades_df[grades_df["StudentID"] == student_id].copy()
    if not student_grades.empty:
        student_grades["Semester"] = ""
        student_grades["SchoolYear"] = ""
        for idx, row in student_grades.iterrows():
            sem_id = row.get("SemesterID")
            match = sem_df[sem_df["_id"] == sem_id]
            if not match.empty:
                student_grades.at[idx, "Semester"] = match.iloc[0].get("Semester", "")
                student_grades.at[idx, "SchoolYear"] = match.iloc[0].get("SchoolYear", "")
    return student_grades.to_dict(orient="records")

def get_subjects():
    if not os.path.exists(subjects_cache):
        st.error("Subjects cache file not found.")
        st.stop()
    subjects = pd.read_pickle(subjects_cache)
    subjects_df = pd.DataFrame(subjects) if isinstance(subjects, list) else subjects
    return subjects_df[["_id", "Description"]].drop_duplicates()

# ------------------ Old Dashboard ------------------ #
def show_student_dashboard_old():
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()
    user_data = st.session_state.get("user_data", {})
    student_name = user_data.get("Name", "")
    if not student_name:
        st.error("Student name not found in session data.")
        st.stop()
    student = get_student_info(student_name)
    if not student:
        st.error("Student record not found.")
        st.stop()
    grades = get_student_grades(student["_id"])
    if grades:
        st.markdown("### 🧭 Self-Assessment & Insights")
        tab1, tab2, tab3, tab4 = st.tabs([
            "Performance Trend Over Time",
            "Subject Difficulty Ratings",
            "Comparison with Class Average",
            "Passed vs Failed Summary"
        ])
        with tab1:
            col1, col2 = st.columns(2)
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")
            transcript_data = {}
            semester_avgs = []
            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"]) 
                subjects_df = pd.read_pickle(subjects_cache)
                subjects_df = pd.DataFrame(subjects_df) if isinstance(subjects_df, list) else subjects_df
                subjects_df = subjects_df[["_id", "Description", "Units"]].drop_duplicates()
                for (sy, sem), sem_df in grouped:
                    if "SubjectCodes" in sem_df and sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                        expanded_df = pd.DataFrame({
                            "SubjectCodes": sem_df["SubjectCodes"].explode().values,
                            "Teacher": sem_df["Teachers"].explode().values,
                            "Grade": sem_df["Grades"].explode().values
                        })
                    else:
                        expanded_df = sem_df[["SubjectCodes", "Teachers", "Grades"]].rename(
                            columns={"Teachers": "Teacher", "Grades": "Grade"}
                        )
                    expanded_df = expanded_df.merge(
                        subjects_df.rename(columns={"_id": "SubjectCodes"}),
                        on="SubjectCodes",
                        how="left"
                    )
                    if "Description" not in expanded_df.columns:
                        expanded_df["Description"] = "N/A"
                    if "Units" not in expanded_df.columns:
                        expanded_df["Units"] = "N/A"
                    expanded_df = expanded_df[["SubjectCodes", "Units", "Description", "Teacher", "Grade"]]
                    transcript_data[f"{sy} - Semester {sem}"] = expanded_df
                    valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                    if not valid_grades.empty:
                        avg = valid_grades.mean()
                        semester_avgs.append((f"{sy} - Sem {sem}", avg))
            with col1:
                if semester_avgs:
                    total_avg = sum(avg for _, avg in semester_avgs) / len(semester_avgs)
                    st.metric("Total Average", f"{total_avg:.2f}")
                else:
                    total_avg = None
                    st.metric("Total Average", "N/A")
            with col2:
                st.metric("Course", student.get("Course", "N/A"))
            for sem_title, expanded_df in transcript_data.items():
                st.subheader(sem_title)
                st.dataframe(expanded_df, use_container_width=True)
                valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                if not valid_grades.empty:
                    avg = valid_grades.mean()
                    st.write(f"**Semester Average: {avg:.2f}**")
                else:
                    st.write("**Semester Average: N/A**")
                if "Units" in expanded_df.columns:
                    total_units = pd.to_numeric(expanded_df["Units"], errors="coerce").fillna(0).sum()
                    st.write(f"**Total Units: {int(total_units)}**")
                else:
                    st.write("**Total Units: N/A**")
                st.markdown("---")
            if semester_avgs:
                labels, values = zip(*semester_avgs)
                labels = list(labels)
                values = list(values)
                if total_avg is not None:
                    labels.append("Final Average")
                    values.append(total_avg)
                plt.figure(figsize=(12, 5))
                plt.plot(labels, values, marker="o", linestyle="-", label="Semester Average + Final")
                plt.ylim(1, 100)
                plt.xlabel("Semester (SchoolYear - Sem)")
                plt.ylabel("Average Grade")
                plt.title("Average Grades per Semester")
                plt.grid(True)
                plt.xticks(rotation=45, ha="right")
                plt.legend()
                plt.tight_layout()
                st.pyplot(plt)
            if transcript_data:
                if st.button("📄 Generate Report"):
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    elements = []
                    styles = getSampleStyleSheet()
                    elements.append(Paragraph("Academic Transcript Report", styles["Title"]))
                    elements.append(Spacer(1, 12))
                    full_name = f"{student.get('Name', '')}"
                    elements.append(Paragraph(f"<b>Student Name:</b> {full_name}", styles["Normal"]))
                    elements.append(Paragraph(f"<b>Course:</b> {student.get('Course', 'N/A')}", styles["Normal"]))
                    if total_avg is not None:
                        elements.append(Paragraph(f"<b>Total Average:</b> {total_avg:.2f}", styles["Normal"]))
                    elements.append(Spacer(1, 12))
                    page_width = A4[0] - doc.leftMargin - doc.rightMargin
                    col_count = 4
                    col_widths = [page_width / col_count] * col_count
                    all_grades = []
                    for sem_title, sem_df in transcript_data.items():
                        elements.append(Paragraph(sem_title, styles["Heading2"]))
                        numeric_grades = pd.to_numeric(sem_df["Grade"], errors="coerce").dropna().tolist()
                        all_grades.extend(numeric_grades)
                        table_data = [sem_df.columns.tolist()] + sem_df.values.tolist()
                        table = Table(table_data, colWidths=col_widths, repeatRows=1)
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 6),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]))
                        elements.append(table)
                        if numeric_grades:
                            avg = sum(numeric_grades) / len(numeric_grades)
                            elements.append(Spacer(1, 6))
                            elements.append(Paragraph(f"<b>Semester Average: {avg:.2f}</b>", styles["Normal"]))
                        else:
                            elements.append(Paragraph("<b>Semester Average: N/A</b>", styles["Normal"]))
                        elements.append(Spacer(1, 12))
                    if all_grades:
                        final_avg = sum(all_grades) / len(all_grades)
                        elements.append(Paragraph(f"<b>Overall Average: {final_avg:.2f}</b>", styles["Heading2"]))
                    else:
                        final_avg = None
                    if semester_avgs:
                        labels, values = zip(*semester_avgs)
                        labels = list(labels)
                        values = list(values)
                        plt.figure(figsize=(8, 4))
                        plt.plot(labels, values, marker="o", linestyle="-", label="Semester Average")
                        for i, (x, y) in enumerate(zip(labels, values)):
                            plt.text(i, y + 1, f"{y:.2f}", ha="center", fontsize=7, color="blue")
                        if final_avg is not None:
                            labels.append("Final Avg")
                            values.append(final_avg)
                            plt.plot(len(labels) - 1, final_avg, marker="o", color="red", markersize=8, label="Final Avg")
                            plt.text(len(labels) - 1, final_avg + 1, f"{final_avg:.2f}", ha="center", fontsize=8, color="red")
                        plt.ylim(1, 100)
                        plt.xlabel("Semester (SchoolYear - Sem)")
                        plt.ylabel("Average Grade")
                        plt.title("Average Grades per Semester")
                        plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
                        plt.grid(True)
                        plt.legend()
                        plt.tight_layout()
                        img_buffer = io.BytesIO()
                        plt.savefig(img_buffer, format="PNG")
                        plt.close()
                        img_buffer.seek(0)
                        reportlab_img = Image(img_buffer, width=400, height=200)
                        elements.append(Spacer(1, 12))
                        elements.append(Paragraph("Performance Trend", styles["Heading2"]))
                        elements.append(reportlab_img)
                    doc.build(elements)
                    buffer.seek(0)
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=buffer,
                        file_name="transcript_report.pdf",
                        mime="application/pdf"
                    )
        with tab2:
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

            if "Semester" in df.columns and "SchoolYear" in df.columns:
                subjects_df = get_subjects()

                # Expand subject codes
                if "SubjectCodes" in df and df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                    expanded_df = pd.DataFrame({
                        "SubjectCodes": df["SubjectCodes"].explode().values,
                        "Teacher": df["Teachers"].explode().values,
                        "Grade": df["Grades"].explode().values,
                        "SchoolYear": df["SchoolYear"].repeat(df["SubjectCodes"].str.len()).values,
                        "Semester": df["Semester"].repeat(df["SubjectCodes"].str.len()).values
                    })
                else:
                    expanded_df = df[["SubjectCodes", "Teachers", "Grades", "SchoolYear", "Semester"]].rename(
                        columns={"Teachers": "Teacher", "Grades": "Grade"}
                    )

                # Merge with subjects
                expanded_df = expanded_df.merge(
                    subjects_df.rename(columns={"_id": "SubjectCodes"}),
                    on="SubjectCodes",
                    how="left"
                )

                if "Description" not in expanded_df.columns:
                    expanded_df["Description"] = "N/A"

                # Convert Grade to numeric
                expanded_df["Grade"] = pd.to_numeric(expanded_df["Grade"], errors="coerce")

                # ✅ Filter only failing grades (<75)
                failed_df = expanded_df[expanded_df["Grade"] < 75]

                # Reorder columns
                columns_to_show = ["SchoolYear", "Semester", "SubjectCodes", "Description", "Teacher", "Grade"]
                failed_df = failed_df[[c for c in columns_to_show if c in failed_df.columns]]

                # ✅ Highlight failing grades in red
                def highlight_failed(val):
                    try:
                        if float(val) < 75:
                            return "color: red; font-weight: bold;"
                    except:
                        pass
                    return ""

                styled_failed = failed_df.style.applymap(highlight_failed, subset=["Grade"])

                st.subheader("❌ Subjects with Failing Grades")
                st.dataframe(styled_failed, use_container_width=True)

                # ---------------- PDF GENERATION ----------------
                def generate_failed_pdf():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    styles = getSampleStyleSheet()
                    elements = []

                    elements.append(Paragraph("Academic Transcript Report", styles["Title"]))
                    elements.append(Spacer(1, 12))

                    full_name = f"{student.get('Name', '')}"
                    elements.append(Paragraph(f"<b>Student Name:</b> {full_name}", styles["Normal"]))
                    elements.append(Paragraph(f"<b>Course:</b> {student.get('Course', 'N/A')}", styles["Normal"]))

                    elements.append(Spacer(1, 12))
                    elements.append(Paragraph("❌ Subjects with Failing Grades", styles["Heading2"]))
                    elements.append(Spacer(1, 12))

                    if failed_df.empty:
                        elements.append(Paragraph("✅ No failing grades found.", styles["Normal"]))
                    else:
                        # Prepare table data
                        data = [list(failed_df.columns)] + failed_df.astype(str).values.tolist()

                        table = Table(data, repeatRows=1, colWidths=[70, 60, 70, 140, 90, 50])
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C00000")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 9),
                            ("FONTSIZE", (0, 1), (-1, -1), 8),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ]))

                        elements.append(table)

                        elements.append(Spacer(1, 12))
                        elements.append(Paragraph(
                            "⚠️ Please consult with your instructor or academic advisor for guidance on retaking these subjects.",
                            styles["Normal"]
                        ))

                    doc.build(elements)
                    buffer.seek(0)
                    return buffer

                # ✅ Download Button
                pdf_buffer = generate_failed_pdf()
                st.download_button(
                    label="📥 Download Failing Grades PDF",
                    data=pdf_buffer,
                    file_name="failing_grades.pdf",
                    mime="application/pdf"
                )
        with tab3:
            st.markdown("""
            **Comparison Legend:**  
            🟢  : Above Average  🔵  : Equal to Average  🔴  : Below Average
            """)

            df = pd.DataFrame(grades)

            # Explode arrays into individual rows
            df_exploded = df.explode(["SubjectCodes", "Grades", "Teachers"]).copy()
            df_exploded = df_exploded.rename(columns={
                "SubjectCodes": "SubjectCode",
                "Grades": "Grade",
                "Teachers": "Teacher"
            })

            # Convert grades to numeric
            df_exploded["Grade"] = pd.to_numeric(df_exploded["Grade"], errors="coerce")
            df_exploded = df_exploded.dropna(subset=["Grade"])

            # Load subjects to get Description
            subjects_df = get_subjects()  # returns _id and Description
            subjects_df.rename(columns={"_id": "SubjectCode"}, inplace=True)

            # Merge Description
            df_exploded = df_exploded.merge(subjects_df, on="SubjectCode", how="left")

            # Compute average grade per subject across all students
            subject_avg = df_exploded.groupby("SubjectCode")["Grade"].mean().reset_index()
            subject_avg.rename(columns={"Grade": "AverageGrade"}, inplace=True)
            subject_avg["AverageGrade"] = subject_avg["AverageGrade"].map(lambda x: f"{x:.2f}")

            # Get logged-in student
            logged_in_refid = str(st.session_state.get("user_data", {}).get("_id", "N/A"))
            if logged_in_refid != "N/A":
                student_df = df_exploded[df_exploded["StudentID"] == int(logged_in_refid)]
                comparison_df = student_df.merge(subject_avg, on="SubjectCode", how="left")

                # Add comparison column
                comparison_df["Comparison"] = comparison_df.apply(
                    lambda row: (
                        "🟢" if row["Grade"] > float(row["AverageGrade"])
                        else "🔵" if row["Grade"] == float(row["AverageGrade"])
                        else "🔴"
                    ),
                    axis=1
                )

                # Separate by semester
                if "SchoolYear" in comparison_df.columns and "Semester" in comparison_df.columns:
                    grouped = comparison_df.groupby(["SchoolYear", "Semester"])

                    def color_comparison(val):
                        if val == "🟢":
                            return "color: green; font-weight: bold;"
                        elif val == "🔵":
                            return "color: blue; font-weight: bold;"
                        elif val == "🔴":
                            return "color: red; font-weight: bold;"
                        return ""

                    for (sy, sem), group in grouped:
                        st.subheader(f"📚 {sy} - {sem}")
                        display_df = group[["SubjectCode", "Description", "Teacher", "Grade", "AverageGrade", "Comparison"]]
                        styled = display_df.style.applymap(color_comparison, subset=["Comparison"])
                        st.dataframe(styled, use_container_width=True)

                    # ---------------- PDF GENERATION ----------------
                    def generate_comparison_pdf():
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=A4)
                        styles = getSampleStyleSheet()
                        elements = []

                        elements.append(Paragraph("Grade Comparison Report", styles["Title"]))
                        elements.append(Spacer(1, 12))

                        # Student Info
                        user_data = st.session_state.get("user_data", {})
                        full_name = user_data.get("Name", "Unknown")
                        elements.append(Paragraph(f"<b>Student Name:</b> {full_name}", styles["Normal"]))
                        elements.append(Paragraph(f"<b>Reference ID:</b> {logged_in_refid}", styles["Normal"]))
                        elements.append(Spacer(1, 12))

                        # Legend
                        elements.append(Paragraph("Legend: 🟢 Above Average | 🔵 Equal to Average | 🔴 Below Average", styles["Normal"]))
                        elements.append(Spacer(1, 12))

                        # Loop semesters
                        for (sy, sem), group in grouped:
                            elements.append(Paragraph(f"📚 {sy} - {sem}", styles["Heading3"]))
                            elements.append(Spacer(1, 6))

                            table_data = [list(group[["SubjectCode", "Description", "Teacher", "Grade", "AverageGrade", "Comparison"]].columns)]
                            for _, row in group.iterrows():
                                table_data.append([
                                    row["SubjectCode"],
                                    row.get("Description", "N/A"),
                                    row.get("Teacher", "N/A"),
                                    str(row["Grade"]),
                                    str(row["AverageGrade"]),
                                    row["Comparison"]
                                ])

                            # Define column widths
                            col_widths = [60, 140, 80, 50, 60, 50]

                            table = Table(table_data, repeatRows=1, colWidths=col_widths)
                            table.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 9),
                                ("FONTSIZE", (0, 1), (-1, -1), 8),
                                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ]))

                            elements.append(table)
                            elements.append(Spacer(1, 12))

                        # Conclusion
                        elements.append(Paragraph("Conclusion", styles["Heading3"]))
                        conclusion_text = """
                        This report compares the student's performance against the class average.
                        🟢 means the student performed above average, 🔵 means equal to average, and 🔴 means below average.
                        """
                        elements.append(Paragraph(conclusion_text, styles["Normal"]))

                        doc.build(elements)
                        buffer.seek(0)
                        return buffer

                    # ✅ Download Button
                    pdf_buffer = generate_comparison_pdf()
                    st.download_button(
                        label="📥 Download Comparison PDF",
                        data=pdf_buffer,
                        file_name="grade_comparison.pdf",
                        mime="application/pdf"
                    )
        with tab4:
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"])
                subjects_df = get_subjects()
                cols = st.columns(3)
                i = 0

                # Store figures for PDF
                charts = []

                for (sy, sem), sem_df in grouped:
                    if "SubjectCodes" in sem_df and sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                        expanded_df = pd.DataFrame({
                            "SubjectCodes": sem_df["SubjectCodes"].explode().values,
                            "Teacher": sem_df["Teachers"].explode().values,
                            "Grade": sem_df["Grades"].explode().values
                        })
                    else:
                        expanded_df = sem_df[["SubjectCodes", "Teachers", "Grades"]].rename(
                            columns={"Teachers": "Teacher", "Grades": "Grade"}
                        )

                    expanded_df = expanded_df.merge(
                        subjects_df.rename(columns={"_id": "SubjectCodes"}),
                        on="SubjectCodes",
                        how="left"
                    )

                    if "Description" not in expanded_df.columns:
                        expanded_df["Description"] = "N/A"

                    expanded_df = expanded_df[["SubjectCodes", "Description", "Teacher", "Grade"]]
                    expanded_df["Grade"] = pd.to_numeric(expanded_df["Grade"], errors="coerce")

                    # Plot chart
                    fig, ax = plt.subplots(figsize=(6, 3))
                    bars = ax.bar(
                        expanded_df["SubjectCodes"],
                        expanded_df["Grade"],
                        color=["green" if g >= 75 else "red" for g in expanded_df["Grade"]]
                    )
                    ax.set_ylim(0, 100)
                    ax.set_ylabel("Grade")
                    ax.set_xlabel("Subjects")
                    ax.set_title(f"{sy} - Sem {sem}")
                    plt.xticks(rotation=45, ha="right")

                    # Add grade labels
                    for bar, grade in zip(bars, expanded_df["Grade"]):
                        ax.text(bar.get_x() + bar.get_width() / 3, bar.get_height() + 1,
                                f"{grade:.0f}", ha="center", fontsize=8)

                    with cols[i % 3]:
                        st.pyplot(fig)
                    i += 1

                    # Save chart image for PDF
                    img_buf = io.BytesIO()
                    plt.savefig(img_buf, format="PNG", bbox_inches="tight")
                    img_buf.seek(0)
                    charts.append((f"{sy} - Semester {sem}", img_buf))
                    plt.close(fig)

                # ---------------- PDF GENERATION ----------------
                def generate_visualization_pdf():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    styles = getSampleStyleSheet()
                    elements = []

                    elements.append(Paragraph("Grade Visualization Report", styles["Title"]))
                    elements.append(Spacer(1, 12))

                    # Student Info
                    user_data = st.session_state.get("user_data", {})
                    full_name = user_data.get("Name", "Unknown")
                    ref_id = str(user_data.get("_id", "N/A"))
                    elements.append(Paragraph(f"<b>Student Name:</b> {full_name}", styles["Normal"]))
                    elements.append(Paragraph(f"<b>Reference ID:</b> {ref_id}", styles["Normal"]))
                    elements.append(Spacer(1, 12))

                    # Insert each chart per semester
                    for title, img_buf in charts:
                        elements.append(Paragraph(title, styles["Heading3"]))
                        elements.append(Spacer(1, 6))
                        elements.append(Image(img_buf, width=450, height=220))  # Scale image
                        elements.append(Spacer(1, 12))

                    # Conclusion
                    elements.append(Paragraph("Conclusion", styles["Heading3"]))
                    elements.append(Paragraph(
                        "This visualization highlights the student’s performance per subject. "
                        "Green bars indicate passing grades, while red bars indicate failing grades.",
                        styles["Normal"]
                    ))

                    doc.build(elements)
                    buffer.seek(0)
                    return buffer

                # ✅ Download Button
                pdf_buffer = generate_visualization_pdf()
                st.download_button(
                    label="📥 Download Grade Visualization PDF",
                    data=pdf_buffer,
                    file_name="grade_visualization.pdf",
                    mime="application/pdf"
                )

# ------------------ New Dashboard ------------------ #
def show_student_dashboard_new():
    st.info("🆕 New Version - Enhanced student dashboard with improved features")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Performance Trend Over Time",
        "Subject Difficulty Ratings",
        "Comparison with Class Average",
        "Passed vs Failed Summary",
        "Curriculum Vitae"
    ])

    
    with tab1:
    # --- Get logged-in student ---
        user_data = st.session_state.get("user_data", {})
        logged_in_refid = str(user_data.get("_id", "N/A"))
        logged_in_name = user_data.get("Name", "Unknown User")

        try:
            # --- Load grades ---
            new_grades = pd.read_pickle("pkl/new_grades.pkl")
            grades_df = pd.DataFrame(new_grades)

            # ✅ Filter for logged-in student
            if logged_in_refid.isdigit():
                grades_df = grades_df[grades_df["StudentID"] == int(logged_in_refid)]
            else:
                grades_df = pd.DataFrame()  # no valid student

            # --- Load student info ---
            course = "N/A"
            try:
                students = pd.read_pickle("pkl/new_students.pkl")
                students_df = pd.DataFrame(students)
                student_info = students_df[students_df["_id"] == int(logged_in_refid)]

                if not student_info.empty:
                    course = student_info.iloc[0].get("Course", "N/A")
            except Exception:
                course = user_data.get("Course", "N/A")

            # --- Compute total average ---
            total_avg = None
            if not grades_df.empty:
                all_grades = grades_df["Grades"].explode()
                all_grades = pd.to_numeric(all_grades, errors="coerce").dropna()
                total_avg = all_grades.mean() if not all_grades.empty else None

            # --- 🎯 Display header (always visible) ---
            st.markdown("### 🧑 Student Information")
            st.write(f"**Name:** {logged_in_name}")
            st.write(f"**Course:** {course}")
            if total_avg is not None:
                st.write(f"**Total Average:** {total_avg:.2f}")
            else:
                st.write("**Total Average:** N/A")

            # --- Proceed only if grades exist ---
            if grades_df.empty:
                st.info("No grades found for this student.")
            else:
                # --- Load semester table ---
                semesters = pd.read_pickle("pkl/semesters.pkl")
                semesters_df = pd.DataFrame(semesters)

                # ✅ Merge semester info (SemesterID ↔ _id)
                grades_df = grades_df.merge(
                    semesters_df,
                    left_on="SemesterID",
                    right_on="_id",
                    how="left"
                )

                # Drop unused columns
                grades_df = grades_df.drop(columns=["_id", "StudentID"], errors="ignore")

                # --- Load curriculum subjects ---
                curriculums = pd.read_pickle("pkl/curriculums.pkl")
                if isinstance(curriculums, pd.DataFrame):
                    curriculums = curriculums.to_dict(orient="records")

                # Flatten all subjects from curriculum into one DataFrame
                all_subjects = []
                for curriculum in curriculums:
                    for subj in curriculum.get("subjects", []):
                        all_subjects.append(subj)
                subjects_df = (
                    pd.DataFrame(all_subjects)
                    if all_subjects
                    else pd.DataFrame(columns=["subjectCode", "subjectName", "units"])
                )

                transcript_data = {}
                semester_avgs = []


                # --- 🔹 General Grade Summary ---
                st.subheader("📊 General Grade Summary")
                all_grades = grades_df["Grades"].explode()  # flatten list of grades
                all_grades = pd.to_numeric(all_grades, errors="coerce").dropna()

                if not all_grades.empty:
                    summary_df = pd.DataFrame([{
                        "MEAN": round(all_grades.mean(), 2),
                        "MEDIAN": round(all_grades.median(), 2),
                        "HIGHEST": round(all_grades.max(), 2),
                        "LOWEST": round(all_grades.min(), 2)
                    }])
                    st.dataframe(summary_df)


                    # Remove index completely
                    summary_df.index = [""]

                    styled_summary = summary_df.style.set_table_styles(
                        [
                            {"selector": "thead th", "props": "background-color: gray; color: white; text-align: center;"},
                            {"selector": "tbody td", "props": "text-align: center;"},
                            {"selector": "table", "props": "border-collapse: collapse; border: 1px solid black;"},
                            {"selector": "td, th", "props": "border: 1px solid black; padding: 5px;"}
                        ]
                    )

                    
                    st.subheader("📊 My Grades by Semester")

                # --- Group by SchoolYear + Semester ---
                if "SchoolYear" in grades_df.columns and "Semester" in grades_df.columns:
                    grouped = grades_df.groupby(["SchoolYear", "Semester"])

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

                        # ✅ Merge with curriculum subjects to get subjectName + units
                        expanded = expanded.merge(
                            subjects_df[["subjectCode", "subjectName", "units"]],
                            left_on="SubjectCode",
                            right_on="subjectCode",
                            how="left"
                        ).drop(columns=["subjectCode"])

                        # ✅ Reorder columns
                        expanded = expanded[["SubjectCode", "subjectName", "units", "Teacher", "Grade"]]

                        # ✅ Add STATUS column
                        expanded["Status"] = expanded["Grade"].apply(
                            lambda x: "PASSED" if pd.to_numeric(x, errors="coerce") >= 75 else "FAILED"
                        )

                        # ✅ Rename columns to ALL CAPS
                        expanded.rename(columns=str.upper, inplace=True)

                        # ✅ Style: make FAILED red
                        def highlight_status(val):
                            if val == "FAILED":
                                return "color: red; font-weight: bold;"
                            return "color: white;"

                        styled = expanded.style.applymap(highlight_status, subset=["STATUS"])

                        # Show styled table
                        st.dataframe(styled, use_container_width=True)

                        # --- Semester average ---
                        valid_grades = pd.to_numeric(expanded["GRADE"], errors="coerce").dropna()
                        if not valid_grades.empty:
                            avg = valid_grades.mean()
                            st.write(f"**Semester Average: {avg:.2f}**")
                            semester_avgs.append((f"{sy} - {sem}", avg))
                        else:
                            st.write("**Semester Average: N/A**")

                        # --- Semester total units ---
                        total_units = pd.to_numeric(expanded["UNITS"], errors="coerce").fillna(0).sum()
                        st.write(f"**Total Units: {int(total_units)}**")

                        transcript_data[f"{sy} - {sem}"] = expanded
                        st.markdown("---")

            # --- Line Graph ---
            if semester_avgs:
                semester_labels, semester_values = zip(*semester_avgs)
                overall_avg = sum(semester_values) / len(semester_values)

                # ✅ Add "Final Average"
                semester_labels = list(semester_labels) + ["Final Average"]
                semester_values = list(semester_values) + [overall_avg]

                fig, ax = plt.subplots(figsize=(10, 2.5), dpi=120)
                ax.plot(semester_labels, semester_values, linestyle="-", color="gray", zorder=1, linewidth=1)

                # ✅ Color-coded points
                for i, value in enumerate(semester_values):
                    color = "red" if value < 75 else "blue"
                    ax.scatter(i, value, color=color, s=30, zorder=2)
                    ax.text(i, value + 1, f"{value:.1f}", ha="center", fontsize=7, color=color)

                ax.set_ylim(1, 100)
                ax.set_title("📈 Semester & Final Average", fontsize=9)
                ax.set_xlabel("Semester", fontsize=8)
                ax.set_ylabel("Average", fontsize=8)
                ax.tick_params(axis="both", labelsize=7)
                ax.grid(True, linewidth=0.3)
                plt.xticks(range(len(semester_labels)), semester_labels, rotation=30, ha="right", fontsize=7)

                st.pyplot(fig, use_container_width=True)

                # --- Generate PDF ---
                def generate_pdf():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    styles = getSampleStyleSheet()
                    elements = []

                   # --- Load student info ---
                    students = pd.read_pickle("pkl/new_students.pkl")
                    students_df = pd.DataFrame(students)

                    # Match logged-in student
                    student_info = students_df[students_df["_id"] == int(logged_in_refid)]

                    if not student_info.empty:
                        course = student_info.iloc[0].get("Course", "N/A")
                        year_level = student_info.iloc[0].get("YearLevel", "N/A")
                    else:
                        course = user_data.get("Course", "N/A")
                        year_level = user_data.get("YearLevel", "N/A")

                    # --- Student Info ---
                    elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                    elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                    elements.append(Paragraph(f"Course: {course}", styles["Normal"]))
                    elements.append(Paragraph(f"Year Level: {year_level}", styles["Normal"]))
                    elements.append(Spacer(1, 12))
                    # --- General Grade Summary ---
                    if not all_grades.empty:
                        elements.append(Paragraph("📊 General Grade Summary", styles["Heading3"]))
                        summary_data = [["MEAN", "MEDIAN", "HIGHEST", "LOWEST"]] + [
                            [f"{all_grades.mean():.2f}", f"{all_grades.median():.2f}", f"{all_grades.max():.2f}", f"{all_grades.min():.2f}"]
                        ]
                        table = Table(summary_data, hAlign="LEFT")
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black)
                        ]))
                        elements.append(table)
                        elements.append(Spacer(1, 12))

                   # --- Transcript Data ---
                    elements.append(Paragraph("📚 Grades by Semester", styles["Heading3"]))

                    # Define a style for wrapped text
                    wrap_style = ParagraphStyle(
                        name="wrap_style",
                        fontSize=7,
                        leading=8
                    )

                    for sem, sem_df in transcript_data.items():
                        elements.append(Paragraph(f"<b>{sem}</b>", styles["Heading4"]))

                        # Convert dataframe to list of lists for PDF with wrapping
                        table_data = [sem_df.columns.tolist()]
                        for row in sem_df.astype(str).values.tolist():
                            wrapped_row = [
                                Paragraph(cell, wrap_style) if i in [1, 3] else Paragraph(cell, wrap_style)
                                for i, cell in enumerate(row)
                            ]
                            table_data.append(wrapped_row)

                        # ✅ Set smaller fixed widths so table fits A4
                        col_widths = [0.8*inch, 2.0*inch, 0.6*inch, 1.6*inch, 0.6*inch, 0.8*inch]

                        table = Table(table_data, repeatRows=1, hAlign="LEFT", colWidths=col_widths)
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                            ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ]))
                        elements.append(table)
                        elements.append(Spacer(1, 6))

                        # Add semester average + units
                        avg = semester_avgs[[s for s, _ in semester_avgs].index(sem)][1]
                        total_units = pd.to_numeric(sem_df["UNITS"], errors="coerce").fillna(0).sum()
                        elements.append(Paragraph(f"Semester Average: {avg:.2f}", styles["Normal"]))
                        elements.append(Paragraph(f"Total Units: {int(total_units)}", styles["Normal"]))
                        elements.append(Spacer(1, 12))
                        
                    # --- Line Graph of Semester Averages ---
                    if semester_avgs:
                        fig, ax = plt.subplots(figsize=(6, 2.5))
                        semester_labels, semester_values = zip(*semester_avgs)
                        overall_avg = sum(semester_values) / len(semester_values)
                        semester_labels = list(semester_labels) + ["Final Average"]
                        semester_values = list(semester_values) + [overall_avg]

                        ax.plot(semester_labels, semester_values, linestyle="-", color="gray")
                        for i, value in enumerate(semester_values):
                            color = "red" if value < 75 else "blue"
                            ax.scatter(i, value, color=color)
                            ax.text(i, value + 1, f"{value:.1f}", ha="center", fontsize=6, color=color)
                        ax.set_ylim(1, 100)
                        ax.set_title("📈 Semester & Final Average", fontsize=9)
                        plt.xticks(rotation=30, ha="right", fontsize=7)
                        ax.grid(True, linewidth=0.3)

                        # Save plot to image
                        img_buf = io.BytesIO()
                        plt.savefig(img_buf, format="PNG", bbox_inches="tight", dpi=120)
                        plt.close(fig)
                        img_buf.seek(0)
                        elements.append(Image(img_buf, width=400, height=150))
                        elements.append(Spacer(1, 12))
                          # --- Conclusion Section ---
                        elements.append(Spacer(1, 24))  # add space before conclusion

                        conclusion_text = """
                        The transcript above reflects the academic performance of the student across all recorded semesters. 
                        Overall averages and subject-specific grades provide a clear summary of achievements and areas of improvement. 
                        This record is generated directly from the student database and may be used for academic monitoring, advising, 
                        and progress evaluation.
                        """

                        elements.append(Paragraph(conclusion_text, styles["Normal"]))


                    doc.build(elements)
                    buffer.seek(0)
                    return buffer
              
                pdf_buffer = generate_pdf()
                st.download_button(
                    label="📄 Download Transcript PDF",
                    data=pdf_buffer,
                    file_name=f"{logged_in_name}_Transcript.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"❌ Error loading grades: {e}")
    with tab2:
        failed_subjects = []  # collect all failed rows

        # --- Load all grades for student counting ---
        all_grades_df = pd.read_pickle("pkl/new_grades.pkl")
        all_grades_df = pd.DataFrame(all_grades_df)

        # --- Group by SchoolYear + Semester ---
        if "SchoolYear" in grades_df.columns and "Semester" in grades_df.columns:
            grouped = grades_df.groupby(["SchoolYear", "Semester"])

            for (sy, sem), sem_df in grouped:
                # Handle expanded grades
                if sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                    expanded = pd.DataFrame({
                        "SubjectCode": sem_df["SubjectCodes"].explode().values,
                        "Teacher": sem_df["Teachers"].explode().values,
                        "Grade": sem_df["Grades"].explode().values,
                        "SemesterID": sem_df["SemesterID"].iloc[0],
                        "section": sem_df["section"].iloc[0] if "section" in sem_df.columns else None,
                        "StudentID": sem_df["StudentID"].iloc[0] if "StudentID" in sem_df.columns else None
                    })
                else:
                    expanded = sem_df[["SubjectCodes", "Teachers", "Grades", "SemesterID", "section", "StudentID"]].rename(
                        columns={"SubjectCodes": "SubjectCode", "Teachers": "Teacher", "Grades": "Grade"}
                    )

                # Merge with curriculum subjects
                expanded = expanded.merge(
                    subjects_df[["subjectCode", "subjectName", "units"]],
                    left_on="SubjectCode",
                    right_on="subjectCode",
                    how="left"
                ).drop(columns=["subjectCode"])

                # Add semester info
                expanded["SchoolYear"] = sy
                expanded["Semester"] = sem

                # Add status (temporary before replacing with LOW/MEDIUM/HIGH)
                expanded["Status"] = expanded["Grade"].apply(
                    lambda x: "PASSED" if pd.to_numeric(x, errors="coerce") >= 75 else "FAILED"
                )

                # Collect failed rows
                failed_rows = expanded[expanded["Status"] == "FAILED"].copy()
                if not failed_rows.empty:
                    # --- Add total student count + fail percentage ---
                    for idx, row in failed_rows.iterrows():
                        subject_code = row["SubjectCode"]
                        semester_id = row["SemesterID"]
                        section = row["section"]

                        # --- Get all students for that subject ---
                        subject_students = all_grades_df[
                            (all_grades_df["SemesterID"] == semester_id) &
                            (all_grades_df["section"] == section) &
                            (all_grades_df["SubjectCodes"].apply(
                                lambda sc: subject_code in sc if isinstance(sc, list) else sc == subject_code
                            ))
                        ]

                        total_students = subject_students["StudentID"].nunique()

                        # --- Count how many failed (<75) ---
                        failed_count = 0
                        if not subject_students.empty:
                            expanded_subject = pd.DataFrame({
                                "StudentID": subject_students["StudentID"].repeat(
                                    subject_students["Grades"].str.len()
                                    if subject_students["Grades"].dtype == "O" else 1
                                ).values,
                                "SubjectCode": subject_students["SubjectCodes"].explode().values,
                                "Grade": subject_students["Grades"].explode().values
                            })
                            failed_count = expanded_subject[
                                (expanded_subject["SubjectCode"] == subject_code) &
                                (pd.to_numeric(expanded_subject["Grade"], errors="coerce") < 75)
                            ]["StudentID"].nunique()

                        # --- Save to row ---
                        failed_rows.loc[idx, "TotalStudents"] = int(total_students)
                        failed_rows.loc[idx, "FailedStudents"] = int(failed_count)  # ensure no decimals
                        failed_rows.loc[idx, "FailedPercentage"] = (
                            round((failed_count / total_students) * 100, 2) if total_students > 0 else 0
                        )

                    failed_subjects.append(failed_rows)

        # ✅ Combine all failed into one table
        if failed_subjects:
            failed_df = pd.concat(failed_subjects, ignore_index=True)

            # ✅ Make sure numeric columns are correct
            failed_df["TotalStudents"] = failed_df["TotalStudents"].astype(int)
            failed_df["FailedStudents"] = failed_df["FailedStudents"].astype(int)   # 👈 force integer
            failed_df["FailedPercentage"] = failed_df["FailedPercentage"].astype(float)

            # --- Replace STATUS with LOW / MEDIUM / HIGH ---
            def categorize_status(pct):
                if pct <= 5:
                    return "LOW"
                elif 6 <= pct <= 10:
                    return "MEDIUM"
                else:
                    return "HIGH"

            failed_df["Status"] = failed_df["FailedPercentage"].apply(categorize_status)

            # Format FailedPercentage as string with 2 decimals + %
            failed_df["FailedPercentage"] = failed_df["FailedPercentage"].map(lambda x: f"{x:.2f}%")

            # Reorder + uppercase
            failed_df = failed_df[[
                "SchoolYear", "Semester", "SubjectCode", "subjectName",
                "units", "Teacher", "Grade", "Status",
                "TotalStudents", "FailedStudents", "FailedPercentage"  # 👈 Added FailedStudents
            ]]
            failed_df.rename(columns=str.upper, inplace=True)

            # Highlight based on status
            def highlight_status(val):
                if val == "LOW":
                    return "color: green; font-weight: bold;"
                elif val == "MEDIUM":
                    return "color: orange; font-weight: bold;"
                elif val == "HIGH":
                    return "color: red; font-weight: bold;"
                return ""

            styled_failed = failed_df.style.applymap(highlight_status, subset=["STATUS"])

            st.subheader("❌ All Failed Subjects (with Risk Levels)")
            st.dataframe(styled_failed, use_container_width=True)

            # --- 📄 Generate PDF for Failed Subjects ---
            def generate_failed_pdf():
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                styles = getSampleStyleSheet()
                elements = []

                # --- Load student info ---
                students = pd.read_pickle("pkl/new_students.pkl")
                students_df = pd.DataFrame(students)

                # Match logged-in student
                student_info = students_df[students_df["_id"] == int(logged_in_refid)]

                if not student_info.empty:
                    course = student_info.iloc[0].get("Course", "N/A")
                    year_level = student_info.iloc[0].get("YearLevel", "N/A")
                else:
                    course = user_data.get("Course", "N/A")
                    year_level = user_data.get("YearLevel", "N/A")

                # --- Student Info ---
                elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                elements.append(Paragraph(f"Course: {course}", styles["Normal"]))
                elements.append(Paragraph(f"Year Level: {year_level}", styles["Normal"]))
                elements.append(Spacer(1, 12))

                # --- Table ---
                table_data = [failed_df.columns.tolist()] + failed_df.astype(str).values.tolist()

                wrap_style = ParagraphStyle("wrap_style", fontSize=5, leading=6)

                for i in range(1, len(table_data)):  # skip header row
                    table_data[i][3] = Paragraph(table_data[i][3], wrap_style)  # SUBJECTNAME col

                # Calculate dynamic column widths
                page_width = doc.width
                col_widths = [
                    page_width * 0.09,  # SCHOOLYEAR
                    page_width * 0.08,  # SEMESTER
                    page_width * 0.09,  # SUBJECTCODE
                    page_width * 0.19,  # SUBJECTNAME
                    page_width * 0.05,  # UNITS
                    page_width * 0.12,  # TEACHER
                    page_width * 0.07,  # GRADE
                    page_width * 0.05,  # STATUS
                    page_width * 0.11,  # TOTALSTUDENTS
                    page_width * 0.11,  # FAILEDSTUDENTS  👈 NEW
                    page_width * 0.12,  # FAILEDPERCENTAGE
                ]

                table = Table(
                    table_data,
                    repeatRows=1,
                    hAlign="LEFT",
                    colWidths=col_widths
                )

                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.red),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))

                elements.append(table)
                elements.append(Spacer(1, 12))

                # --- Conclusion ---
                elements.append(Paragraph("Conclusion", styles["Heading3"]))
                conclusion_text = """
                The above list summarizes all subjects where the student received a failing grade (< 75).
                The STATUS column now indicates the risk level:
                - LOW (≤5%) - Green
                - MEDIUM (6–10%) - Yellow
                - HIGH (≥11%) - Red
                """
                elements.append(Paragraph(conclusion_text, styles["Normal"]))

                # Build PDF
                doc.build(elements)
                buffer.seek(0)
                return buffer

            pdf_failed_buffer = generate_failed_pdf()
            st.download_button(
                label="📄 Download Failed Subjects PDF",
                data=pdf_failed_buffer,
                file_name=f"{logged_in_name}_Failed_Subjects.pdf",
                mime="application/pdf"
            )
        else:
            st.success("✅ No failed subjects found!")
    with tab3:
        st.markdown("""
        **Comparison Legend:**  
        🟢  : Above Average  🔵  : Equal to Average  🔴  : Below Average
        """)

        # --- Get logged-in student ---
        user_data = st.session_state.get("user_data", {})
        logged_in_refid = str(user_data.get("_id", "N/A"))
        logged_in_name = user_data.get("Name", "Unknown User")

        try:
            # --- Load all grades ---
            new_grades = pd.read_pickle("pkl/new_grades.pkl")
            grades_df = pd.DataFrame(new_grades)

            # ✅ Total number of unique students
            total_students = grades_df["StudentID"].nunique()

            # ✅ Expand SubjectCodes/Grades into rows
            all_subject_grades = []
            for _, row in grades_df.iterrows():
                if isinstance(row["SubjectCodes"], list):
                    for subj, grade in zip(row["SubjectCodes"], row["Grades"]):
                        all_subject_grades.append({
                            "StudentID": row["StudentID"],
                            "SubjectCode": subj,
                            "Grade": grade,
                            "section": row.get("section", "N/A"),
                            "SemesterID": row.get("SemesterID", None)
                        })
                else:
                    all_subject_grades.append({
                        "StudentID": row["StudentID"],
                        "SubjectCode": row["SubjectCodes"],
                        "Grade": row["Grades"],
                        "section": row.get("section", "N/A"),
                        "SemesterID": row.get("SemesterID", None)
                    })

            all_subject_grades_df = pd.DataFrame(all_subject_grades)
            all_subject_grades_df["Grade"] = pd.to_numeric(all_subject_grades_df["Grade"], errors="coerce")

            # ✅ Class average per subject + section + SemesterID
            subject_avg_df = (
                all_subject_grades_df.groupby(["SubjectCode", "section", "SemesterID"])["Grade"]
                .mean()
                .reset_index()
                .rename(columns={"Grade": "ClassAverage"})
            )
            subject_avg_df["ClassAverage"] = subject_avg_df["ClassAverage"].round(2)

            # ✅ Total student count per subject + section + SemesterID
            subject_count_df = (
                all_subject_grades_df.groupby(["SubjectCode", "section", "SemesterID"])
                .size()
                .reset_index(name="TotalStudent")
            )

            # ✅ Student rank per subject + section + SemesterID
            all_subject_grades_df["Rank"] = (
                all_subject_grades_df.groupby(["SubjectCode", "section", "SemesterID"])["Grade"]
                .rank(method="min", ascending=False)
            )

            # ✅ Filter for logged-in student only
            student_grades_df = grades_df[grades_df["StudentID"] == int(logged_in_refid)]

            if student_grades_df.empty:
                st.info("No grades found for this student.")
            else:
                # --- Load semester table ---
                semesters = pd.read_pickle("pkl/semesters.pkl")
                semesters_df = pd.DataFrame(semesters)

                # ✅ Merge semester info
                student_grades_df = student_grades_df.merge(
                    semesters_df,
                    left_on="SemesterID",
                    right_on="_id",
                    how="left"
                ).drop(columns=["_id", "StudentID"], errors="ignore")

                # --- Load curriculum subjects ---
                curriculums = pd.read_pickle("pkl/curriculums.pkl")
                if isinstance(curriculums, pd.DataFrame):
                    curriculums = curriculums.to_dict(orient="records")

                all_subjects = []
                for curriculum in curriculums:
                    for subj in curriculum.get("subjects", []):
                        all_subjects.append(subj)
                subjects_df = (
                    pd.DataFrame(all_subjects)
                    if all_subjects
                    else pd.DataFrame(columns=["subjectCode", "subjectName", "units"])
                )

                # ✅ Store semester-wise tables for PDF later
                semester_comparison = {}

                # --- Group by SchoolYear + Semester + Section ---
                if "SchoolYear" in student_grades_df.columns and "Semester" in student_grades_df.columns:
                    grouped = student_grades_df.groupby(["SchoolYear", "Semester", "section", "SemesterID"])

                    for (sy, sem, student_section, sem_id), sem_df in grouped:
                        st.subheader(f"📚 {sy} - {sem} (section {student_section})")

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

                        # ✅ Merge with curriculum subjects
                        expanded = expanded.merge(
                            subjects_df[["subjectCode", "subjectName", "units"]],
                            left_on="SubjectCode",
                            right_on="subjectCode",
                            how="left"
                        ).drop(columns=["subjectCode"])

                        # ✅ Add Section + SemesterID
                        expanded["section"] = student_section
                        expanded["SemesterID"] = sem_id

                        # ✅ Merge with total student count
                        expanded = expanded.merge(
                            subject_count_df,
                            on=["SubjectCode", "section", "SemesterID"],
                            how="left"
                        )

                        # ✅ Merge with class average
                        expanded = expanded.merge(
                            subject_avg_df,
                            on=["SubjectCode", "section", "SemesterID"],
                            how="left"
                        )

                        # ✅ Merge with student rank
                        expanded = expanded.merge(
                            all_subject_grades_df[["SubjectCode", "section", "SemesterID", "StudentID", "Rank"]],
                            left_on=["SubjectCode", "section", "SemesterID"],
                            right_on=["SubjectCode", "section", "SemesterID"],
                            how="left"
                        )

                        # ✅ Keep only the logged-in student's rank
                        expanded = expanded[expanded["Rank"].notna()].drop_duplicates(subset=["SubjectCode"])

                        # ✅ Add comparison column
                        expanded["Comparison"] = expanded.apply(
                            lambda row: (
                                "🟢 Above Average" if row["Grade"] > row["ClassAverage"]
                                else "🔵 Equal To Average" if row["Grade"] == row["ClassAverage"]
                                else "🔴 Below Average"
                            ),
                            axis=1
                        )

                        # ✅ Rank string (e.g., "3/40")
                        expanded["RANK"] = expanded.apply(
                            lambda row: f"{int(row['Rank'])}/{int(row['TotalStudent'])}", axis=1
                        )

                        # ✅ Reorder columns
                        expanded = expanded[
                            ["SubjectCode", "subjectName", "units", "Teacher", "Grade",
                            "ClassAverage", "Comparison", "TotalStudent", "RANK"]
                        ]
                        expanded.rename(columns=str.upper, inplace=True)

                        # ✅ Save for PDF
                        semester_comparison[f"{sy} - {sem} (section {student_section})"] = expanded.copy()

                        # Show table
                        st.dataframe(expanded, use_container_width=True)

                # --- 📄 Generate PDF function ---
                def generate_comparison_pdf():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    styles = getSampleStyleSheet()
                    elements = []

                    # --- Load student info ---
                    students = pd.read_pickle("pkl/new_students.pkl")
                    students_df = pd.DataFrame(students)

                    # Match logged-in student
                    student_info = students_df[students_df["_id"] == int(logged_in_refid)]

                    if not student_info.empty:
                        course = student_info.iloc[0].get("Course", "N/A")
                        year_level = student_info.iloc[0].get("YearLevel", "N/A")
                    else:
                        course = user_data.get("Course", "N/A")
                        year_level = user_data.get("YearLevel", "N/A")

                    # --- Student Info ---
                    elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                    elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                    elements.append(Paragraph(f"Course: {course}", styles["Normal"]))
                    elements.append(Paragraph(f"Year Level: {year_level}", styles["Normal"]))
                    elements.append(Spacer(1, 12))

                    # --- Custom wrap style for subject names ---
                    wrap_style = ParagraphStyle(name="Wrap", fontSize=6, leading=7, alignment=1)

                    # --- Add semester tables ---
                    for sem, sem_df in semester_comparison.items():
                        elements.append(Paragraph(f"<b>{sem}</b>", styles["Heading3"]))

                        sem_df = sem_df.copy()
                        sem_df["SUBJECTNAME"] = sem_df["SUBJECTNAME"].apply(
                            lambda x: Paragraph(str(x), wrap_style)
                        )

                        # Convert dataframe to list of lists
                        table_data = [sem_df.columns.tolist()] + sem_df.values.tolist()

                        # Column widths
                        page_width = doc.width
                        col_widths = [
                            page_width * 0.10,  # SubjectCode
                            page_width * 0.21,  # SubjectName
                            page_width * 0.06,  # Units
                            page_width * 0.15,  # Teacher
                            page_width * 0.08,  # Grade
                            page_width * 0.11,  # ClassAverage
                            page_width * 0.12,  # Comparison
                            page_width * 0.11,  # TotalStudent
                            page_width * 0.07,  # Rank
                        ]

                        # Create table
                        table = Table(table_data, repeatRows=1, hAlign="LEFT", colWidths=col_widths)
                        style = TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.red),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                            ("FONTSIZE", (0, 0), (-1, -1), 6),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ])

                        # --- Highlight the Comparison column ---
                        comp_idx = sem_df.columns.get_loc("COMPARISON") if "COMPARISON" in sem_df.columns else None
                        if comp_idx is not None:
                            for row_idx, value in enumerate(sem_df["COMPARISON"], start=1):  # start=1 (skip header row)
                                if "🟢" in str(value):
                                    style.add("BACKGROUND", (comp_idx, row_idx), (comp_idx, row_idx), colors.lightgreen)
                                elif "🔵" in str(value):
                                    style.add("BACKGROUND", (comp_idx, row_idx), (comp_idx, row_idx), colors.lightblue)
                                elif "🔴" in str(value):
                                    style.add("BACKGROUND", (comp_idx, row_idx), (comp_idx, row_idx), colors.pink)

                        table.setStyle(style)
                        elements.append(table)
                        elements.append(Spacer(1, 10))

                    # --- Conclusion ---
                    conclusion_text = """
                    This comparison highlights how the student’s performance compares with the overall class average 
                    and their rank among classmates (based on section and semester). 🟢 indicates above average, 
                    🔵 equal to average, 🔴 below average. Rank is shown as Position/Total Students.
                    """
                    elements.append(Paragraph("Conclusion", styles["Heading3"]))
                    elements.append(Paragraph(conclusion_text, styles["Normal"]))

                    doc.build(elements)
                    buffer.seek(0)
                    return buffer


                # --- Add Download Button ---
                pdf_buffer = generate_comparison_pdf()
                st.download_button(
                    label="📄 Download Comparison PDF",
                    data=pdf_buffer,
                    file_name=f"{logged_in_name}_Comparison.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Error: {e}")
    with tab4:
        user_data = st.session_state.get("user_data", {})
        logged_in_refid = str(user_data.get("_id", "N/A"))
        logged_in_name = user_data.get("Name", "Unknown User")

        try:
            # --- Load grades ---
            new_grades = pd.read_pickle("pkl/new_grades.pkl")
            grades_df = pd.DataFrame(new_grades)

            # ✅ Filter for logged-in student
            grades_df = grades_df[grades_df["StudentID"] == int(logged_in_refid)]

            if grades_df.empty:
                st.info("No grades found for this student.")
            else:
                # --- Load semester table ---
                semesters = pd.read_pickle("pkl/semesters.pkl")
                semesters_df = pd.DataFrame(semesters)

                # ✅ Merge semester info (SemesterID ↔ _id)
                grades_df = grades_df.merge(
                    semesters_df,
                    left_on="SemesterID",
                    right_on="_id",
                    how="left"
                )

                # Drop unused columns
                grades_df = grades_df.drop(columns=["_id", "StudentID"], errors="ignore")

                # --- Load curriculum subjects ---
                curriculums = pd.read_pickle("pkl/curriculums.pkl")
                if isinstance(curriculums, pd.DataFrame):
                    curriculums = curriculums.to_dict(orient="records")

                # Flatten all subjects from curriculum into one DataFrame
                all_subjects = []
                for curriculum in curriculums:
                    for subj in curriculum.get("subjects", []):
                        all_subjects.append(subj)
                subjects_df = (
                    pd.DataFrame(all_subjects)
                    if all_subjects
                    else pd.DataFrame(columns=["subjectCode", "subjectName", "units"])
                )

                # ✅ Subject Completion Overview
                expanded_grades = pd.DataFrame({
                    "SubjectCode": grades_df["SubjectCodes"].explode(),
                    "Grade": grades_df["Grades"].explode()
                })
                expanded_grades["Grade"] = pd.to_numeric(expanded_grades["Grade"], errors="coerce")

                # --- Counts
                passed_count = (expanded_grades["Grade"] >= 75).sum()
                failed_count = (expanded_grades["Grade"] < 75).sum()
                total_subjects = len(subjects_df)
                taken_subjects = expanded_grades["SubjectCode"].nunique()
                not_taken_count = total_subjects - taken_subjects

                # --- Percentages
                passed_pct = (passed_count / total_subjects * 100) if total_subjects > 0 else 0
                failed_pct = (failed_count / total_subjects * 100) if total_subjects > 0 else 0
                not_taken_pct = (not_taken_count / total_subjects * 100) if total_subjects > 0 else 0

                # --- Build table
                completion_data = {
                    "Category": [
                        "Passed Subject",
                        "Failed Subject",
                        "Not Yet Taken",
                        "Total Required Subject"
                    ],
                    "Count": [
                        passed_count,
                        failed_count,
                        not_taken_count,
                        total_subjects
                    ],
                    "Percentage": [
                        f"{passed_pct:.2f}%",
                        f"{failed_pct:.2f}%",
                        f"{not_taken_pct:.2f}%",
                        "100%"
                    ],
                    "Description": [
                        "Number of subjects successfully completed with passing grade.",
                        "Number of subjects with grade below 75 (failed).",
                        "Subjects still pending or not yet enrolled.",
                        "Total number of subjects required in the curriculum."
                    ]
                }

                completion_df = pd.DataFrame(completion_data)

                # --- Display in dashboard
                st.subheader("📊 Subject Completion Overview")
                st.table(completion_df.style.set_table_styles(
                    [{
                        'selector': 'thead th',
                        'props': [('background-color', '#1E1E1E'), ('color', 'white')]
                    }]
                ))

                # --- Group by SchoolYear + Semester ---
                if "SchoolYear" in grades_df.columns and "Semester" in grades_df.columns:
                    grouped = list(grades_df.groupby(["SchoolYear", "Semester"]))

                    st.subheader("75 Above is The Passing Grade✅ ")
                    st.subheader("🟦 PASSED || 🟥 FAILED")

                    # --- Process in chunks of 3 semesters per row ---
                    for i in range(0, len(grouped), 3):
                        cols = st.columns(3)

                        for j, (sy_sem, sem_df) in enumerate(grouped[i:i+3]):
                            sy, sem = sy_sem
                            with cols[j]:
                                st.subheader(f"📚 {sy} - {sem}")

                                # Expand subjects + grades
                                if sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                                    expanded = pd.DataFrame({
                                        "SubjectCode": sem_df["SubjectCodes"].explode().values,
                                        "Grade": sem_df["Grades"].explode().values
                                    })
                                else:
                                    expanded = sem_df[["SubjectCodes", "Grades"]].rename(
                                        columns={"SubjectCodes": "SubjectCode", "Grades": "Grade"}
                                    )

                                expanded = expanded.merge(
                                    subjects_df[["subjectCode", "subjectName"]],
                                    left_on="SubjectCode",
                                    right_on="subjectCode",
                                    how="left"
                                ).drop(columns=["subjectCode"])

                                expanded["Grade"] = pd.to_numeric(expanded["Grade"], errors="coerce")

                                # --- 📊 Bar chart ---
                                fig, ax = plt.subplots(figsize=(4, 3), dpi=120)
                                colors_list = ["red" if g < 75 else "blue" for g in expanded["Grade"]]

                                bars = ax.bar(expanded["SubjectCode"], expanded["Grade"], color=colors_list, zorder=2)

                                # Add labels on top
                                for bar, value in zip(bars, expanded["Grade"]):
                                    ax.text(
                                        bar.get_x() + bar.get_width() / 2,
                                        bar.get_height() + 1,
                                        f"{value:.0f}",
                                        ha="center",
                                        va="bottom",
                                        fontsize=7,
                                        color="black"
                                    )

                                ax.set_ylim(1, 100)
                                ax.set_title(f"{sy} {sem}", fontsize=9)
                                ax.set_xlabel("Subjects", fontsize=7)
                                ax.set_ylabel("Grade", fontsize=7)
                                ax.tick_params(axis="both", labelsize=6)
                                ax.grid(True, axis="y", linewidth=0.3, zorder=1)
                                plt.xticks(rotation=45, ha="right", fontsize=6)

                                st.pyplot(fig, use_container_width=True)

                    # --- 📄 Generate PDF function for Tab4 ---
                    def generate_pass_fail_pdf(completion_df):
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=A4)
                        styles = getSampleStyleSheet()
                        elements = []

                        # --- Student Info ---
                        students = pd.read_pickle("pkl/new_students.pkl")
                        students_df = pd.DataFrame(students)
                        student_info = students_df[students_df["_id"] == int(logged_in_refid)]

                        if not student_info.empty:
                            course = student_info.iloc[0].get("Course", "N/A")
                            year_level = student_info.iloc[0].get("YearLevel", "N/A")
                        else:
                            course = user_data.get("Course", "N/A")
                            year_level = user_data.get("YearLevel", "N/A")

                        elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                        elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                        elements.append(Paragraph(f"Course: {course}", styles["Normal"]))
                        elements.append(Paragraph(f"Year Level: {year_level}", styles["Normal"]))
                        elements.append(Spacer(1, 12))

                     # --- Subject Completion Overview ---
                        data = [completion_df.columns.tolist()] + completion_df.values.tolist()

                        # ✅ Calculate proportional column widths (smaller table)
                        page_width = doc.width
                        col_widths = [
                            page_width * 0.18,  # Category
                            page_width * 0.12,  # Count
                            page_width * 0.15,  # Percentage
                            page_width * 0.45   # Description
                        ]

                        table = Table(data, hAlign="LEFT", colWidths=col_widths)

                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#444141")),  # dark header like your example
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 7),   # smaller font
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]))
                        elements.append(table)
                        elements.append(Spacer(1, 12))

                        # --- Charts per semester ---
                        for (sy, sem), sem_df in grouped:
                            elements.append(Paragraph(f"<b>{sy} - {sem}</b>", styles["Heading3"]))

                            if sem_df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                                expanded = pd.DataFrame({
                                    "SubjectCode": sem_df["SubjectCodes"].explode().values,
                                    "Grade": sem_df["Grades"].explode().values
                                })
                            else:
                                expanded = sem_df[["SubjectCodes", "Grades"]].rename(
                                    columns={"SubjectCodes": "SubjectCode", "Grades": "Grade"}
                                )

                            expanded = expanded.merge(
                                subjects_df[["subjectCode", "subjectName"]],
                                left_on="SubjectCode",
                                right_on="subjectCode",
                                how="left"
                            ).drop(columns=["subjectCode"])
                            expanded["Grade"] = pd.to_numeric(expanded["Grade"], errors="coerce")

                            fig, ax = plt.subplots(figsize=(4, 3), dpi=120)
                            colors_list = ["red" if g < 75 else "blue" for g in expanded["Grade"]]
                            bars = ax.bar(expanded["SubjectCode"], expanded["Grade"], color=colors_list, zorder=2)

                            for bar, value in zip(bars, expanded["Grade"]):
                                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+1,
                                        f"{value:.0f}", ha="center", va="bottom", fontsize=7)

                            ax.set_ylim(1, 100)
                            ax.set_title(f"{sy} {sem}", fontsize=9)
                            ax.tick_params(axis="both", labelsize=6)
                            ax.grid(True, axis="y", linewidth=0.3, zorder=1)
                            plt.xticks(rotation=45, ha="right", fontsize=6)

                            img_buffer = io.BytesIO()
                            plt.savefig(img_buffer, format="PNG", bbox_inches="tight")
                            plt.close(fig)
                            img_buffer.seek(0)

                            elements.append(Image(img_buffer, width=400, height=250))
                            elements.append(Spacer(1, 12))
                        # --- ✅ Conclusion ---
                        conclusion_text = """
                        This report summarizes the student’s performance per semester.  
                        - 🟦 Blue bars indicate passed subjects (Grade ≥ 75).  
                        - 🟥 Red bars indicate failed subjects (Grade < 75).  
                        - The Subject Completion Overview shows total required subjects, completed ones, and pending ones.  

                        This helps track progress toward graduation requirements and highlights areas that need improvement.
                        """
                        elements.append(Paragraph("Conclusion", styles["Heading3"]))
                        elements.append(Paragraph(conclusion_text, styles["Normal"]))

                        doc.build(elements)
                        buffer.seek(0)
                        return buffer

                    # --- 📌 Add download button in Tab4 ---
                    pdf_buffer = generate_pass_fail_pdf(completion_df)
                    st.download_button(
                        "📥 Download PDF Report",
                        data=pdf_buffer,
                        file_name=f"{logged_in_name}_PassFail_Report.pdf",
                        mime="application/pdf"
                    )

        except Exception as e:
            st.error(f"Error loading data: {e}")
    with tab5:
        st.subheader("📘 Curriculum with Grades")

        try:
            # ✅ Get current logged-in user from session state
            user_data = st.session_state.get("user_data", {})
            logged_in_name = user_data.get("Name", "Unknown User")
            logged_in_refid = int(user_data.get("_id", 0))  # ensure int

            # ✅ Load curriculum
            curriculums = pd.read_pickle("pkl/curriculums.pkl")
            if isinstance(curriculums, pd.DataFrame):
                curriculums = curriculums.to_dict(orient="records")

            # ✅ Load new_grades
            new_grades_df = pd.read_pickle("pkl/new_grades.pkl")
            if not isinstance(new_grades_df, pd.DataFrame):
                new_grades_df = pd.DataFrame(new_grades_df)

            # ✅ Filter for the logged-in student
            student_grades = new_grades_df[new_grades_df['StudentID'] == logged_in_refid].copy()

            # Expand SubjectCodes if they are lists
            if "SubjectCodes" in student_grades.columns and student_grades["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                expanded_grades = pd.DataFrame({
                    "subjectCode": student_grades["SubjectCodes"].explode().values,
                    "Grade": student_grades["Grades"].explode().values
                })
            else:
                expanded_grades = student_grades[["SubjectCodes", "Grades"]].rename(
                    columns={"SubjectCodes": "subjectCode", "Grades": "Grade"}
                )

            expanded_grades['subjectCode'] = expanded_grades['subjectCode'].astype(str)

            # ✅ Loop through each curriculum
            for curriculum in curriculums:
                st.markdown(f"""
                ## 👤 Student: {logged_in_name}  
                **Reference ID:** {logged_in_refid}  
                **Course Code:** {curriculum.get('courseCode', 'N/A')}  
                **Course Name:** {curriculum.get('courseName', 'N/A')}  
                **Curriculum Year:** {curriculum.get('curriculumYear', 'N/A')}  
                """)

                # --- 🔹 Overall Rank, Total Students & Average Grade ---
                total_students = "N/A"
                rank_display = "N/A"
                avg_grade_display = "N/A"
                section = "N/A"

                if not student_grades.empty and "section" in student_grades.columns:
                    section = student_grades.iloc[0]["section"]
                    sem = student_grades.iloc[0]["SemesterID"]

                    classmates = new_grades_df[
                        (new_grades_df["SemesterID"] == sem) &
                        (new_grades_df["section"] == section)
                    ].copy()

                    if not classmates.empty:
                        avg_list = []
                        for idx, row in classmates.iterrows():
                            grades = row["Grades"]
                            if isinstance(grades, list):
                                grades_numeric = [float(g) if g is not None else 0 for g in grades]
                            else:
                                grades_numeric = [float(grades) if grades is not None else 0]
                            avg_list.append({"StudentID": row["StudentID"], "AvgGrade": sum(grades_numeric)/len(grades_numeric)})

                        avg_grades_df = pd.DataFrame(avg_list)
                        avg_grades_df["Rank"] = avg_grades_df["AvgGrade"].rank(ascending=False, method="min")
                        total_students = len(avg_grades_df)

                        user_row = avg_grades_df.loc[avg_grades_df["StudentID"] == logged_in_refid]
                        if not user_row.empty:
                            rank_display = int(user_row["Rank"].values[0])

                    # --- Calculate Average Grade for logged-in student including 0s ---
                    all_user_grades = []
                    for grades_list in student_grades["Grades"]:
                        if isinstance(grades_list, list):
                            all_user_grades.extend([float(g) if g is not None else 0 for g in grades_list])
                        else:
                            all_user_grades.append(float(grades_list) if grades_list is not None else 0)

                    if all_user_grades:
                        avg_grade_display = round(sum(all_user_grades) / len(all_user_grades), 2)
                    else:
                        avg_grade_display = 0

                st.markdown(f"**Section:** {section} | **Total Students:** {total_students} | **Your Rank:** {rank_display} / {total_students} | **Average Grade:** {avg_grade_display}")

                # --- Show curriculum subjects ---
                subjects = curriculum.get("subjects", [])
                if not subjects:
                    st.info("No subjects found for this curriculum.")
                    continue

                subj_df = pd.DataFrame(subjects)
                subj_df['subjectCode'] = subj_df['subjectCode'].astype(str)

                merged_df = subj_df.merge(
                    expanded_grades,
                    on="subjectCode",
                    how="left"
                )
                merged_df['Grade'] = merged_df['Grade'].fillna("")

                grouped = merged_df.groupby(["yearLevel", "semester"])

                for (year, sem), group in grouped:
                    st.subheader(f"📚 Year {year} - Semester {sem}")
                    columns_to_show = ["subjectCode", "subjectName", "Grade", "lec", "lab", "units", "prerequisite"]
                    group = group[[c for c in columns_to_show if c in group.columns]]
                    group = group.rename(columns={
                        "subjectCode": "Subject Code",
                        "subjectName": "Subject Name",
                        "lec": "Lec",
                        "lab": "Lab",
                        "units": "Units",
                        "prerequisite": "Prerequisite",
                        "Grade": "Grade"
                    })

                    st.dataframe(group, use_container_width=True)

                st.markdown("---")

            # --- 📄 Generate Curriculum PDF ---
            def generate_curriculum_pdf():
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                styles = getSampleStyleSheet()
                elements = []

                students = pd.read_pickle("pkl/new_students.pkl")
                students_df = pd.DataFrame(students)
                student_info_pdf = students_df[students_df["_id"] == logged_in_refid]

                if not student_info_pdf.empty:
                    course = student_info_pdf.iloc[0].get("Course", "N/A")
                    year_level = student_info_pdf.iloc[0].get("YearLevel", "N/A")
                else:
                    course = user_data.get("Course", "N/A")
                    year_level = user_data.get("YearLevel", "N/A")

                elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                elements.append(Paragraph(f"Course: {course}", styles["Normal"]))
                elements.append(Paragraph(f"Year Level: {year_level}", styles["Normal"]))
                elements.append(Spacer(1, 12))

                wrap_style = ParagraphStyle(name="TableCell", fontSize=7, leading=8, alignment=TA_LEFT)

                for curriculum in curriculums:
                    elements.append(Paragraph(f"<b>Course Code:</b> {curriculum.get('courseCode', 'N/A')}", styles["Normal"]))
                    elements.append(Paragraph(f"<b>Curriculum Year:</b> {curriculum.get('curriculumYear', 'N/A')}", styles["Normal"]))

                    # --- Add Section, Total Students, Rank & Average Grade ---
                    elements.append(Paragraph(
                        f"Section: {section} | Total Students: {total_students} | Your Rank: {rank_display} / {total_students} | Average Grade: {avg_grade_display}",
                        styles["Normal"]
                    ))
                    elements.append(Spacer(1, 12))

                    subjects = curriculum.get("subjects", [])
                    if not subjects:
                        elements.append(Paragraph("No subjects found for this curriculum.", styles["Normal"]))
                        continue

                    subj_df = pd.DataFrame(subjects)
                    subj_df['subjectCode'] = subj_df['subjectCode'].astype(str)
                    merged_df = subj_df.merge(expanded_grades, on="subjectCode", how="left")
                    merged_df['Grade'] = merged_df['Grade'].fillna("")

                    grouped = merged_df.groupby(["yearLevel", "semester"])
                    for (year, sem), group in grouped:
                        elements.append(Paragraph(f"📚 Year {year} - Semester {sem}", styles["Heading3"]))
                        elements.append(Spacer(1, 6))

                        columns_to_show = ["subjectCode", "subjectName", "Grade", "lec", "lab", "units", "prerequisite"]
                        group = group[[c for c in columns_to_show if c in group.columns]]
                        group = group.rename(columns={
                            "subjectCode": "Code",
                            "subjectName": "Subject Name",
                            "lec": "Lec",
                            "lab": "Lab",
                            "units": "Units",
                            "prerequisite": "Prereq",
                            "Grade": "Grade"
                        })

                        data = [list(group.columns)]
                        for row in group.values.tolist():
                            row[1] = Paragraph(str(row[1]), wrap_style)
                            if len(row) >= 7:
                                row[6] = Paragraph(str(row[6]), wrap_style)
                            data.append(row)

                        table = Table(data, repeatRows=1, colWidths=[55, 160, 45, 30, 30, 35, 90])
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (0, -1), "CENTER"),
                            ("ALIGN", (2, 0), (-2, -1), "CENTER"),
                            ("ALIGN", (1, 1), (1, -1), "LEFT"),
                            ("ALIGN", (6, 1), (6, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 8),
                            ("FONTSIZE", (0, 1), (-1, -1), 7),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]))
                        elements.append(table)
                        elements.append(Spacer(1, 12))

                conclusion_text = """
                This curriculum report shows all enrolled subjects, their corresponding grades, 
                and subject details (units, lecture, lab, and prerequisites). Use this as a guide 
                for academic progress tracking.
                """
                elements.append(Paragraph("Conclusion", styles["Heading3"]))
                elements.append(Paragraph(conclusion_text, styles["Normal"]))

                doc.build(elements)
                buffer.seek(0)
                return buffer

            # --- 📌 Download Button ---
            pdf_buffer = generate_curriculum_pdf()
            st.download_button(
                "📥 Download Curriculum PDF",
                data=pdf_buffer,
                file_name=f"{logged_in_name}_Curriculum_Report.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Error loading curriculum data: {e}")


# ------------------ Version Trigger Helpers ------------------ #
def is_in_pickle_by_name(pkl_path, student_name):
    if not os.path.exists(pkl_path):
        return False
    data = pd.read_pickle(pkl_path)
    df = pd.DataFrame(data) if isinstance(data, list) else data
    if "Name" not in df.columns:
        return False
    return not df[df["Name"] == student_name].empty

def choose_dashboard_version(student_name):
    if is_in_pickle_by_name(new_student_cache, student_name):
        return "new"
    if is_in_pickle_by_name(student_cache, student_name):
        return "old"
    return "old"

# ------------------ Main Student Dashboard ------------------ #
def show_student_dashboard():
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()
    user_data = st.session_state.get("user_data", {})
    student_name = user_data.get("Name", "")
    if not student_name:
        st.error("Student name not found in session data.")
        st.stop()
    version = choose_dashboard_version(student_name)
    if version == "new":
        show_student_dashboard_new()
    else:
        show_student_dashboard_old()

# ------------------ Entry Point ------------------ #
if __name__ == "__main__":
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()


