import firebase_admin
from firebase_admin import credentials, firestore
import uuid

cred = credentials.Certificate("backend/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

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
    
create_user_data({"FName": "John", "LName": "Doe", "Age": "30"})
# print(get_user_data("5gbRpYJZbNFMnvXQ4XWF"))