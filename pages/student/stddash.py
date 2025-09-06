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
def get_student_info(username):
    """Fetch student info from pickle by username"""
    if not os.path.exists(student_cache):
        st.error("Student cache file not found.")
        st.stop()

    students = pd.read_pickle(student_cache)
    students_df = pd.DataFrame(students) if isinstance(students, list) else students
    match = students_df[students_df["username"] == username]
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
def show_student_dashboard():
    
    if 'authenticated' not in st.session_state or not st.session_state.authenticated or st.session_state.role != "student":
        st.error("Unauthorized access. Please login as Student.")
        st.stop()

    username = st.session_state.username
    student = get_student_info(username)

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
           

# ------------------ Entry Point ------------------ #
def main():
    st.set_page_config(
        page_title="DAPAS Student Dashboard",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    show_student_dashboard()
 
