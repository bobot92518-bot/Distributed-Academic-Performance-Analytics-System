import streamlit as st
import pandas as pd
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import matplotlib.pyplot as plt
from reportlab.platypus import Image
# ------------------ Paths to Pickle Files ------------------ #
student_cache = "pkl/students.pkl"
grades_cache = "pkl/grades.pkl"
semesters_cache = "pkl/semesters.pkl"
subjects_cache = "pkl/subjects.pkl"

# ------------------ Helper Functions ------------------ #
def get_student_info(student_name):
    """Fetch student info from pickle by student name"""
    if not os.path.exists(student_cache):
        st.error("Student cache file not found.")
        st.stop()

    students = pd.read_pickle(student_cache)
    students_df = pd.DataFrame(students) if isinstance(students, list) else students
    match = students_df[students_df["Name"] == student_name]
    return match.iloc[0].to_dict() if not match.empty else None

def get_student_grades(student_id):
    """Fetch grades of a student by their student_id and join with semesters"""
    if not os.path.exists(grades_cache) or not os.path.exists(semesters_cache):
        st.error("Grades or semesters cache file not found.")
        st.stop()

    grades = pd.read_pickle(grades_cache)
    semesters = pd.read_pickle(semesters_cache)

    grades_df = pd.DataFrame(grades) if isinstance(grades, list) else grades
    sem_df = pd.DataFrame(semesters) if isinstance(semesters, list) else semesters

    student_grades = grades_df[grades_df["StudentID"] == student_id].copy()

    # Attach Semester + SchoolYear from semesters
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

# ------------------ Self-Assessment: Data Helpers ------------------ #
def _expand_subject_rows(grades_records):
    """Expand per-semester records to per-subject rows with semester labels."""
    if not grades_records:
        return pd.DataFrame([])

    df = pd.DataFrame(grades_records)
    if df.empty:
        return df

    # Ensure required columns exist
    for col in ["SubjectCodes", "Teachers", "Grades", "Semester", "SchoolYear", "SemesterID"]:
        if col not in df.columns:
            df[col] = None

    # Build a semester label
    df["SemesterLabel"] = df.apply(
        lambda r: f"{r.get('SchoolYear', '')} - Sem {r.get('Semester', '')}", axis=1
    )

    # If lists, explode; otherwise, normalize single values
    if df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
        exp = pd.DataFrame({
            "SubjectCode": df["SubjectCodes"].explode().values,
            "Teacher": df["Teachers"].explode().values,
            "Description": df["Description"].explode().values,
            "Grade": df["Grades"].explode().values,
            "SemesterID": df["SemesterID"].explode().values if df["SemesterID"].apply(lambda x: isinstance(x, list)).any() else df["SemesterID"].values,
            "SemesterLabel": df["SemesterLabel"].explode().values if df["SemesterLabel"].apply(lambda x: isinstance(x, list)).any() else df["SemesterLabel"].values,
        })
    else:
        exp = df.rename(columns={
            "SubjectCodes": "SubjectCodes",
            "Teachers": "Teacher",
            "Grades": "Grade",
        })[["SubjectCodes", "Teacher", "Grade", "SemesterID", "SemesterLabel"]]

    # Coerce numeric grades
    exp["NumericGrade"] = pd.to_numeric(exp["Grade"], errors="coerce")
    return exp

def _compute_student_trend(grades_records):
    """Return DataFrame with semester-level averages for the student."""
    exp = _expand_subject_rows(grades_records)
    if exp.empty:
        return pd.DataFrame([])

    trend = (
        exp.dropna(subset=["NumericGrade"]) 
           .groupby(["SemesterID", "SemesterLabel"], dropna=False)["NumericGrade"]
           .mean()
           .reset_index()
           .rename(columns={"NumericGrade": "StudentAverage"})
    )
    return trend
def get_subjects():
    """Fetch subjects (with descriptions) from pickle."""
    if not os.path.exists(subjects_cache):
        st.error("Subjects cache file not found.")
        st.stop()

    subjects = pd.read_pickle(subjects_cache)
    subjects_df = pd.DataFrame(subjects) if isinstance(subjects, list) else subjects
    return subjects_df[["_id", "Description"]].drop_duplicates()
