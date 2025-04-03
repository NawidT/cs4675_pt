from fastapi import FastAPI, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
import asyncio
from PIL import Image
import base64
import io

from human_external_data_store import HumanExternalDataStore
# Import placeholder for Gemini integration
from gemini_service import query_gemini_api

app = FastAPI(title="PT - Personal Transformer", 
              description="A personalized nutrition and fitness assistant")

# Pydantic models for request/response validation
class UserMessage(BaseModel):
    user_id: str
    fname: str
    lname: str
    message: str
    timestamp: Optional[datetime] = None
# Not used, can simplify or keep in Optionals in case of future use
class UserProfile(BaseModel):
    user_id: str
    fname: str
    lname: str
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    goals: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    fitness_level: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    data_extracted: Optional[Dict[str, Any]] = None

# User data store cache
user_data_stores = {}

async def get_data_store(fname: str, lname: str):
    """Get or create a data store for a user"""
    user_key = f"{fname}_{lname}"
    
    if user_key not in user_data_stores:
        try:
            loop = asyncio.get_event_loop()
            data_store = await loop.run_in_executor(
                None, lambda: HumanExternalDataStore(fname, lname)
            )
            user_data_stores[user_key] = data_store
        except ValueError as e:
            raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to database: {str(e)}")
    
    return user_data_stores[user_key]

# Endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(message: UserMessage):
    """
    Process user messages, extract data, and return a response from LLM
    """
    try:
        data_store = await get_data_store(message.fname, message.lname)
        
        structured_data = data_store.get_structured_data()
        
        # Add the new message to the list
        if len(structured_data["messages"]) >= 20:
            structured_data["messages"].pop(0)
            structured_data["responses"].pop(0)
        
        structured_data["messages"].append(message.message)
        structured_data["last_updated"] = datetime.now().isoformat()
        
        data_store.update_structured_data(structured_data)
        
        unstructured_data = data_store.get_unstructured_data()
        
        # Create context for the LLM
        context = {
            "structured_data": structured_data,
            "unstructured_data": unstructured_data,
            "current_message": message.message,
            "timestamp": message.timestamp or datetime.now()
        }
        
        # Plaaceholder for Gemini API call
        # This should be replaced with the actual API call to Gemini`
        gemini_response = await query_gemini_api(
            user_message=message.message,
            user_context=context
        )
        
        structured_data["responses"].append(gemini_response["text_response"])
        data_store.update_structured_data(structured_data)
        ## To replace the above line with actual API call from Gemini. Get key facts from gemini module and
        ## update unstructured data
        if "extracted_data" in gemini_response and gemini_response["extracted_data"]:
            if "key_facts" in gemini_response["extracted_data"]:
                unstructured_data["key_facts"].update(gemini_response["extracted_data"]["key_facts"])
                data_store.update_unstructured_data(unstructured_data)
        
        # Update the conversation summary
        if len(structured_data["messages"]) % 5 == 0:  # Every 5 messages
            await update_conversation_summary(data_store)
        
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )

        # Update datastore db
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )
        ## update based on gemini module
        return {
            "response": gemini_response["text_response"],
            "data_extracted": gemini_response.get("extracted_data", {})
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")
## update structured data summary using llm and update data store
async def update_conversation_summary(data_store: HumanExternalDataStore):
    """Update the conversation summary using the LLM"""
    structured_data = data_store.get_structured_data()
    
    # last 10 messages and responses
    messages = structured_data['messages'][-10:]
    responses = structured_data['responses'][-10:]
    
    # prompt to summarize the conversation
    conversation_text = ""
    for i in range(min(len(messages), len(responses))):
        conversation_text += f"User: {messages[i]}\nAssistant: {responses[i]}\n\n"
    
    from langchain_core.messages import SystemMessage, HumanMessage
    
    summary_prompt = SystemMessage(content="""
        Create a concise summary of the conversation so far, focusing on:
        1. The user's fitness and nutrition goals
        2. Key personal information (height, weight, age, etc.)
        3. Dietary preferences and restrictions
        4. Current fitness level and exercise habits
        5. Any health issues or concerns mentioned
        
        Be brief but comprehensive. This summary will be used to maintain context in future conversations.
    """)
    
    conversation_message = HumanMessage(content=f"Here's the conversation to summarize:\n\n{conversation_text}")
    
    try:
        summary = data_store.invoke_chat([summary_prompt, conversation_message], "str")
        
        structured_data["summary"] = summary
        data_store.update_structured_data(structured_data)
    except Exception as e:
        print(f"Error updating summary: {str(e)}")

@app.post("/profile", response_model=UserProfile)
async def create_or_update_profile(profile: UserProfile):
    """
    Create or update user profile information
    """
    try:
        # Get data store for the user
        data_store = await get_data_store(profile.fname, profile.lname)
        
        # Get current structured data
        structured_data = data_store.get_structured_data()
        
        # Update profile information
        if profile.age is not None:
            structured_data["age"] = profile.age
            
        # Update the data store
        data_store.update_structured_data(structured_data)
        
        # Update database
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )
        
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

