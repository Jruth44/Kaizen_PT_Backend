# backend/main.py
import os
import json
import uvicorn
import jwt  # Make sure to add 'PyJWT' to your requirements.txt
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
from models import PatientCreate, PatientUpdate, ExerciseRecommendationsRequest, InjuryQuestionnaire
from utils import load_patients, save_patients, create_weekly_schedule
from services import generate_recovery_plan, generate_diagnosis
from dotenv import load_dotenv

load_dotenv()

# Create the FastAPI app instance before using it
app = FastAPI(title="PT Exercise Planner API")

# Enable CORS for local development; update allow_origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kaizen-pt-frontend.vercel.app"],  # Replace with your production frontend URL as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database for simplicity (replace with a persistent DB later)
patients_db = {}

# ----------------------------
# Supabase Authentication Setup
# ----------------------------
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    raise Exception("SUPABASE_JWT_SECRET environment variable must be set for JWT validation")

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}  # disable audience verification
        )
        return payload
    except Exception as e:
        print("JWT decode error:", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/auth/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user's information after verifying the Supabase JWT token.
    """
    return current_user

# ----------------------------
# Patient Management Endpoints
# ----------------------------
@app.get("/patients", response_model=List[str])
def list_patients():
    """
    Returns a list of patient names.
    """
    return list(patients_db.keys())

@app.get("/patients/{patient_name}")
def get_patient(patient_name: str):
    """
    Retrieve detailed data for a specific patient.
    """
    if patient_name not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patients_db[patient_name]

@app.post("/patients/")
def create_patient(patient: PatientCreate):
    """
    Create a new patient.
    TODO: Later expand this endpoint to include user authentication details.
    """
    if patient.name in patients_db:
        raise HTTPException(status_code=400, detail="Patient already exists")
    
    patients_db[patient.name] = patient.dict()
    patients_db[patient.name]["injuries"] = []
    # Initialize a weekly schedule using the utility function
    patients_db[patient.name]["weekly_schedule"] = create_weekly_schedule()
    return {"message": f"Patient {patient.name} created successfully"}

@app.put("/patients/{patient_name}")
def update_patient(patient_name: str, patient_update: PatientUpdate):
    """
    Update details for an existing patient.
    """
    if patient_name not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_data = patient_update.dict(exclude_unset=True)
    patients_db[patient_name].update(patient_data)
    return {"message": f"Patient {patient_name} updated successfully"}

@app.delete("/patients/{patient_name}")
def delete_patient(patient_name: str):
    """
    Delete a patient record.
    """
    if patient_name not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    del patients_db[patient_name]
    save_patients(patients_db)
    return {"message": f"Patient '{patient_name}' has been deleted."}

# ----------------------------
# Exercise and Schedule Endpoints
# ----------------------------
@app.post("/patients/{patient_name}/generate_recovery_plan")
async def create_recovery_plan(
    patient_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a personalized recovery plan for a patient based on their injuries.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Use the authenticated user's email as the patient identifier
    patient_identifier = user_email
    print(f"Generating recovery plan for patient: {patient_identifier}", flush=True)
    
    if patient_identifier not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_data = patients_db[patient_identifier]
    injuries = patient_data.get("injuries", [])
    
    if not injuries:
        raise HTTPException(status_code=400, detail="No injuries found for this patient. Please add injury information first.")
    
    try:
        recovery_plan = generate_recovery_plan(patient_data, injuries)
        
        # Save the generated plan to the patient's data
        patients_db[patient_identifier]["weekly_schedule"] = recovery_plan
        save_database()
        
        return recovery_plan
    except Exception as e:
        error_message = f"Error generating recovery plan: {str(e)}"
        print(error_message, flush=True)
        raise HTTPException(status_code=500, detail=error_message)

@app.get("/weekly_schedule/{patient_name}")
def get_weekly_schedule(patient_name: str):
    """
    Retrieve the weekly exercise schedule for a given patient.
    """
    if patient_name not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patients_db[patient_name]["weekly_schedule"]

@app.post("/weekly_schedule/{patient_name}/{day}")
def add_exercise_to_day(patient_name: str, day: str, exercise: Dict):
    """
    Add an exercise to a specific day in the patient's weekly schedule.
    TODO: Expand validation for day names and exercise details.
    """
    if patient_name not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    if day not in patients_db[patient_name]["weekly_schedule"]:
        raise HTTPException(status_code=400, detail="Invalid day provided")

    patients_db[patient_name]["weekly_schedule"][day].append(exercise)
    save_patients(patients_db)
    return {"message": f"Exercise added to {day} for {patient_name}"}

@app.get("/pt_schedule")
def get_overall_pt_schedule():
    """
    Retrieve the overall schedule combining exercises for all patients.
    TODO: This method is a placeholder for a more advanced schedule aggregation.
    """
    from utils import generate_pt_weekly_schedule
    schedule = generate_pt_weekly_schedule(patients_db)
    return schedule

@app.get("/patients/{patient_name}/injuries")
async def get_patient_injuries(
    patient_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all injuries for a specific patient.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Use the authenticated user's email as the patient identifier
    patient_identifier = user_email
    
    if patient_identifier not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Return the injuries array for this patient
    return patients_db[patient_identifier].get("injuries", [])

# ----------------------------
# Injury Questionnaire Endpoint
# ----------------------------
@app.post("/patients/{patient_name}/injury_questionnaire")
async def add_injury_questionnaire(
    patient_name: str,
    questionnaire: InjuryQuestionnaire,
    current_user: dict = Depends(get_current_user)
):
    # Use the authenticated user's email as the patient identifier.
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    # Override the provided patient_name with the authenticated user's email.
    patient_identifier = user_email
    print(f"Received questionnaire for patient: {patient_identifier}", flush=True)
    print(f"Questionnaire data: {questionnaire.dict()}", flush=True)

    if patient_identifier not in patients_db:
        print(f"Creating new patient record for: {patient_identifier}", flush=True)
        patients_db[patient_identifier] = {
            "name": patient_identifier,
            "injuries": [],
            "weekly_schedule": create_weekly_schedule()
        }

    try:
        injury_data = questionnaire.dict()
        print("Calling Anthropic (Claude 3.5) for diagnosis...", flush=True)
        diagnosis_result = generate_diagnosis(injury_data)
        print(f"Diagnosis received: {diagnosis_result}", flush=True)
        
        injury_data.update(diagnosis_result)
        patients_db[patient_identifier]["injuries"].append(injury_data)
        
        # Save the updated database to disk
        save_database()
        
        return diagnosis_result

    except Exception as e:
        error_message = f"Error during diagnosis generation: {str(e)}"
        print(error_message, flush=True)
        raise HTTPException(status_code=500, detail=error_message)

@app.get("/patients/{patient_name}/injuries")
async def get_patient_injuries(
    patient_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all injuries for a specific patient.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Use the authenticated user's email as the patient identifier
    patient_identifier = user_email
    print(f"Retrieving injuries for patient: {patient_identifier}", flush=True)
    
    if patient_identifier not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Return the injuries array for this patient
    injuries = patients_db[patient_identifier].get("injuries", [])
    print(f"Found {len(injuries)} injuries for patient", flush=True)
    return injuries

# ----------------------------
# Helper Functions for Database Persistence
# ----------------------------
def save_database():
    """Save the current patients_db state to disk."""
    try:
        with open("patients_db.json", "w") as f:
            json.dump(patients_db, f, indent=2)
    except Exception as e:
        print(f"Error saving database: {e}")

# Attempt to load an existing database on startup (development-only)
try:
    with open("patients_db.json", "r") as f:
        patients_db = json.load(f)
except FileNotFoundError:
    print("No existing database found. Starting fresh.")
    patients_db = {}
except Exception as e:
    print(f"Error loading database: {e}")
    patients_db = {}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)