def _compute_class_trend():
    """Compute class average per semester across all students."""
    if not os.path.exists(grades_cache) or not os.path.exists(semesters_cache):
        return pd.DataFrame([])

    all_grades = pd.read_pickle(grades_cache)
    semesters = pd.read_pickle(semesters_cache)

    grades_df = pd.DataFrame(all_grades) if isinstance(all_grades, list) else all_grades
    sem_df = pd.DataFrame(semesters) if isinstance(semesters, list) else semesters

    if grades_df.empty:
        return pd.DataFrame([])

    # Join semester label
    merged = grades_df.copy()
    merged["Semester"] = ""
    merged["SchoolYear"] = ""
    for idx, row in merged.iterrows():
        sem_id = row.get("SemesterID")
        match = sem_df[sem_df["_id"] == sem_id]
        if not match.empty:
            merged.at[idx, "Semester"] = match.iloc[0].get("Semester", "")
            merged.at[idx, "SchoolYear"] = match.iloc[0].get("SchoolYear", "")

    merged_records = merged.to_dict(orient="records")
    exp = _expand_subject_rows(merged_records)
    if exp.empty:
        return pd.DataFrame([])

    class_trend = (
        exp.dropna(subset=["NumericGrade"]) 
           .groupby(["SemesterID", "SemesterLabel"], dropna=False)["NumericGrade"]
           .mean()
           .reset_index()
           .rename(columns={"NumericGrade": "ClassAverage"})
    )
    return class_trend

def _compute_pass_fail_summary(grades_records, pass_threshold=75):
    """Return counts of Passed/Failed/Incomplete based on numeric grades and NaNs."""
    exp = _expand_subject_rows(grades_records)
    if exp.empty:
        return pd.Series({"Passed": 0, "Failed": 0, "Incomplete": 0})

    status = pd.Series(index=exp.index, dtype="object")
    status[(exp["NumericGrade"].notna()) & (exp["NumericGrade"] >= pass_threshold)] = "Passed"
    status[(exp["NumericGrade"].notna()) & (exp["NumericGrade"] < pass_threshold)] = "Failed"
    status[exp["NumericGrade"].isna()] = "Incomplete"
    return status.value_counts().reindex(["Passed", "Failed", "Incomplete"]).fillna(0).astype(int)

def _compute_subject_vs_class(grades_records):
    """Return DataFrame with student's subject averages vs class averages per subject."""
    exp_student = _expand_subject_rows(grades_records)
    if exp_student.empty:
        return pd.DataFrame([])

    # Student per-subject average
    stu = (
        exp_student.dropna(subset=["NumericGrade"]) 
                 .groupby("SubjectCode")["NumericGrade"].mean()
                 .reset_index()
                 .rename(columns={"NumericGrade": "StudentAvg"})
    )

    # Class per-subject average (across all semesters)
    if not os.path.exists(grades_cache):
        return stu

    all_grades = pd.read_pickle(grades_cache)
    grades_df = pd.DataFrame(all_grades) if isinstance(all_grades, list) else all_grades
    if grades_df.empty:
        return stu

    exp_all = _expand_subject_rows(grades_df.to_dict(orient="records"))
    if exp_all.empty:
        return stu

    cls = (
        exp_all.dropna(subset=["NumericGrade"]) 
              .groupby("SubjectCode")["NumericGrade"].mean()
              .reset_index()
              .rename(columns={"NumericGrade": "ClassAvg"})
    )

    out = pd.merge(stu, cls, on="SubjectCode", how="left")
    return out

# ------------------ Self-Assessment: UI ------------------ #

