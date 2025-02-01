# models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class PatientCreate(BaseModel):
    """Model for creating a new patient"""
    name: str
    age: int
    injury_location: Optional[str] = None
    pain_level: Optional[int] = None
    mobility_status: Optional[str] = None
    medical_history: Optional[str] = None
    activity_level: Optional[str] = None
    goals: Optional[str] = None

class PatientUpdate(BaseModel):
    """Model for updating an existing patient"""
    age: Optional[int] = None
    injury_location: Optional[str] = None
    pain_level: Optional[int] = None
    mobility_status: Optional[str] = None
    medical_history: Optional[str] = None
    activity_level: Optional[str] = None
    goals: Optional[str] = None

class ExerciseRecommendationsRequest(BaseModel):
    """Model for requesting exercise recommendations"""
    patient_name: str
    injury_type: str
    pain_level: int
    goals: Optional[str] = None

class InjuryQuestionnaire(BaseModel):
    """
    A generalized model for different injury questionnaires.
    """
    body_part: str  # e.g. "Shoulder", "Knee", "Hip"
    
    # Basic Painful Area Evaluation
    hurting_description: str  # e.g. "Where are you hurting / what does it feel like?"
    date_of_onset: Optional[str] = None
    aggravating_factors: Optional[str] = None
    easing_factors: Optional[str] = None
    mechanism_of_injury: Optional[str] = None  # direct, indirect, unexpected, etc.

    # SINSS: Severity, Irritability, Nature, Stage, Stability
    severity_best: Optional[int] = None    # 0-10 at best
    severity_worst: Optional[int] = None   # 0-10 at worst
    severity_daily_avg: Optional[int] = None  # 0-10 on average

    irritability_factors: Optional[str] = None
    nature_of_pain: Optional[str] = None  # "Clicking," "Grinding," "Sharp," etc.
    stage: Optional[str] = None           # "Acute," "Subacute," "Chronic," etc.
    stability: Optional[str] = None       # "Improving," "Worsening," "Fluctuating," etc.

    # Additional specialized data for each body part or extra fields you want to store
    specialized_data: Dict[str, Any] = Field(default_factory=dict)
    """
    Example:
    {
      "special_tests": {
        "hawkins_kennedy": true,
        "neer": false,
        ...
      },
      "joint_angles": {
        "flexion": 120,
        "abduction": 90,
        ...
      }
    }
    """ 
