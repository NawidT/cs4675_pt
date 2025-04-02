import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from typing_extensions import TypedDict
from datetime import datetime
from PIL import Image

cred = credentials.Certificate("backend/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

class UserData(TypedDict):
    FName: str
    LName: str
    Age: int

class StructuredData(TypedDict):
    Messages: list[str] # store last 20 messages
    Responses: list[str] # store last 20 responses
    Summary: str # summary of the conversation
    LastUpdated: str # last updated timestamp
    user_info: UserData

class UnstructuredData(TypedDict):
    key_facts: dict[str, str] # key facts of the conversation
    static_data: dict[str, Image.Image] # static data of the conversation

class PTData(TypedDict):
    structured_data: StructuredData
    unstructured_data: UnstructuredData


# step 1: fetch data from db
# step 2: process user input and return response
# step 3: update conversation data in db

def get_user_data(user_id):
    user_ref = db.collection("test-users").document(user_id)
    user_doc = user_ref.get()
    if user_doc.exists:
        return user_doc.to_dict()
    else:
        return None
    
def create_user_data(user_data):
    random_id = str(uuid.uuid4())
    user_ref = db.collection("test-users").document(random_id)
    user_ref.set(user_data)

def update_user_data(user_id, user_data):
    user_ref = db.collection("test-users").document(user_id)
    user_ref.update(user_data)




create_user_data({"FName": "John", "LName": "Doe", "Age": "30"})
# print(get_user_data("5gbRpYJZbNFMnvXQ4XWF"))