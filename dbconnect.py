import os
from dotenv import load_dotenv
from pymongo import MongoClient
import streamlit as st

load_dotenv()

# Prefer environment variable, then Streamlit secrets if available
MONGO_URI = os.getenv("MONGO_URI") or st.secrets.get("MONGO_URI", None)

client = None

def db_connect():
    global client
    try:
        if client is None:
            if not MONGO_URI:
                raise ValueError("MONGO_URI is not set. Provide it via environment or Streamlit secrets.")
            client = MongoClient(MONGO_URI)
        db = client["mit261"]
        print("Connected to MongoDB:", db.name)
        return db
    except Exception as e:
        print("Connection failed:", e)
        return None

def close_db_connect():
    global client
    if client:
        client.close()
        client = None
        print("🔒 MongoDB connection closed")