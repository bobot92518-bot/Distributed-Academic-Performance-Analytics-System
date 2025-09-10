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
from matplotlib.patches import Patch


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

            # Compute average grade per subject across all students (format only AverageGrade)
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
                        else "🔵" if row["Grade"] < float(row["AverageGrade"])
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
        with tab4:
            df = pd.DataFrame(grades)
            df = df.drop(columns=["_id", "StudentID", "SemesterID"], errors="ignore")
            if "Semester" in df.columns and "SchoolYear" in df.columns:
                grouped = df.groupby(["SchoolYear", "Semester"])
                subjects_df = get_subjects()
                cols = st.columns(3)
                i = 0
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
                    for bar, grade in zip(bars, expanded_df["Grade"]):
                        ax.text(bar.get_x() + bar.get_width() / 3, bar.get_height() + 1,
                                f"{grade:.0f}", ha="center", fontsize=8)
                    with cols[i % 3]:
                        st.pyplot(fig)
                    i += 1
    
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

    # ---------------- Tab 1 ----------------
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

                    # --- Student Info ---
                    elements.append(Paragraph(f"Student Name: {logged_in_name}", styles["Heading2"]))
                    elements.append(Paragraph(f"Reference ID: {logged_in_refid}", styles["Normal"]))
                    elements.append(Paragraph(f"Course: {user_data.get('Course', 'N/A')}", styles["Normal"]))
                    elements.append(Paragraph(f"Year Level: {user_data.get('YearLevel', 'N/A')}", styles["Normal"]))

                    if semester_avgs:
                        total_avg = sum(v for _, v in semester_avgs) / len(semester_avgs)
                        elements.append(Paragraph(f"Total Average: {total_avg:.2f}", styles["Normal"]))
                    elements.append(Spacer(1, 12))

                    # (rest of PDF code here...)

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

# --- Group by SchoolYear + Semester ---
            if "SchoolYear" in grades_df.columns and "Semester" in grades_df.columns:
                grouped = grades_df.groupby(["SchoolYear", "Semester"])

                for (sy, sem), sem_df in grouped:
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

                    # Add status
                    expanded["Status"] = expanded["Grade"].apply(
                        lambda x: "PASSED" if pd.to_numeric(x, errors="coerce") >= 75 else "FAILED"
                    )

                    # Collect failed rows
                    failed_rows = expanded[expanded["Status"] == "FAILED"]
                    if not failed_rows.empty:
                        failed_subjects.append(failed_rows)

            # ✅ Combine all failed into one table
            if failed_subjects:
                failed_df = pd.concat(failed_subjects, ignore_index=True)

                # Reorder + uppercase
                failed_df = failed_df[["SchoolYear", "Semester", "SubjectCode", "subjectName", "units", "Teacher", "Grade", "Status"]]
                failed_df.rename(columns=str.upper, inplace=True)

                # Highlight failed
                def highlight_failed(val):
                    if val == "FAILED":
                        return "color: red; font-weight: bold;"
                    return ""

                styled_failed = failed_df.style.applymap(highlight_failed, subset=["STATUS"])

                st.subheader("❌ All Failed Subjects")
                st.dataframe(styled_failed, use_container_width=True)
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

            # ✅ Compute class average grades per subject (all students)
            all_subject_grades = []
            for _, row in grades_df.iterrows():
                if isinstance(row["SubjectCodes"], list):
                    for subj, grade in zip(row["SubjectCodes"], row["Grades"]):
                        all_subject_grades.append({"SubjectCode": subj, "Grade": grade})
                else:
                    all_subject_grades.append({"SubjectCode": row["SubjectCodes"], "Grade": row["Grades"]})

            all_subject_grades_df = pd.DataFrame(all_subject_grades)
            all_subject_grades_df["Grade"] = pd.to_numeric(all_subject_grades_df["Grade"], errors="coerce")

            subject_avg_df = (
                all_subject_grades_df.groupby("SubjectCode")["Grade"]
                .mean()
                .reset_index()
                .rename(columns={"Grade": "ClassAverage"})
            )
            subject_avg_df["ClassAverage"] = subject_avg_df["ClassAverage"].round(2)  # ✅ 2 decimals only

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

                # --- Group by SchoolYear + Semester ---
                if "SchoolYear" in student_grades_df.columns and "Semester" in student_grades_df.columns:
                    grouped = student_grades_df.groupby(["SchoolYear", "Semester"])

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

                        # ✅ Merge with curriculum subjects
                        expanded = expanded.merge(
                            subjects_df[["subjectCode", "subjectName", "units"]],
                            left_on="SubjectCode",
                            right_on="subjectCode",
                            how="left"
                        ).drop(columns=["subjectCode"])

                        # ✅ Merge with class average per subject
                        expanded = expanded.merge(
                            subject_avg_df,
                            on="SubjectCode",
                            how="left"
                        )

                        # ✅ Add comparison column
                        expanded["Comparison"] = expanded.apply(
                            lambda row: (
                                "🟢" if row["Grade"] > row["ClassAverage"]
                                else "🔵 " if row["Grade"] == row["ClassAverage"]
                                else "🔴 "
                            ),
                            axis=1
                        )

                        # ✅ Reorder columns
                        expanded = expanded[["SubjectCode", "subjectName", "units", "Teacher", "Grade", "ClassAverage", "Comparison"]]

                        # ✅ Rename to ALL CAPS
                        expanded.rename(columns=str.upper, inplace=True)

                        # Show table
                        st.dataframe(expanded, use_container_width=True)
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

                                    # ✅ Merge with curriculum subjects for names
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

            except Exception as e:
                st.error(f"Error loading data: {e}")


    with tab5:
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


