# init_db.py
import os
import json

def initialize_database():
    # Create database directory if it doesn't exist
    db_dir = os.path.join(os.path.dirname(__file__), "database")
    os.makedirs(db_dir, exist_ok=True)
    
    # Create patients.json with an empty object
    db_file = os.path.join(db_dir, "patients.json")
    with open(db_file, "w") as f:
        json.dump({}, f)

        
    
    print(f"Database initialized at {db_file}")

if __name__ == "__main__":
    initialize_database()