import json
import os
from anthropic import Anthropic
from typing import Dict
from dotenv import load_dotenv

# Load environment variables (make sure to create a .env file with your keys)
load_dotenv()

def generate_exercises(patient_data: Dict, num_exercises: int) -> Dict:
    """
    Generate exercise recommendations using Anthropic's API.
    """
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return {}

    # Initialize the client without any additional arguments
    client = Anthropic()
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10000,
            system=f"""You are an expert physical therapy assistant...
Generate exactly {num_exercises} exercises.
Format all responses as a JSON object.""",
            messages=[{
                "role": "user",
                "content": f"""Generate a set of targeted exercises for this patient:
Age: {patient_data.get('age')}
Injury Location: {patient_data.get('injury_location')}
Pain Level: {patient_data.get('pain_level')}/10
Mobility Status: {patient_data.get('mobility_status')}
Medical History: {patient_data.get('medical_history')}
Activity Level: {patient_data.get('activity_level')}
Goals: {patient_data.get('goals')}
Provide output in the specified JSON format."""
            }]
        )
        # Parse the returned content as JSON
        content = message.content[0].text if isinstance(message.content, list) else message.content
        parsed = json.loads(content)
        return parsed

    except Exception as e:
        print(f"Anthropic API error in generate_exercises: {e}")
        return {}

def generate_diagnosis(injury_data: Dict) -> Dict:
    """
    Generate a preliminary diagnosis using Anthropic's API.
    """
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
    # Initialize the client without any additional arguments
    client = Anthropic()
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
            max_tokens=10000,
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