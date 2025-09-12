
import streamlit as st
import pandas as pd
from dbconnect import *
from global_utils import pkl_data_to_df, students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache, new_subjects_cache, new_students_cache, new_grades_cache

admission_year = 2023

@st.cache_data(ttl=300)
def get_semesters_list(new_curriculum):
    """Get list of all semesters"""
    try:
        semesters_df = pkl_data_to_df(semesters_cache)

        if semesters_df is None or semesters_df.empty:
            return []

        if new_curriculum:
            semesters_df = semesters_df[
                (semesters_df["Semester"] != "Summer") &
                (
                    (semesters_df["SchoolYear"] < admission_year) |
                    ((semesters_df["SchoolYear"] == admission_year) & (semesters_df["Semester"] != "FirstSem"))
                )
            ]

        required_cols = {"SchoolYear", "Semester"}
        if not required_cols.issubset(semesters_df.columns):
            st.warning(f"Required columns {required_cols} not found in semesters data")
            return []

        # Define custom semester order
        semester_cat = pd.CategoricalDtype(
            categories=["FirstSem", "Summer", "SecondSem"],
            ordered=True
        )

        # Apply category dtype
        semesters_df["Semester"] = semesters_df["Semester"].astype(semester_cat)

        # Sort by SchoolYear (desc) then Semester (custom order asc)
        semesters_df_sorted = semesters_df.sort_values(
            ["SchoolYear", "Semester"],
            ascending=[False, True]
        )

        # Return as list of dicts
        return semesters_df_sorted[["_id", "Semester", "SchoolYear"]].to_dict("records")

    except Exception as e:
        st.error(f"Error fetching semesters: {e}")
        return []



@st.cache_data(ttl=300)
def get_subjects_by_teacher(teacher_name, is_new_curriculum = False):
    """Get subjects taught by a specific teacher"""
    try:
        if(is_new_curriculum):
            subjects_df = pkl_data_to_df(new_subjects_cache)
        else:
            subjects_df = pkl_data_to_df(subjects_cache)

        # Handle empty DataFrame
        if subjects_df is None or subjects_df.empty:
            return []

        if "Teacher" in subjects_df.columns:
            teacher_subjects = subjects_df[subjects_df["Teacher"] == teacher_name]

            if "_id" in teacher_subjects.columns:
                teacher_subjects = teacher_subjects.sort_values("_id")

            columns_to_return = ["_id", "Description", "Units", "Teacher"]
            available_columns = [col for col in columns_to_return if col in teacher_subjects.columns]

            return teacher_subjects[available_columns].to_dict("records")
        else:
            st.warning("'Teacher' column not found in subjects data")
            return []

    except Exception as e:
        st.error(f"Error fetching subjects for teacher {teacher_name}: {e}")
        return []



@st.cache_data(ttl=300)
def get_students_from_grades(is_new_curriculum, teacher_name, name=""):
    df = get_dataframe_grades(is_new_curriculum)
    if df.empty:
        return pd.DataFrame()

    students_df = pkl_data_to_df(new_students_cache if is_new_curriculum else students_cache)

    if students_df is None or students_df.empty:
        st.warning("Students data not available.")
        return pd.DataFrame()

    # Merge grades with student info
    merged = df.merge(
        students_df[["_id", "Name", "Course", "YearLevel"]],
        left_on="StudentID", right_on="_id",
        how="inner"
    )

    # Apply filters
    if name:
        merged = merged[merged["Name"].str.contains(name, case=False, na=False)]
    if teacher_name:
        merged = merged[merged["Teacher"] == teacher_name]

    # Only distinct students
    distinct_students = merged.drop_duplicates(subset=["StudentID", "Name", "Course", "YearLevel"])
    distinct_students = distinct_students.rename(columns={
        "Name": "Student",
        "Course": "Course",
        "YearLevel": "YearLevel"
    })

    return distinct_students[["StudentID", "Student", "Course", "YearLevel"]].reset_index(drop=True)

    
    
    