# ------------------ Main Dashboard Function ------------------ #
def show_student_dashboard_old():
    """Original student dashboard implementation"""
    
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()

    # Get student name from session state (using only Name field)
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
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Performance Trend Over Time",
            "Subject Difficulty Ratings",
            "Comparison with Class Average",
            "Passed vs Failed Summary",
            "New Curriculum"
        ])

        # 📌 Tab 1 = Transcript table + Trend chart
        with tab1:
            col1, col2 = st.columns(2)

            # --- Prepare DataFrame ---
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

            transcript_data = {}
            semester_avgs = []  # store semester averages for plotting

            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"])
                
                # 🔑 Load subjects with Description + Units
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

                    # ✅ Ensure Description and Units always exist
                    if "Description" not in expanded_df.columns:
                        expanded_df["Description"] = "N/A"
                    if "Units" not in expanded_df.columns:
                        expanded_df["Units"] = "N/A"

                    # ✅ Reorder with Units
                    expanded_df = expanded_df[["SubjectCodes", "Units", "Description", "Teacher", "Grade"]]

                    transcript_data[f"{sy} - Semester {sem}"] = expanded_df

                    valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                    if not valid_grades.empty:
                        avg = valid_grades.mean()
                        semester_avgs.append((f"{sy} - Sem {sem}", avg))


            # ✅ Show Total Average ABOVE
            with col1:
                if semester_avgs:
                    total_avg = sum(avg for _, avg in semester_avgs) / len(semester_avgs)
                    st.metric("Total Average", f"{total_avg:.2f}")
                else:
                    total_avg = None
                    st.metric("Total Average", "N/A")

            with col2:
                st.metric("Course", student.get("Course", "N/A"))

            # --- Now show transcript tables ---
            for sem_title, expanded_df in transcript_data.items():
                st.subheader(sem_title)
                st.dataframe(expanded_df, use_container_width=True)

                # ✅ Semester Average
                valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                if not valid_grades.empty:
                    avg = valid_grades.mean()
                    st.write(f"**Semester Average: {avg:.2f}**")
                else:
                    st.write("**Semester Average: N/A**")

                # ✅ Semester Total Units
                if "Units" in expanded_df.columns:
                    total_units = pd.to_numeric(expanded_df["Units"], errors="coerce").fillna(0).sum()
                    st.write(f"**Total Units: {int(total_units)}**")
                else:
                    st.write("**Total Units: N/A**")

                st.markdown("---")

            # ✅ Line Graph after tables
            if semester_avgs:
                labels, values = zip(*semester_avgs)
                labels = list(labels)
                values = list(values)

                # ✅ Add final average as extra point on X-axis
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

            # ---------------- PDF Export ONLY in Tab 1 ---------------- #
            if transcript_data:
                if st.button("📄 Generate Report"):
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    elements = []
                    styles = getSampleStyleSheet()

                    # Title
                    elements.append(Paragraph("Academic Transcript Report", styles["Title"]))
                    elements.append(Spacer(1, 12))

                    # Student Info
                    full_name = f"{student.get('Name', '')}"
                    elements.append(Paragraph(f"<b>Student Name:</b> {full_name}", styles["Normal"]))
                    elements.append(Paragraph(f"<b>Course:</b> {student.get('Course', 'N/A')}", styles["Normal"]))
                    if total_avg is not None:
                        elements.append(Paragraph(f"<b>Total Average:</b> {total_avg:.2f}", styles["Normal"]))
                    elements.append(Spacer(1, 12))

                    # Page width for table layout
                    page_width = A4[0] - doc.leftMargin - doc.rightMargin
                    col_count = 4
                    col_widths = [page_width / col_count] * col_count

                    # Collect grades for final average
                    all_grades = []

                    for sem_title, sem_df in transcript_data.items():
                        elements.append(Paragraph(sem_title, styles["Heading2"]))

                        numeric_grades = pd.to_numeric(sem_df["Grade"], errors="coerce").dropna().tolist()
                        all_grades.extend(numeric_grades)

                        # Table data
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

                        # Semester average
                        if numeric_grades:
                            avg = sum(numeric_grades) / len(numeric_grades)
                            elements.append(Spacer(1, 6))
                            elements.append(Paragraph(f"<b>Semester Average: {avg:.2f}</b>", styles["Normal"]))
                        else:
                            elements.append(Paragraph("<b>Semester Average: N/A</b>", styles["Normal"]))

                        elements.append(Spacer(1, 12))

                    # Overall average
                    if all_grades:
                        final_avg = sum(all_grades) / len(all_grades)
                        elements.append(Paragraph(f"<b>Overall Average: {final_avg:.2f}</b>", styles["Heading2"]))
                    else:
                        final_avg = None

                    # ✅ Add line graph
                    if semester_avgs:
                        labels, values = zip(*semester_avgs)
                        labels = list(labels)
                        values = list(values)

                        plt.figure(figsize=(8, 4))
                        plt.plot(labels, values, marker="o", linestyle="-", label="Semester Average")

                        # Annotate each dot
                        for i, (x, y) in enumerate(zip(labels, values)):
                            plt.text(i, y + 1, f"{y:.2f}", ha="center", fontsize=7, color="blue")

                        # Add final average in red
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

                    # ✅ Build PDF
                    doc.build(elements)
                    buffer.seek(0)

                    st.download_button(
                        label="⬇️ Download PDF",
                        data=buffer,
                        file_name="transcript_report.pdf",
                        mime="application/pdf"
                    )
                        # Other tabs (difficulty, comparison, summary)
        with tab2:
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"])
                subjects_df = get_subjects()

                for (sy, sem), sem_df in grouped:
                    st.subheader(f"{sy} - Semester {sem}")

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

                    # Merge with subjects_df
                    expanded_df = expanded_df.merge(
                        subjects_df.rename(columns={"_id": "SubjectCodes"}),
                        on="SubjectCodes",
                        how="left"
                    )

                    # ✅ Ensure Description always exists
                    if "Description" not in expanded_df.columns:
                        expanded_df["Description"] = "N/A"

                    # Reorder columns safely
                    columns_to_show = ["SubjectCodes", "Description", "Teacher", "Grade"]
                    expanded_df = expanded_df[[c for c in columns_to_show if c in expanded_df.columns]]

                    st.dataframe(expanded_df, use_container_width=True)

                    if "Grade" in expanded_df.columns:
                        valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                        if not valid_grades.empty:
                            avg = valid_grades.mean()
                            st.write(f"**Semester Average: {avg:.2f}**")
                        else:
                            st.write("**Semester Average: N/A**")

                    st.markdown("---")

        with tab3:
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"])
                subjects_df = get_subjects()

                for (sy, sem), sem_df in grouped:
                    st.subheader(f"{sy} - Semester {sem}")

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

                    # Merge with subjects_df
                    expanded_df = expanded_df.merge(
                        subjects_df.rename(columns={"_id": "SubjectCodes"}),
                        on="SubjectCodes",
                        how="left"
                    )

                    # ✅ Ensure Description always exists
                    if "Description" not in expanded_df.columns:
                        expanded_df["Description"] = "N/A"

                    # Reorder columns safely
                    columns_to_show = ["SubjectCodes", "Description", "Teacher", "Grade"]
                    expanded_df = expanded_df[[c for c in columns_to_show if c in expanded_df.columns]]

                    st.dataframe(expanded_df, use_container_width=True)

                    if "Grade" in expanded_df.columns:
                        valid_grades = pd.to_numeric(expanded_df["Grade"], errors="coerce").dropna()
                        if not valid_grades.empty:
                            avg = valid_grades.mean()
                            st.write(f"**Semester Average: {avg:.2f}**")
                        else:
                            st.write("**Semester Average: N/A**")

                    st.markdown("---")
                    
        with tab4:
           if "Semester" in df.columns and "SchoolYear" in df.columns:
            grouped = df.groupby(["SchoolYear", "Semester"])
            subjects_df = get_subjects()

            cols = st.columns(3)  # ✅ create two columns
            i = 0  # counter to switch between col1 and col2

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

                # Merge with subjects info
                expanded_df = expanded_df.merge(
                    subjects_df.rename(columns={"_id": "SubjectCodes"}),
                    on="SubjectCodes",
                    how="left"
                )

                if "Description" not in expanded_df.columns:
                    expanded_df["Description"] = "N/A"

                expanded_df = expanded_df[["SubjectCodes", "Description", "Teacher", "Grade"]]

                # ✅ Convert grades to numeric
                expanded_df["Grade"] = pd.to_numeric(expanded_df["Grade"], errors="coerce")

                # ✅ Plot bar graph
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

                # ✅ Annotate bars
                for bar, grade in zip(bars, expanded_df["Grade"]):
                    ax.text(bar.get_x() + bar.get_width() / 3, bar.get_height() + 1,
                            f"{grade:.0f}", ha="center", fontsize=8)

                # ✅ Display two graphs per row
                with cols[i % 3]:
                    st.pyplot(fig)

                i += 1
        with tab5:
            st.subheader("📘 Curriculum with Grades")

            try:
                # Load curriculum
                curriculums = pd.read_pickle("pkl/curriculums.pkl")
                if isinstance(curriculums, pd.DataFrame):
                    curriculums = curriculums.to_dict(orient="records")

                # Load grades
                df = pd.DataFrame(grades)
                df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")

                # Expand grades if subject codes are lists
                if "SubjectCodes" in df.columns and df["SubjectCodes"].apply(lambda x: isinstance(x, list)).any():
                    expanded_grades = pd.DataFrame({
                        "subjectCode": df["SubjectCodes"].explode().values,   # 🔑 match column name with curriculum
                        "Grade": df["Grades"].explode().values
                    })
                else:
                    expanded_grades = df[["SubjectCodes", "Grades"]].rename(
                        columns={"SubjectCodes": "subjectCode", "Grades": "Grade"}  # 🔑 align with curriculum "subjectCode"
                    )

                for curriculum in curriculums:
                    st.markdown(f"""
                    ## 🎓 {curriculum.get('courseName', 'N/A')}
                    **Course Code:** {curriculum.get('courseCode', 'N/A')}  
                    **Curriculum Year:** {curriculum.get('curriculumYear', 'N/A')}  
                    """)

                    subjects = curriculum.get("subjects", [])
                    if not subjects:
                        st.info("No subjects found for this curriculum.")
                        continue

                    # Convert curriculum subjects to DataFrame
                    subj_df = pd.DataFrame(subjects)

                    # ✅ Merge curriculum subjects with student grades by subjectCode
                    subj_df = subj_df.merge(
                        expanded_grades,
                        on="subjectCode",
                        how="left"  # keep all curriculum subjects even if no grade exists
                    )

                    # Group by yearLevel & semester
                    grouped = subj_df.groupby(["yearLevel", "semester"])

                    for (year, sem), group in grouped:
                        st.subheader(f"📚 Year {year} - Semester {sem}")

                        # Reorder columns
                        columns_to_show = [
                            "subjectCode",
                            "subjectName",
                            "Grade",
                            "lec",
                            "lab",
                            "units",
                            "prerequisite"
                        ]
                        group = group[[c for c in columns_to_show if c in group.columns]]

                        # ✅ Rename column headers
                        group = group.rename(columns={
                            "subjectCode": "Subject Code",
                            "subjectName": "Subject Name",
                            "lec": "Lec",
                            "lab": "Lab",
                            "units": "Units",
                            "prerequisite": "Prerequisite",
                            "Grade": "Grade"
                        })

                        # Display as table
                        st.dataframe(group, use_container_width=True)

                    st.markdown("---")

            except Exception as e:
                st.error(f"Error loading curriculum data: {e}")
           

