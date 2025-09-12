import streamlit as st
import pandas as pd
import pymongo
import pickle
import os
from dbconnect import db_connect
from global_utils import students_cache, grades_cache, semesters_cache, subjects_cache, curriculums_cache, new_subjects_cache, new_students_cache, new_grades_cache

output_folder = "pkl"

db = db_connect()
os.makedirs(output_folder, exist_ok=True)

def reload_pkl_by_specific_collections(collection_name): 
    if collection_name != "":
        collection = db[collection_name]
        documents = list(collection.find({}))  # Fetch all documents

        # Define pickle file path
        file_path = os.path.join(output_folder, f"{collection_name}.pkl")

        # Save to pickle
        with open(file_path, "wb") as f:
            pickle.dump(documents, f)

        print(f"Saved {len(documents)} documents from '{collection_name}' to '{file_path}'")
        print("All collections have been pickled successfully!")
    else:
        print("No Collection Name!")

def save_new_student_grades(student_id, subject_code, semester_id, grade, teacher):
    student_id = int(student_id)
    semester_id = int(semester_id)
    grade = float(grade) if grade is not None else None
    try:
        if not all([student_id, subject_code, semester_id]) or grade is None or not teacher:
            raise ValueError("StudentID, SubjectCode, SemesterID, Grade, and Teacher are all required")
        
        if not isinstance(grade, (int, float)) or grade < 0 or grade > 100:
            raise ValueError("Grade must be a number between 0 and 100")
        
        
        new_grades_col = db["new_grades"]
        
        existing_record = new_grades_col.find_one({
            "StudentID": student_id, 
            "SemesterID": semester_id
        })
        
        if not existing_record:
            # Create new record
            new_record = {
                "StudentID": student_id,
                "SemesterID": semester_id,
                "SubjectCodes": [subject_code],
                "Grades": [grade],
                "Teachers": [teacher]
            }
            result = new_grades_col.insert_one(new_record)
            reload_pkl_by_specific_collections(collection_name = "new_grades")
            return {
                "success": True, 
                "message": f"New grade record created for Student {student_id}",
                "action": "created"
            }
        else:
            subject_codes = existing_record.get("SubjectCodes", [])
            grades = existing_record.get("Grades", [])
            teachers = existing_record.get("Teachers", [])
            
            if subject_code in subject_codes:
                subject_index = subject_codes.index(subject_code)
                old_grade = grades[subject_index]
                grades[subject_index] = grade
                teachers[subject_index] = teacher
                
                result = new_grades_col.update_one(
                    {"StudentID": student_id, "SemesterID": semester_id},
                    {
                        "$set": {
                            "Grades": grades,
                            "Teachers": teachers
                        }
                    }
                )
                reload_pkl_by_specific_collections(collection_name = "new_grades")
                
                return {
                    "success": True,
                    "message": f"Updated {subject_code}: {old_grade} → {grade}",
                    "action": "updated"
                }
            else:
                result = new_grades_col.update_one(
                    {"StudentID": student_id, "SemesterID": semester_id},
                    {
                        "$push": {
                            "SubjectCodes": subject_code,
                            "Grades": grade,
                            "Teachers": teacher
                        }
                    }
                )
                reload_pkl_by_specific_collections(collection_name = "new_grades")
                return {
                    "success": True,
                    "message": f"Added new subject {subject_code} with grade {grade}",
                    "action": "added"
                }
                
    except Exception as e:
        return {
            "success": False, 
            "message": f"Error: {str(e)}",
            "action": "error"
        }