@st.cache_data(ttl=300)
def get_dataframe_grades(is_new_curriculum):
    """
    Flatten the 'grades' collection where SubjectCodes, Grades, Teachers are arrays.
    Returns a DataFrame with columns:
    StudentID, SubjectCode, Grade, Teacher, SemesterID
    """
    try:
        df = pkl_data_to_df(new_grades_cache if is_new_curriculum else grades_cache)

        if df is None or df.empty:
            return pd.DataFrame()

        # Ensure required columns
        required_cols = {"StudentID", "SubjectCodes", "Grades", "Teachers", "SemesterID"}
        if not required_cols.issubset(df.columns):
            st.warning(f"Missing required columns: {required_cols - set(df.columns)}")
            return pd.DataFrame()

        # Explode arrays into rows
        df_exploded = df.explode(["SubjectCodes", "Grades", "Teachers"]).reset_index(drop=True)

        # Rename for clarity
        df_exploded = df_exploded.rename(columns={
            "SubjectCodes": "SubjectCode",
            "Grades": "Grade",
            "Teachers": "Teacher"
        })

        return df_exploded[["StudentID", "SubjectCode", "Grade", "Teacher", "SemesterID"]]

    except Exception as e:
        st.error(f"Error normalizing grades: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_student_grades_by_subject_and_semester(current_faculty, semester_id=None, subject_code=None):
    """Retrieve all student grades for subjects taught by a specific teacher in a given semester"""
    try:
        # Load datasets
        grades_df = pkl_data_to_df(grades_cache)
        students_df = pkl_data_to_df(students_cache)
        subjects_df = pkl_data_to_df(subjects_cache)
        semesters_df = pkl_data_to_df(semesters_cache)

        if grades_df.empty:
            return []
        
        if subject_code is None:
            st.warning(f"Selected Subject Not Found!")
        
        if semester_id is None:
            st.warning(f"Selected Semester Not Found!")

        # Expand SubjectCodes + Grades + Teachers into rows
        grades_expanded = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])

        # Filter by teacher
        grades_expanded = grades_expanded[grades_expanded["Teachers"] == current_faculty]

        # Optional filters
        if semester_id:
            grades_expanded = grades_expanded[grades_expanded["SemesterID"] == semester_id]
        if subject_code:
            grades_expanded = grades_expanded[grades_expanded["SubjectCodes"] == subject_code]

        if grades_expanded.empty:
            st.warning("No grades available")
        # Join with students, subjects, semesters
        merged = (
            grades_expanded
            .merge(students_df, left_on="StudentID", right_on="_id", suffixes=("", "_student"))
            .merge(subjects_df, left_on="SubjectCodes", right_on="_id", suffixes=("", "_subject"))
            .merge(semesters_df, left_on="SemesterID", right_on="_id", suffixes=("", "_semester"))
        )
        merged["SubjectYearLevel"] = 0
        # Select relevant columns
        results = merged[[
            "Semester", "SchoolYear", "SubjectCodes", "Description", "Units", "Name", "Grades", "YearLevel", "StudentID" , "Course", "SubjectYearLevel"
        ]].rename(columns={
            "Semester": "semester",
            "SchoolYear": "schoolYear",
            "SubjectCodes": "subjectCode",
            "Description": "subjectDescription",
            "Units": "units",
            "Name": "studentName",
            "Grades": "grade"
        })

        # Sort like Mongo pipeline
        results = results.sort_values(
            by=["schoolYear", "semester", "subjectCode", "studentName"],
            ascending=[False, True, True, True]
        )

        return results.to_dict("records")

    except Exception as e:
        st.error(f"Error querying grades: {e}")
        return []
    
