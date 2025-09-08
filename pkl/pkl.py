import pymongo
import pickle
import os

# MongoDB credentials
MONGO_USERNAME = "smsgaldones"
MONGO_PASSWORD = "mit261laban"
DB_NAME = "mit261"
MONGO_CLUSTER = "cluster0"
MONGO_KEY="jp5aupl"
# Correct Python f-string for URI
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_CLUSTER}.{MONGO_KEY}.mongodb.net/{DB_NAME}?retryWrites=true&w=majority"

# MongoDB connection setup
client = pymongo.MongoClient(MONGO_URI)
db = client[DB_NAME]

# Create a folder to store pickle files
output_folder = "pkl"
os.makedirs(output_folder, exist_ok=True)

def run_all_collections():
    # Fetch all collections
    collections = db.list_collection_names()

    for collection_name in collections:
        collection = db[collection_name]
        documents = list(collection.find({}))  # Fetch all documents

        # Define pickle file path
        file_path = os.path.join(output_folder, f"{collection_name}.pkl")

        # Save to pickle
        with open(file_path, "wb") as f:
            pickle.dump(documents, f)

        print(f"Saved {len(documents)} documents from '{collection_name}' to '{file_path}'")

    print("\n🎉 All collections have been pickled successfully!")

def run_specific_collections(collection_name): 
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


if __name__ == "__main__":
    # run_all_collections()
    run_specific_collections(collection_name = "new_grades")