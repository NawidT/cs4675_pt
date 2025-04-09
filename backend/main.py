from flask import Flask, request, jsonify
from database import HumanExternalDataStore
import os
from dotenv import load_dotenv
from flask_cors import CORS
# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
user_creds = {
    "fname": "",
    "lname": "",
    "db": None
}

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
    user_creds["fname"] = userfname
    user_creds["lname"] = userlname
    if user_creds["db"] is None:
        user_creds["db"] = HumanExternalDataStore(userfname, userlname)
    else:
        del user_creds["db"]
        user_creds["db"] = HumanExternalDataStore(userfname, userlname)
    return jsonify({
        "status": "success", 
        "message": "Database connection initialized",
        "human_messages": user_creds["db"].structured_data["messages"],
        "ai_responses": user_creds["db"].structured_data["responses"],
        "meal_plan": user_creds["db"].structured_data['meal_plan']
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
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Extract required fields
        message = data.get('message')
        userfname = data.get('userfname')
        userlname = data.get('userlname')

        # compare userfname and userlname with user_creds
        if userfname != user_creds["fname"] or userlname != user_creds["lname"]:
            return jsonify({"error": "Invalid user credentials"}), 401
        
        # Process the message and get response
        ai_response = user_creds["db"].call_chat(message)
        
        return jsonify({"response": ai_response}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/close', methods=['GET'])
def close():
    """
    Close the database for a user
    """
    user_creds["db"].close()
    return jsonify({"status": "success", "message": "Database connection closed"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

