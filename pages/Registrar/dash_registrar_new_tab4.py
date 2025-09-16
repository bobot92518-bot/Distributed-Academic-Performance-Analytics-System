import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
from global_utils import load_pkl_data, pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache

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

def show_registrar_new_tab4_info(data, students_df, semesters_df, teachers_df, grades_df):
        subjects_df = data['subjects']

        st.subheader("📈 Student Grade Analytics (per Teacher)")
        st.markdown("Select a teacher, then choose a class to view analytics and students list.")

        # Prepare expanded dataframe once
        def _expand_rows(gr):
            rows = []
            grades_list = gr.get("Grades", [])
            subjects_list = gr.get("SubjectCodes", [])
            teachers_list = gr.get("Teachers", [])
            grades_list = grades_list if isinstance(grades_list, list) else [grades_list]
            subjects_list = subjects_list if isinstance(subjects_list, list) else [subjects_list]
            teachers_list = teachers_list if isinstance(teachers_list, list) else [teachers_list]
            max_len = max(len(grades_list), len(subjects_list), len(teachers_list)) if max(len(grades_list), len(subjects_list), len(teachers_list)) > 0 else 0
            for i in range(max_len):
                rows.append({
                    "StudentID": gr.get("StudentID"),
                    "SemesterID": gr.get("SemesterID"),
                    "Grade": grades_list[i] if i < len(grades_list) else None,
                    "SubjectCode": subjects_list[i] if i < len(subjects_list) else None,
                    "TeacherID": teachers_list[i] if i < len(teachers_list) else None,
                })
            return rows

        merged_base = grades_df.merge(students_df[["_id", "Name", "Course", "YearLevel"]], left_on="StudentID", right_on="_id", how="left")
        expanded_rows = []
        for _, rr in merged_base.iterrows():
            expanded_rows.extend(_expand_rows(rr))

        if not expanded_rows:
            st.warning("No grade records available.")
        else:
            df_exp = pd.DataFrame(expanded_rows)
            # Maps
            tmap = dict(zip(teachers_df["_id"], teachers_df["Teacher"])) if not teachers_df.empty else {}
            smap = dict(zip(subjects_df["_id"], subjects_df["Description"])) if not subjects_df.empty else {}
            semmap = dict(zip(semesters_df["_id"], semesters_df["Semester"])) if not semesters_df.empty else {}

            df_exp["Teacher"] = df_exp["TeacherID"].map(tmap).fillna(df_exp["TeacherID"].astype(str))
            df_exp["Subject"] = df_exp["SubjectCode"].map(smap).fillna(df_exp["SubjectCode"].astype(str))
            df_exp["Semester"] = df_exp["SemesterID"].map(semmap).fillna(df_exp["SemesterID"].astype(str))

            # Filter to valid numeric grades
            df_exp = df_exp[pd.to_numeric(df_exp["Grade"], errors="coerce").notna()].copy()
            df_exp["Grade"] = pd.to_numeric(df_exp["Grade"], errors="coerce")

            # Teacher selector (distinct)
            teacher_choices = sorted([t for t in df_exp["Teacher"].dropna().unique().tolist() if t is not None])
            sel_teacher = st.selectbox("Teacher", teacher_choices, key="tga_teacher_distinct") if teacher_choices else None

            if not sel_teacher:
                st.info("Select a teacher to view analytics.")
            else:
                df_t = df_exp[df_exp["Teacher"] == sel_teacher]
                if df_t.empty:
                    st.warning("No records for the selected teacher.")
                else:
                    # Build subject options under selected teacher
                    subject_options = sorted(df_t["Subject"].dropna().unique().tolist())
                    sel_subject = st.radio("Subject", subject_options, horizontal=False, key="tga_subject_radio") if subject_options else None

                    if not sel_subject:
                        st.info("Choose a subject to see analytics.")
                    else:
                        df_c = df_t[df_t["Subject"] == sel_subject]

                        if df_c.empty:
                            st.warning("No data for the selected class.")
                        else:
                            # Summary metrics table (mean, median, highest, lowest)
                            mean_g = df_c["Grade"].mean()
                            med_g = df_c["Grade"].median()
                            max_g = df_c["Grade"].max()
                            min_g = df_c["Grade"].min()
                            summary_df = pd.DataFrame([
                                {"Metric": "Mean", "Value": round(mean_g, 2)},
                                {"Metric": "Median", "Value": round(med_g, 2)},
                                {"Metric": "Highest", "Value": round(max_g, 2)},
                                {"Metric": "Lowest", "Value": round(min_g, 2)},
                            ])
                            st.subheader("Summary Statistics")
                            st.dataframe(summary_df, use_container_width=True, hide_index=True)

                            # Grade distribution (bar)
                            vc = df_c["Grade"].round(0).astype(int).value_counts().sort_index().reset_index()
                            vc.columns = ["Grade", "Count"]
                            fig_dist = px.bar(vc, x="Grade", y="Count", title="Grade Distribution (Rounded)")
                            fig_dist.update_layout(xaxis_title="Grade", yaxis_title="Students")
                            st.plotly_chart(fig_dist, use_container_width=True)

                            # Pass/Fail per class (bar)
                            df_c["Status"] = df_c["Grade"].apply(lambda g: "Pass" if g >= 75 else "Fail")
                            pf = df_c["Status"].value_counts().reindex(["Pass", "Fail"], fill_value=0).reset_index()
                            pf.columns = ["Status", "Count"]
                            fig_pf = px.bar(pf, x="Status", y="Count", title="Pass/Fail Counts")
                            fig_pf.update_layout(xaxis_title="Status", yaxis_title="Students")
                            st.plotly_chart(fig_pf, use_container_width=True)

                            # Students list with remarks (⭐ for pass, ❌ for fail)
                            # Join back details
                            name_map = dict(zip(students_df["_id"], students_df["Name"])) if not students_df.empty else {}
                            course_map = dict(zip(students_df["_id"], students_df["Course"])) if not students_df.empty else {}
                            year_map = dict(zip(students_df["_id"], students_df["YearLevel"])) if not students_df.empty else {}
                            df_c["StudentName"] = df_c["StudentID"].map(name_map).fillna(df_c["StudentID"].astype(str))
                            df_c["Course"] = df_c["StudentID"].map(course_map)
                            df_c["YearLevel"] = df_c["StudentID"].map(year_map)
                            df_c["Remark"] = df_c["Grade"].apply(lambda g: "⭐ Pass" if g >= 75 else "❌ Fail")
                            st.subheader("Students by Course and Year Level")
                            show_cols = ["StudentID", "StudentName", "Course", "YearLevel", "Remark"]
                            courses_in_class = [c for c in sorted(df_c["Course"].dropna().unique().tolist())]
                            for course_name in courses_in_class:
                                st.markdown(f"**Course: {course_name}**")
                                df_course = df_c[df_c["Course"] == course_name]
                                years = [y for y in sorted(df_course["YearLevel"].dropna().unique().tolist())]
                                for ylevel in years:
                                    st.markdown(f"- Year Level: {ylevel}")
                                    df_year = df_course[df_course["YearLevel"] == ylevel]
                                    st.dataframe(
                                        df_year[show_cols]
                                            .sort_values(["StudentName"], ascending=[True])
                                            .reset_index(drop=True),
                                        use_container_width=True
                                    )