from flask import Flask, request, jsonify
from database import HumanExternalDataStore, HumanMessage, AIMessage
import os
from dotenv import load_dotenv
from flask_cors import CORS
from typing_extensions import TypedDict
from pydantic import BaseModel
from time import time
# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
pool = dict()

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    """Simple route to check if the API is running"""
    return jsonify({"status": "alive", "message": "API is running"}), 200

@app.route('/init', methods=['POST'])
def init():
    """
    Initialize the database for a new user
    """
    data = request.get_json() 
    # handle authentication
    userfname = data.get('userfname')
    userlname = data.get('userlname')
    start_time = time()
    api_id = userfname + ":" + userlname

    if api_id not in pool:
        pool[api_id] = {
            "fname": userfname,
            "lname": userlname,
            "db": None
        }
    
    # get url
    url = request.url
    
    if pool[api_id]["db"] is None: # if the database is not initialized, initialize it
        pool[api_id]["db"] = HumanExternalDataStore(pool[api_id]["fname"], pool[api_id]["lname"], url)
    else: # if the database is already initialized, close it and initialize a new one
        pool[api_id]["db"].close() 
        pool[api_id]["db"] = HumanExternalDataStore(pool[api_id]["fname"], pool[api_id]["lname"], url)
    
    cur_db = pool[api_id]["db"]
    end_time = time()
    print(f"API to Firebase time: {end_time - start_time} seconds")
    
    return jsonify({
        "status": "success", 
        "message": "Database connection initialized",
        "human_messages": [m.content for m in cur_db.msg_chain if isinstance(m, HumanMessage)], # "responses" and "messages" was removed
        "ai_responses": [m.content for m in cur_db.msg_chain if isinstance(m, AIMessage)],
        "meal_plan": cur_db.structured_data['meal_plan'],
        "latency": end_time - start_time
    }), 200


@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint that processes user messages
    
    Expected JSON payload:
    {
        "userfname": "First Name",
        "userlname": "Last Name",
        "message": "User message here"
    }
    """
    try:
        # Get JSON data from request
        start_time = time()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract required fields
        message = data.get('message')
        userfname = data.get('userfname')
        userlname = data.get('userlname')
        model = data.get('model')
        api_id = userfname + ":" + userlname

        # compare userfname and userlname with user_creds
        if userfname != pool[api_id]["fname"] or userlname != pool[api_id]["lname"]:
            return jsonify({"error": "Invalid user credentials"}), 401
        
        # Process the message and get response
        pool[api_id]["db"].model = model
        ai_response = pool[api_id]["db"].call_chat(message)

        end_time = time()
        print(f"API to Lang to GPT and back RTT: {end_time - start_time} seconds")
        return jsonify({
            "status": "success",
            "response": ai_response,
            "meal_plan": pool[api_id]["db"].structured_data["meal_plan"],
            "latency": end_time - start_time,
            "langchain_rtt": pool[api_id]["db"].last_langchain_rtt
        }), 200
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    
@app.route('/close', methods=['POST'])
def close():
    """
    Close the database for a user
    """
    data = request.get_json()
    userfname = data.get('userfname')
    userlname = data.get('userlname')
    api_id = userfname + ":" + userlname

    # save user data and remove the user from the pool
    try:
        _, message = pool[api_id]["db"].close()
        del pool[api_id]
        return jsonify({"status": "success", "message": message}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

