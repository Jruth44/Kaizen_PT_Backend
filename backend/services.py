import json
import os
from anthropic import Anthropic
from typing import Dict
import asyncio
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
            model="claude-3-7-sonnet-20250219",
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
            model="claude-3-7-sonnet-20250219",
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

async def chat_with_pt(messages: List[Dict]) -> AsyncGenerator[str, None]:
    """
    Chat with Claude as a PT assistant with streaming response.
    
    Args:
        messages: A list of message objects in the format expected by Anthropic's API
                 [{"role": "user", "content": "..."}, ...]
                 
    Yields:
        Text chunks as they are generated by Claude
    """
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    # Initialize the client with the API key
    client = Anthropic(api_key=anthropic_api_key)
    
    try:
        # Use the streaming API
        async with client.messages.stream(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4000,
            messages=messages,
            temperature=0.7,
        ) as stream:
            # Stream each chunk of the response
            async for text in stream.text_stream:
                yield text
                # Small delay to prevent flooding
                await asyncio.sleep(0.01)
    
    except Exception as e:
        print(f"Anthropic API streaming error: {e}")
        yield f"Sorry, I encountered an error: {str(e)}"

def create_pt_system_prompt(injuries=None, recovery_plan=None):
    """
    Create a system prompt for the PT assistant based on the user's context.
    
    Args:
        injuries: List of injury data
        recovery_plan: Weekly recovery plan data
        
    Returns:
        A string containing the system prompt
    """
    prompt = "You are a helpful and knowledgeable physical therapist assistant, providing guidance and advice about injuries, exercises, and physical recovery. "
    
    # Add injury context if available
    if injuries and len(injuries) > 0:
        prompt += "The user has the following injuries:\n"
        for i, injury in enumerate(injuries):
            prompt += f"Injury {i + 1}: {injury.get('body_part')} - {injury.get('hurting_description')}\n"
            if injury.get('diagnosis'):
                prompt += f"Diagnosis: {injury.get('diagnosis')}\n"
            prompt += f"Pain levels: Best={injury.get('severity_best') or 'N/A'}, Worst={injury.get('severity_worst') or 'N/A'}\n"
    
    # Add recovery plan context if available
    if recovery_plan:
        prompt += "\nThe user has a recovery plan with the following exercises:\n"
        for day, exercises in recovery_plan.items():
            if exercises and len(exercises) > 0:
                prompt += f"{day}: "
                exercise_names = []
                for exercise in exercises:
                    # Handle both string and object exercise formats
                    name = exercise.get('name') if isinstance(exercise, dict) else exercise
                    if name:
                        exercise_names.append(name)
                prompt += ", ".join(exercise_names) + "\n"
    
    prompt += "\nProvide concise, helpful answers about physical therapy, exercises, and recovery. Don't suggest medical diagnoses, but you can explain potential causes of symptoms. If you don't know something, be honest about it. Always prioritize safety and recommend consulting a healthcare provider for serious concerns."
    
    return prompt