@st.cache_data(ttl=300)
def get_new_student_grades_by_subject_and_semester(current_faculty, semester_id=None, subject_code=None):
    try:
        admission_year = 2022
        # Load datasets
        students_df = pkl_data_to_df(new_students_cache)
        subjects_df = pkl_data_to_df(new_subjects_cache)
        semesters_df = pkl_data_to_df(semesters_cache)
        curriculums_df = pkl_data_to_df(curriculums_cache)
        grades_df = pkl_data_to_df(new_grades_cache)
        mapping = {
            "FirstSem": 1,
            "SecondSem": 2,
            "Summer": 3
        }
        
        year_map = {
        1: "1st Year",
        2: "2nd Year",
        3: "3rd Year",
        4: "4th Year",
        5: "5th Year",
    }


        if curriculums_df.empty or students_df.empty or subjects_df.empty or semesters_df.empty:
            return []

        # --- Step 1: Expand curriculum subjects
        curriculum_subjects = curriculums_df.explode("subjects").reset_index(drop=True)
        curriculum_subjects = pd.concat(
            [curriculum_subjects.drop(columns=["subjects"]), curriculum_subjects["subjects"].apply(pd.Series)],
            axis=1
        )
        
        if subject_code is None:
            st.warning(f"Selected Subject Not Found!")
        
        if semester_id is None:
            st.warning(f"Selected Semester Not Found!")

        # Filter curriculum for this subject
        subject_curriculum = curriculum_subjects[curriculum_subjects["subjectCode"] == subject_code]
        if subject_curriculum.empty:
            st.warning(f"Subject {subject_code} not found in curriculum")
            return []

        subject_year = subject_curriculum["yearLevel"].iloc[0]
        subject_sem = subject_curriculum["semester"].iloc[0]

        # --- Step 2: Find the target semester info
        semester_row = semesters_df[semesters_df["_id"] == semester_id]
        if semester_row.empty:
            st.warning(f"Semester ID {semester_id} not found")
            return []

        target_sy = semester_row["SchoolYear"].iloc[0]
        target_semester = semester_row["Semester"].iloc[0]
        target_sem = mapping.get(target_semester, 0)
        
        if target_sy > admission_year and not (target_sy == admission_year + 1 and target_sem == 2):
            st.warning(f"⚠️ No student admissions have been recorded for the selected semester.")
        
        if target_sem != subject_sem:
            st.warning(f"Subject not Found in this selected semester!")
            return []
        
        
        
        studentYearLevel = 0
        if target_sem == 1: 
            studentYearLevel = admission_year-target_sy+subject_year
        else:
            studentYearLevel = admission_year-target_sy+subject_year+1

        
        if studentYearLevel <= 0 or studentYearLevel > 4:
            print(f"Invalid Student's Year Level of {subject_year}")
            st.warning(f"Selected Semester has No Students Enrolled for Year Level:  {year_map.get(subject_year,"")}")
            # st.warning(f"No Students Admitted for this Year Level {subject_year}")
            return []
        
        filtered_students = students_df[students_df["YearLevel"] == studentYearLevel]
        
        if filtered_students.empty:
            st.warning(f"Selected Semester has No Students Enrolled for Year Level:  {year_map.get(studentYearLevel,"")}")
            return []
        
        students_with_curriculum = (
            subject_curriculum
            .merge(filtered_students,left_on=["courseName"], right_on=["Course"],how="left")
            .merge(subjects_df,left_on=["subjectCode"],right_on=["_id"],how="inner")
        )
        
        semester_info = semester_row.head(1).to_dict("records")[0]
        for col, val in semester_info.items():
            if(col == "_id"):
                students_with_curriculum["SemesterID"] = val
            students_with_curriculum[col] = val
        
        students_with_curriculum = students_with_curriculum.rename(
            columns={"_id_x": "CurriculumID", "_id_y": "StudentID", "yearLevel": "SubjectYearLevel"}
        ).drop(columns=["courseName","_id"])

        grades_flat = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])

        grades_flat = grades_flat.rename(columns={
            "StudentID": "StudentID",
            "SubjectCodes": "subjectCode",
            "Grades": "Grade",
            "Teachers": "Teacher"
        }).reset_index(drop=True)
        
        
        curriculum_with_grades = students_with_curriculum.merge(
            grades_flat,
            on=["StudentID", "subjectCode", "SemesterID"], 
            how="left"
        )
        curriculum_with_grades = curriculum_with_grades.rename(
            columns={"_id": "GradeID"}
        )

        curriculum_with_grades["Grade"] = curriculum_with_grades["Grade"].fillna("")
        results = curriculum_with_grades[[
            "Semester", "SchoolYear", "YearLevel", "subjectCode", "Description", "Units",
            "Name", "Grade", "StudentID", "Course", "SubjectYearLevel"
        ]].rename(columns={
            "Semester": "semester",
            "SchoolYear": "schoolYear",
            "Description": "subjectDescription",
            "Units": "units",
            "Name": "studentName",
            "Grade": "grade"
        })
        
        results = results.sort_values(
            by=["semester", "YearLevel", "subjectCode", "studentName"],
            ascending=[True, True, True, True]
        )
        
        return results.to_dict("records")

    except Exception as e:
        st.error(f"Error querying students: {e}")
        return []



