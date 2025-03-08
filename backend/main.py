import os
import json
import uvicorn
import jwt
from fastapi import FastAPI, HTTPException, Depends, Body, Request, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict
from models import PatientCreate, PatientUpdate, InjuryQuestionnaire
from utils import create_weekly_schedule
from services import generate_recovery_plan, generate_diagnosis, chat_with_pt, create_pt_system_prompt
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Create the FastAPI app instance
app = FastAPI(title="PT Exercise Planner API")

# Enable CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kaizen-pt-frontend.vercel.app"],  # Replace with your production frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database for simplicity (would be replaced with a database in production)
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
# Weekly Schedule Endpoints
# ----------------------------
@app.get("/weekly_schedule/{patient_name}")
def get_weekly_schedule(patient_name: str, current_user: dict = Depends(get_current_user)):
    """
    Retrieve the weekly exercise schedule for a given patient.
    Uses the authenticated user's email to verify access.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Use the authenticated user's email as the patient identifier
    patient_identifier = user_email
    
    if patient_identifier not in patients_db:
        # Create an empty schedule if the patient doesn't exist
        patients_db[patient_identifier] = {
            "name": patient_identifier,
            "injuries": [],
            "weekly_schedule": create_weekly_schedule()
        }
        
    return patients_db[patient_identifier]["weekly_schedule"]

# ----------------------------
# Injury Management Endpoints
# ----------------------------
@app.post("/patients/{patient_name}/injury_questionnaire")
async def add_injury_questionnaire(
    patient_name: str,
    questionnaire: InjuryQuestionnaire,
    current_user: dict = Depends(get_current_user)
):
    """
    Add an injury questionnaire for a patient and generate a diagnosis.
    """
    # Use the authenticated user's email as the patient identifier.
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Override the provided patient_name with the authenticated user's email.
    patient_identifier = user_email
    print(f"Received questionnaire for patient: {patient_identifier}", flush=True)

    if patient_identifier not in patients_db:
        print(f"Creating new patient record for: {patient_identifier}", flush=True)
        patients_db[patient_identifier] = {
            "name": patient_identifier,
            "injuries": [],
            "weekly_schedule": create_weekly_schedule()
        }

    try:
        injury_data = questionnaire.dict()
        print("Calling Anthropic (Claude) for diagnosis...", flush=True)
        diagnosis_result = generate_diagnosis(injury_data)
        print(f"Diagnosis received", flush=True)
        
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
    
    if patient_identifier not in patients_db:
        return []
    
    # Return the injuries array for this patient
    return patients_db[patient_identifier].get("injuries", [])

@app.delete("/patients/{patient_name}/injuries/{injury_index}")
async def delete_patient_injury(
    patient_name: str,
    injury_index: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific injury for a patient.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    # Use the authenticated user's email as the patient identifier
    patient_identifier = user_email
    
    if patient_identifier not in patients_db:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    injuries = patients_db[patient_identifier].get("injuries", [])
    
    if not injuries or injury_index < 0 or injury_index >= len(injuries):
        raise HTTPException(status_code=404, detail=f"Injury with index {injury_index} not found")
    
    # Remove the injury at the specified index
    deleted_injury = injuries.pop(injury_index)
    
    # Save the updated database to disk
    save_database()
    
    return {"message": f"Injury deleted successfully", "deleted_injury": deleted_injury}

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
    
@app.post("/chat_with_pt")
async def chat_with_pt_endpoint(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Chat with Claude as a PT assistant in a streaming response.
    
    This endpoint uses Server-Sent Events (SSE) to stream the response
    from Claude back to the frontend.
    """
    if not payload or not isinstance(payload.get("messages"), list):
        raise HTTPException(status_code=400, detail="Invalid messages format")
    
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    
    try:
        # Get the messages from the request
        messages = payload["messages"]
        
        # Create the streaming response
        async def generate():
            async for text_chunk in chat_with_pt(messages):
                yield text_chunk
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    
    except Exception as e:
        print(f"Chat with PT error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with AI: {str(e)}"
        )

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

# Attempt to load an existing database on startup
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