@app.get("/profile/{fname}/{lname}", response_model=UserProfile)
async def get_profile(fname: str, lname: str):
    """
    Retrieve user profile information
    """
    try:
        # Get data store for the user
        data_store = await get_data_store(fname, lname)
        
        # Get structured data
        structured_data = data_store.get_structured_data()
        
        # Extract information
        profile = UserProfile(
            user_id=structured_data.get("user_id", ""),
            fname=structured_data.get("fname", ""),
            lname=structured_data.get("lname", ""),
            age=structured_data.get("age")
        )
        
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")
## Update when preferences data structure / storage is detemrined
## Should preferences come from key facts? Or just remove preferendces and use structured data
@app.post("/meal-plan/{fname}/{lname}")
async def generate_meal_plan(fname: str, lname: str, preferences: Dict = Body(...)):
    """
    Generate a personalized meal plan using the Gemini API
    """
    try:
        data_store = await get_data_store(fname, lname)
        
        structured_data = data_store.get_structured_data()
        unstructured_data = data_store.get_unstructured_data()
        
        context = {
            "structured_data": structured_data,
            "unstructured_data": unstructured_data,
            "preferences": preferences
        }
        
        # Placeholder
        response = await query_gemini_api(
            user_message="Generate a personalized meal plan",
            user_context=context,
            task="meal_plan"
        )
        
        # Add interaction to messages and responses
        if len(structured_data["messages"]) >= 20:
            structured_data["messages"].pop(0)
            structured_data["responses"].pop(0)
        ## Update when preferences data structure / storage is detemrined
        structured_data["messages"].append("Please generate a meal plan with these preferences: " + json.dumps(preferences)) ## replace with key facts
        structured_data["responses"].append(response.get("text_response", ""))
        structured_data["last_updated"] = datetime.now().isoformat()
        
        # Update data store
        data_store.update_structured_data(structured_data)
        
        # Update Data Base database
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )
        
        return {
            "meal_plan": response.get("meal_plan", {}),
            "message": response.get("text_response")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating meal plan: {str(e)}")
## Update when preferences data structure / storage is detemrined
## Should preferences come from key facts
@app.post("/workout-plan/{fname}/{lname}")
async def generate_workout_plan(fname: str, lname: str, preferences: Dict = Body(...)):
    """
    Generate a personalized workout plan using the Gemini API
    """
    try:
        data_store = await get_data_store(fname, lname)
        
        structured_data = data_store.get_structured_data()
        unstructured_data = data_store.get_unstructured_data()
        # UPDATE
        context = {
            "structured_data": structured_data,
            "unstructured_data": unstructured_data,
            "preferences": preferences
        }
        
        # PLACEHOLDER
        response = await query_gemini_api(
            user_message="Generate a personalized workout plan",
            user_context=context,
            task="workout_plan"
        )
        
        # Add interaction to messages and responses
        if len(structured_data["messages"]) >= 20:
            structured_data["messages"].pop(0)
            structured_data["responses"].pop(0)
        ## Update when preferences data structure / storage is detemrined
        structured_data["messages"].append("Please generate a workout plan with these preferences: " + json.dumps(preferences))
        structured_data["responses"].append(response.get("text_response", ""))
        structured_data["last_updated"] = datetime.now().isoformat()
        
        # Update data store
        data_store.update_structured_data(structured_data)
        
        # Update database
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )
        
        return {
            "workout_plan": response.get("workout_plan", {}),
            "message": response.get("text_response")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating workout plan: {str(e)}")

@app.get("/history/{fname}/{lname}")
async def get_conversation_history(fname: str, lname: str, limit: int = 10):
    """
    Retrieve conversation history for a user
    """
    try:
        # Get data store for the user
        data_store = await get_data_store(fname, lname)
        
        # Get structured data
        structured_data = data_store.get_structured_data()
        
        messages = structured_data["messages"][-limit:]
        responses = structured_data["responses"][-limit:]
        
        history = []
        for i in range(min(len(messages), len(responses))):
            history.append({
                "message": messages[i],
                "response": responses[i]
            })
        
        return {
            "history": history,
            "summary": structured_data.get("summary", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")

@app.post("/feedback/{fname}/{lname}")
async def submit_feedback(
    fname: str,
    lname: str,
    feedback: Dict[str, Any] = Body(...)
):
    """
    Store user feedback on recommendations for continuous improvement
    """
    try:
        data_store = await get_data_store(fname, lname)
        
        structured_data = data_store.get_structured_data()
        
        # add feedback as a message
        if len(structured_data["messages"]) >= 20:
            structured_data["messages"].pop(0)
            structured_data["responses"].pop(0)
        
        feedback_message = f"Feedback: {json.dumps(feedback)}"
        structured_data["messages"].append(feedback_message)
        structured_data["responses"].append("Thank you for your feedback!")
        structured_data["last_updated"] = datetime.now().isoformat()
        
        # Update data store
        data_store.update_structured_data(structured_data)
        
        # Update database
        await asyncio.get_event_loop().run_in_executor(
            None, data_store.update_db
        )
        
        return {"status": "Feedback submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)