def show_student_dashboard_new():
    """Enhanced faculty dashboard implementation with simplified tabs"""
    # Add version indicator
    st.info("🆕 **New Version** - Enhanced faculty dashboard with improved features")
    
    st.set_page_config(
        page_title="DAPAS - Faculty Dashboard",
        page_icon="🏫",
        layout="wide"
    )
    
    # Simplified tabs for new version
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Class List",
        "👥 Evaluation Sheet", 
        "📈 Curriculum Viewer",
        "👨‍🏫 Teacher Analysis"
    ])

    with tab1:
        st.subheader("📊 Class List")
        st.markdown("This is Sample tab for New Version")
        
    with tab2:
        

        # --- Get logged-in student ---
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

                transcript_data = {}
                semester_avgs = []

                # --- 🔹 General Grade Summary ---
                all_grades = grades_df["Grades"].explode()  # flatten list of grades
                all_grades = pd.to_numeric(all_grades, errors="coerce").dropna()

                if not all_grades.empty:
                    summary_df = pd.DataFrame([{
                        "MEAN": all_grades.mean(),
                        "MEDIAN": all_grades.median(),
                        "HIGHEST": all_grades.max(),
                        "LOWEST": all_grades.min()
                    }])

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

                    st.subheader("📊 General Grade Summary")
                    st.dataframe(styled_summary, use_container_width=True, height=80)
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

                # 📏 Wide (max width) but short height
                fig, ax = plt.subplots(figsize=(10, 2.5), dpi=120)

                # ✅ Plot line
                ax.plot(semester_labels, semester_values, linestyle="-", color="gray", zorder=1, linewidth=1)

                # ✅ Color-coded points
                for i, value in enumerate(semester_values):
                    color = "red" if value < 75 else "blue"
                    ax.scatter(i, value, color=color, s=30, zorder=2)  # smaller dots
                    ax.text(i, value + 1, f"{value:.1f}", ha="center", fontsize=7, color=color)

                # ✅ Y-axis fixed 1–100
                ax.set_ylim(1, 100)

                # ✅ Smaller fonts
                ax.set_title("📈 Semester & Final Average", fontsize=9)
                ax.set_xlabel("Semester", fontsize=8)
                ax.set_ylabel("Average", fontsize=8)
                ax.tick_params(axis="both", labelsize=7)
                ax.grid(True, linewidth=0.3)

                # ✅ Slant X-axis labels
                plt.xticks(range(len(semester_labels)), semester_labels, rotation=30, ha="right", fontsize=7)

                # ✅ Stretch width in Streamlit
                st.pyplot(fig, use_container_width=True)

                def generate_pdf():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    styles = getSampleStyleSheet()
                    elements = []

                    # --- Student Info ---
                    elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                    elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                    elements.append(Paragraph(f"Course: {user_data.get('Course', 'N/A')}", styles["Normal"]))
                    elements.append(Paragraph(f"Year Level: {user_data.get('YearLevel', 'N/A')}", styles["Normal"]))

                    if semester_avgs:
                        total_avg = sum(v for _, v in semester_avgs) / len(semester_avgs)
                        elements.append(Paragraph(f"Total Average: {total_avg:.2f}", styles["Normal"]))
                    elements.append(Spacer(1, 12))

                    # --- Add each semester table ---
                    for sem_title, sem_df in transcript_data.items():
                        elements.append(Paragraph(sem_title, styles["Heading3"]))

                        # Capitalize headers
                        headers = [h.upper() for h in sem_df.columns.tolist()]
                        table_data = [headers]

                        # Add rows with conditional formatting for Grade
                        for row in sem_df.astype(str).values.tolist():
                            row_data = []
                            for col_idx, value in enumerate(row):
                                if headers[col_idx] == "GRADE":
                                    try:
                                        grade_val = float(value)
                                        if grade_val < 75:
                                            row_data.append(Paragraph(
                                                f'<para align="center"><font color="red" size="8">{value}</font></para>',
                                                styles["Normal"]
                                            ))
                                        else:
                                            row_data.append(Paragraph(
                                                f'<para align="center" size="8">{value}</para>',
                                                styles["Normal"]
                                            ))
                                    except ValueError:
                                        row_data.append(Paragraph(
                                            f'<para align="center" size="8">{value}</para>',
                                            styles["Normal"]
                                        ))
                                else:
                                    row_data.append(Paragraph(
                                        f'<para align="center" size="8">{value}</para>',
                                        styles["Normal"]
                                    ))
                            table_data.append(row_data)

                        # ✅ Flexible column widths
                        total_width = doc.width
                        col_widths = []
                        for h in headers:
                            if h == "SUBJECTNAME":
                                col_widths.append(total_width * 0.40)  # 40% width for subject name
                            else:
                                col_widths.append(total_width * 0.60 / (len(headers) - 1))  # share remaining width

                        table = Table(table_data, colWidths=col_widths, repeatRows=1)
                        table.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.gray),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ]))
                        elements.append(table)
                        elements.append(Spacer(1, 12))

                    # --- Add graph to PDF ---
                    if semester_avgs:
                        fig, ax = plt.subplots(figsize=(6, 2.5), dpi=100)
                        semester_labels, semester_values = zip(*semester_avgs)
                        overall_avg = sum(semester_values) / len(semester_values)
                        semester_labels = list(semester_labels) + ["Final Average"]
                        semester_values = list(semester_values) + [overall_avg]

                        ax.plot(semester_labels, semester_values, linestyle="-", color="gray", linewidth=1)
                        for i, value in enumerate(semester_values):
                            color = "red" if value < 75 else "blue"
                            ax.scatter(i, value, color=color, s=25)
                            ax.text(i, value + 1, f"{value:.1f}", ha="center", fontsize=6, color=color)

                        ax.set_ylim(1, 100)
                        ax.set_title("📈 Semester & Final Average", fontsize=8)
                        ax.set_xlabel("Semester", fontsize=7)
                        ax.set_ylabel("Average", fontsize=7)
                        ax.tick_params(axis="both", labelsize=6)
                        plt.xticks(range(len(semester_labels)), semester_labels, rotation=30, ha="right", fontsize=6)
                        ax.grid(True, linewidth=0.3)

                        img_buffer = io.BytesIO()
                        plt.savefig(img_buffer, format="PNG", bbox_inches="tight")
                        plt.close(fig)
                        img_buffer.seek(0)

                        elements.append(Paragraph("Performance Graph", styles["Heading3"]))
                        elements.append(Image(img_buffer, width=doc.width, height=150))
                        elements.append(Spacer(1, 12))

                    doc.build(elements)
                    buffer.seek(0)
                    return buffer


                # --- Download button ---
                pdf_buffer = generate_pdf()
                st.download_button(
                    label="📄 Download Transcript PDF",
                    data=pdf_buffer,
                    file_name=f"{logged_in_name}_Transcript.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"❌ Error loading grades: {e}")

#   done
    with tab3:
        st.subheader("📘 Curriculum with Grades")

        try:
            # ✅ Get current logged-in user from session state
            user_data = st.session_state.get("user_data", {})
            logged_in_name = user_data.get("Name", "Unknown User")
            logged_in_refid = str(user_data.get("_id", "N/A"))

            # ✅ Load curriculum
            curriculums = pd.read_pickle("pkl/curriculums.pkl")
            if isinstance(curriculums, pd.DataFrame):
                curriculums = curriculums.to_dict(orient="records")

            # ✅ Load new_grades
            new_grades_df = pd.read_pickle("pkl/new_grades.pkl")
            if not isinstance(new_grades_df, pd.DataFrame):
                new_grades_df = pd.DataFrame(new_grades_df)

            # Optional: filter for the logged-in student
            student_grades = new_grades_df[new_grades_df['StudentID'] == int(logged_in_refid)].copy()

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

            # Ensure string type for merging
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

                subjects = curriculum.get("subjects", [])
                if not subjects:
                    st.info("No subjects found for this curriculum.")
                    continue

                # Convert curriculum subjects to DataFrame
                subj_df = pd.DataFrame(subjects)
                subj_df['subjectCode'] = subj_df['subjectCode'].astype(str)  # ensure string

                # ✅ Merge with grades
                merged_df = subj_df.merge(
                    expanded_grades,
                    on="subjectCode",
                    how="left"
                )
                merged_df['Grade'] = merged_df['Grade'].fillna("N/A")

                # ✅ Group by yearLevel & semester
                grouped = merged_df.groupby(["yearLevel", "semester"])

                for (year, sem), group in grouped:
                    st.subheader(f"📚 Year {year} - Semester {sem}")

                    columns_to_show = ["subjectCode", "subjectName", "Grade", "lec", "lab", "units", "prerequisite"]
                    group = group[[c for c in columns_to_show if c in group.columns]]

                    # Rename columns
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

        except Exception as e:
            st.error(f"Error loading curriculum data: {e}")



    with tab4:
        st.subheader("👨‍🏫 Teacher Analysis")
        st.markdown("This is Sample tab for New Version")


def show_student_dashboard():
    """Main student dashboard function with toggle between old and new implementations"""
    # Add toggle at the top left
    col1, col2 = st.columns([1, 3])
    with col1:
        use_new_version = st.toggle(
            "🆕 Toggle Dashboard Version", 
            value=True,  # Default to new version
            help="Toggle between the original dashboard and the enhanced version with improved features"
        ) 
    # Call the appropriate version based on toggle
    if use_new_version:
        show_student_dashboard_new()
    else:
        show_student_dashboard_old()

# ------------------ Entry Point ------------------ #
def main():
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()
 
