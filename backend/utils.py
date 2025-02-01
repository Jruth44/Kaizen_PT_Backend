# utils.py
import json
import os
from typing import Dict

DATA_FILE = os.path.join("database", "patients.json")

def load_patients() -> Dict:
    """
    Loads patient data from a JSON file or returns an empty dict if missing.
    """
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_patients(patients: Dict):
    """
    Saves patient data to a JSON file.
    """
    with open(DATA_FILE, "w") as f:
        json.dump(patients, f, indent=4)

def create_weekly_schedule():
    """
    Creates a basic weekly schedule template.
    NOTE: This is a placeholder; consider enhancing with dynamic scheduling features.
    """
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return {day: [] for day in days}

def generate_pt_weekly_schedule(patients_db: Dict):
    """
    Aggregates the weekly schedule for the PT by combining all patients' schedules.
    NOTE: Placeholder for more sophisticated aggregation and filtering.
    """
    pt_schedule = create_weekly_schedule()
    for patient_name, data in patients_db.items():
        if "weekly_schedule" in data:
            for day, exercises in data["weekly_schedule"].items():
                for exercise in exercises:
                    pt_schedule[day].append(f"{patient_name}: {exercise.get('name', exercise)}")
    return pt_schedule