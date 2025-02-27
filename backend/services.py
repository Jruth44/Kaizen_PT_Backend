import json
import os
from anthropic import Anthropic
from typing import Dict
from dotenv import load_dotenv

# Load environment variables (make sure to create a .env file with your keys)
load_dotenv()

# Optionally remove proxy settings if they cause issues
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

def generate_recovery_plan(patient_data, injuries):
    """
    Generate a personalized recovery plan using Anthropic's API.
    This creates a weekly schedule of exercises based on the patient's injuries.
    """
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
    # Initialize the client with the API key
    client = Anthropic(api_key=anthropic_api_key)
    
    # Format the injuries data for the prompt
    injuries_text = []
    for i, injury in enumerate(injuries):
        injuries_text.append(f"""
Injury {i+1}:
- Body Part: {injury.get('body_part')}
- Description: {injury.get('hurting_description')}
- Diagnosis: {injury.get('diagnosis')}
- Pain Levels: Best={injury.get('severity_best')}, Worst={injury.get('severity_worst')}, Daily Avg={injury.get('severity_daily_avg')}
- Stage: {injury.get('stage')}
        """)
    
    injuries_description = "\n".join(injuries_text)
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            system="""You are an expert physical therapist creating personalized recovery plans.
            
For each day of the week, recommend appropriate exercises based on the patient's injuries and condition.
Format your response as a JSON object with the days of the week as keys.
Each day should have an array of exercise objects with the following properties:
- name: The name of the exercise
- sets: Number of sets
- reps: Number of repetitions
- description: Brief instructions for performing the exercise
- purpose: What this exercise helps with

Include rest days as appropriate. If certain days should focus on different body parts or aspects of recovery, organize them accordingly.
            """,
            messages=[{
                "role": "user",
                "content": f"""Create a personalized weekly recovery plan for a patient with the following profile:

Patient Information:
- Age: {patient_data.get('age', 'Unknown')}
- Activity Level: {patient_data.get('activity_level', 'Unknown')}
- Goals: {patient_data.get('goals', 'Recovery')}

Injuries:
{injuries_description}

Please create a structured weekly exercise schedule that addresses all injuries while allowing for proper recovery.
Include a variety of exercises including stretching, strengthening, and mobility work as appropriate.
Format the response as a JSON object."""
            }]
        )
        content = message.content[0].text if isinstance(message.content, list) else message.content
        
        # Use regex to extract JSON from the response (in case extra text is included)
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            return {
                "error": "Failed to generate recovery plan",
                "message": "Could not parse the AI response"
            }

    except Exception as e:
        print(f"Anthropic API error (generate_recovery_plan): {e}")
        return {
            "error": "Failed to generate recovery plan",
            "message": f"API Error: {str(e)}"
        }

def generate_diagnosis(injury_data: Dict) -> Dict:
    """
    Generate a preliminary diagnosis using Anthropic's API.
    """
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
    # Initialize the client with the API key
    client = Anthropic(api_key=anthropic_api_key)
    
    injury_description = f"""
    Body Part: {injury_data.get('body_part')}
    Description: {injury_data.get('hurting_description')}
    Onset: {injury_data.get('date_of_onset')}
    Aggravating Factors: {injury_data.get('aggravating_factors')}
    Easing Factors: {injury_data.get('easing_factors')}
    Mechanism: {injury_data.get('mechanism_of_injury')}
    Pain Levels: Best={injury_data.get('severity_best')}, Worst={injury_data.get('severity_worst')}, Daily Avg={injury_data.get('severity_daily_avg')}
    Special Tests: {injury_data.get('specialized_data', {}).get('special_tests', {})}
    """
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": f"""Analyze the following injury data and provide:
1. A preliminary diagnosis
2. Clinical reasoning
3. Recommended next steps

Patient Data:
{injury_description}

Format your response as JSON:
{{
  "diagnosis": "your diagnosis",
  "reasoning": "your reasoning",
  "recommendations": "your next steps"
}}"""
            }]
        )
        content = message.content[0].text if isinstance(message.content, list) else message.content
        # Use regex to extract JSON from the response (in case extra text is included)
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            return {
                "diagnosis": "Error parsing diagnosis",
                "reasoning": "Could not generate reasoning",
                "recommendations": "Consult a healthcare provider"
            }

    except Exception as e:
        print(f"Anthropic API error (generate_diagnosis): {e}")
        return {
            "diagnosis": "Error generating diagnosis",
            "reasoning": f"API Error: {str(e)}",
            "recommendations": "Consult a healthcare provider"
        }