def get_semester_from_curriculum(curriculum_year, semesters_df):
    if not curriculum_year or curriculum_year == "" or semesters_df.empty:
        return None

    start_year, end_year = map(int, curriculum_year.split("-"))

    # First semester belongs to the start year
    first_sem = semesters_df[
        (semesters_df["SchoolYear"] == start_year) & (semesters_df["Semester"] == "FirstSem")
    ]

    # Second semester belongs to the end year
    second_sem = semesters_df[
        (semesters_df["SchoolYear"] == end_year) & (semesters_df["Semester"] == "SecondSem")
    ]

    semesters_list = first_sem.to_dict("records") + second_sem.to_dict("records")
    semesters_list = sorted(semesters_list, key=lambda x: x["SchoolYear"], reverse=True)
    return semesters_list
    
def get_active_curriculum(new_curriculum):
    if new_curriculum:
        curriculum_df = pkl_data_to_df(curriculums_cache)

        if curriculum_df is None or curriculum_df.empty:
            return ""

        curriculum_df = curriculum_df.sort_values("curriculumYear", ascending=False).head(1)
        return curriculum_df["curriculumYear"].iloc[0]
    else:
        return ""

def get_semester(Semester, SchoolYear):
    semesters_df = pkl_data_to_df(semesters_cache)
    semesters_df = semesters_df[
        (semesters_df["Semester"] == Semester) & (semesters_df["SchoolYear"] == SchoolYear)
    ]
    return semesters_df








database = db_connect()

