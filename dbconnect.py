import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

database = None

def db_connect():
    try:
        database = MongoClient(MONGO_URI)
        db = database["mit261"]
        print("Connected to MongoDB:", db.name)
        return db
    except Exception as e:
        print("Connection failed:", e)
        return None
        return none

def close_db_connect():
    global database
    if database:
        database.close()
        print("🔒 MongoDB connection closed")