@st.cache_data(ttl=300)
def get_new_student_grades_from_db_by_subject_and_semester(current_faculty, semester_id=None, subject_code=None):
    try:
        grades_col = database["new_grades"]
        grades = grades_col.find({"SemesterID": semester_id},{})
        grades_data = list(grades)
        grades_df = pd.DataFrame(grades_data) if grades_data else pd.DataFrame()
        
        admission_year = 2022
        # Load datasets
        students_df = pkl_data_to_df(new_students_cache)
        subjects_df = pkl_data_to_df(new_subjects_cache)
        semesters_df = pkl_data_to_df(semesters_cache)
        curriculums_df = pkl_data_to_df(curriculums_cache)
        # grades_df = pkl_data_to_df(new_grades_cache)
        mapping = {
            "FirstSem": 1,
            "SecondSem": 2,
            "Summer": 3
        }
        
        year_map = {
        1: "1st Year",
        2: "2nd Year",
        3: "3rd Year",
        4: "4th Year",
        5: "5th Year",
    }


        if curriculums_df.empty or students_df.empty or subjects_df.empty or semesters_df.empty:
            return []

        # --- Step 1: Expand curriculum subjects
        curriculum_subjects = curriculums_df.explode("subjects").reset_index(drop=True)
        curriculum_subjects = pd.concat(
            [curriculum_subjects.drop(columns=["subjects"]), curriculum_subjects["subjects"].apply(pd.Series)],
            axis=1
        )
        
        if subject_code is None:
            st.warning(f"Selected Subject Not Found!")
        
        if semester_id is None:
            st.warning(f"Selected Semester Not Found!")

        # Filter curriculum for this subject
        subject_curriculum = curriculum_subjects[curriculum_subjects["subjectCode"] == subject_code]
        if subject_curriculum.empty:
            st.warning(f"Subject {subject_code} not found in curriculum")
            return []

        subject_year = subject_curriculum["yearLevel"].iloc[0]
        subject_sem = subject_curriculum["semester"].iloc[0]

        # --- Step 2: Find the target semester info
        semester_row = semesters_df[semesters_df["_id"] == semester_id]
        if semester_row.empty:
            st.warning(f"Semester ID {semester_id} not found")
            return []

        target_sy = semester_row["SchoolYear"].iloc[0]
        target_semester = semester_row["Semester"].iloc[0]
        target_sem = mapping.get(target_semester, 0)
        
        if target_sy > admission_year and not (target_sy == admission_year + 1 and target_sem == 2):
            st.warning(f"⚠️ No student admissions have been recorded for the selected semester.")
        
        if target_sem != subject_sem:
            st.warning(f"Subject not Found in this selected semester!")
            return []
        
        
        
        studentYearLevel = 0
        if target_sem == 1: 
            studentYearLevel = admission_year-target_sy+subject_year
        else:
            studentYearLevel = admission_year-target_sy+subject_year+1

        
        if studentYearLevel <= 0 or studentYearLevel > 4:
            print(f"Invalid Student's Year Level of {subject_year}")
            st.warning(f"Selected Semester has No Students Enrolled for Year Level:  {year_map.get(subject_year,"")}")
            # st.warning(f"No Students Admitted for this Year Level {subject_year}")
            return []
        
        filtered_students = students_df[students_df["YearLevel"] == studentYearLevel]
        
        if filtered_students.empty:
            st.warning(f"Selected Semester has No Students Enrolled for Year Level:  {year_map.get(studentYearLevel,"")}")
            return []
        
        students_with_curriculum = (
            subject_curriculum
            .merge(filtered_students,left_on=["courseName"], right_on=["Course"],how="left")
            .merge(subjects_df,left_on=["subjectCode"],right_on=["_id"],how="inner")
        )
        
        semester_info = semester_row.head(1).to_dict("records")[0]
        for col, val in semester_info.items():
            if(col == "_id"):
                students_with_curriculum["SemesterID"] = val
            students_with_curriculum[col] = val
        
        students_with_curriculum = students_with_curriculum.rename(
            columns={"_id_x": "CurriculumID", "_id_y": "StudentID", "yearLevel": "SubjectYearLevel"}
        ).drop(columns=["courseName","_id"])

        grades_flat = grades_df.explode(["SubjectCodes", "Grades", "Teachers"])

        grades_flat = grades_flat.rename(columns={
            "StudentID": "StudentID",
            "SubjectCodes": "subjectCode",
            "Grades": "Grade",
            "Teachers": "Teacher"
        }).reset_index(drop=True)
        
        
        curriculum_with_grades = students_with_curriculum.merge(
            grades_flat,
            on=["StudentID", "subjectCode", "SemesterID"], 
            how="left"
        )
        curriculum_with_grades = curriculum_with_grades.rename(
            columns={"_id": "GradeID"}
        )

        curriculum_with_grades["Grade"] = curriculum_with_grades["Grade"].fillna("")
        results = curriculum_with_grades[[
            "Semester", "SchoolYear", "YearLevel", "subjectCode", "Description", "Units",
            "Name", "Grade", "StudentID", "Course", "SubjectYearLevel"
        ]].rename(columns={
            "Semester": "semester",
            "SchoolYear": "schoolYear",
            "Description": "subjectDescription",
            "Units": "units",
            "Name": "studentName",
            "Grade": "grade"
        })
        
        results = results.sort_values(
            by=["semester", "YearLevel", "subjectCode", "studentName"],
            ascending=[True, True, True, True]
        )
        
        return results.to_dict("records")

    except Exception as e:
        st.error(f"Error querying students: {e}")
        return []