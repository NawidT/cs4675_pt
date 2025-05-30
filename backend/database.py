from time import time
import firebase_admin
from firebase_admin import credentials, firestore
from typing_extensions import TypedDict
from langchain_openai.chat_models import ChatOpenAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from langchain_ollama.chat_models import ChatOllama
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser, PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from pydantic import BaseModel
import os
import base64



# TECHNICAL DECISION: support only one conversation per user    
class StructuredData(TypedDict):
    messages: list[str] # store last 20 messages
    responses: list[str] # store last 20 responses
    summary: str # summary of the conversation
    meal_plan: str # meal plan of the conversation
# TECHNICAL DECISION: focused on data made/changed this session and for short term use
class UnstructuredData(TypedDict):
    key_facts: dict[str, str] # key facts of the conversation

pk_service = base64.b64decode(os.getenv("BASE64_ENCODE_PK")).decode("utf-8")

credens = credentials.Certificate({
    "type": os.getenv("FIRESTORE_TYPE"),
    "project_id": os.getenv("FIRESTORE_PROJECT_ID"),
    "private_key_id": os.getenv("FIRESTORE_PRIVATE_KEY_ID"),
    "private_key": pk_service,
    "client_email": os.getenv("FIRESTORE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIRESTORE_CLIENT_ID"),
    "auth_uri": os.getenv("FIRESTORE_AUTH_URI"),
    "token_uri": os.getenv("FIRESTORE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIRESTORE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIRESTORE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("FIRESTORE_UNIVERSE_DOMAIN")
})


firebase_admin.initialize_app(credens)


# pydantic model with reasoning and is_health_related
class Guardrail(BaseModel):
    reasoning: str
    is_health_related: bool

def create_db_user(user_fname: str, user_lname: str):
    """
    Stateless API. Used to create a new user in the database
    """
    db = firestore.client()
    users = db.collection("convos")\
        .where(filter=firestore.firestore.FieldFilter("fname", "==", user_fname))\
        .where(filter=firestore.firestore.FieldFilter("lname", "==", user_lname))\
        .get()
    if len(users) > 0:
        return grab_db_user_data(user_fname, user_lname)
    # create key facts
    kf_ref = db.collection("keyfacts").document()
    kf_ref.set({})

    # create user
    user_ref = db.collection("convos").document()
    user_ref.set({
        "fname": user_fname,
        "lname": user_lname,
        "messages": [],
        "responses": [],
        "summary": "",
        "kf_ref": kf_ref.path, # we want the path
        "meal_plan": ""
    })
    # save references   
    user_ref = user_ref.get().to_dict()
    kf_ref =  {}

    return user_ref, kf_ref

def grab_db_user_data(user_fname: str, user_lname: str):
    """
    Stateless API. Used to grab user data from the database
    """
    db = firestore.client()
    users = db.collection("convos")\
        .where(filter=firestore.firestore.FieldFilter("fname", "==", user_fname))\
        .where(filter=firestore.firestore.FieldFilter("lname", "==", user_lname))\
        .get()
    
    if len(users) == 0:
        return create_db_user(user_fname, user_lname)
    
    user_ref = users[0]

    user_data = user_ref.to_dict()
    # get key facts
    kf_ref_path = user_data.get("kf_ref")
    key_facts = db.document(kf_ref_path).get().to_dict()
    # chose the user data we need
    user_data = {
        "messages": user_data.get("messages", []),
        "responses": user_data.get("responses", []),
        "summary": user_data.get("summary", ""),
        "meal_plan": user_data.get("meal_plan", ""),
    }
    # return user data and key facts
    return user_data, key_facts

def save_db_user_data(fname: str, lname: str, user_data: dict, key_facts: dict) -> tuple[bool, str]:
    """
    Stateless API. Used to save user data to the database
    """
    if (user_data.get("messages") == [] and user_data.get("responses") == []):
        return False, "No user data to save"
    
    db = firestore.client()
    # find the user
    users = db.collection("convos")\
        .where(filter=firestore.firestore.FieldFilter("fname", "==", fname))\
        .where(filter=firestore.firestore.FieldFilter("lname", "==", lname)).get()
    
    if len(users) == 0:
        return False, "User not found"
    
    user_ref = users[0].reference
    
    # update user data
    user_ref.update(user_data)

    # update key facts
    user_doc = user_ref.get()
    user_doc_data = user_doc.to_dict()
    # if key_facts != {}:
    #     kf_ref_path = user_doc_data.get("kf_ref")
    #     kf_ref = db.document(kf_ref_path)
    #     kf_ref.update(key_facts)

    return True, "User data saved"

class HumanExternalDataStore:
    def __init__(self, user_fname: str, user_lname: str, requester_url: str):
        self.msg_chain = list[BaseMessage]() # list of HumanMessage and AIMessage

        # allow user to select model across multiple
        self.model = "gpt-4o-mini"
        self.chat = ChatOpenAI(model=self.model)
        self.fname = user_fname
        self.lname = user_lname
        self.structured_data = StructuredData(messages=[], responses=[], summary="", meal_plan="")
        self.unstructured_data = UnstructuredData(key_facts={})
        self.requester_url = requester_url
        self.last_langchain_rtt = 0

        # use fname and lname to get user id. Thats our authentication
        print("retrieving user id...")
        self.structured_data, self.unstructured_data["key_facts"] = grab_db_user_data(user_fname, user_lname)


        # populate msg_chain
        for i, m in enumerate(self.structured_data["messages"]):
            self.msg_chain.append(HumanMessage(content=m))
            self.msg_chain.append(AIMessage(content=self.structured_data["responses"][i]))


    def close(self):
        # save summary and key facts
        self.update_summary()
        # self.update_key_facts()

        # split messages in msg_chain into messages (HumanMessage) and responses (AIMessage)
        # reset messages and responses to ensure double entries into Firestore dont happen
        msgs = []
        resps = []
        for m in self.msg_chain:
            if isinstance(m, HumanMessage):
                msgs.append(m.content.strip())
            elif isinstance(m, AIMessage):
                resps.append(m.content.strip())
        
        # limit messages and responses to 20
        msgs = msgs[-20:]
        resps = resps[-20:]

        self.structured_data["messages"] = msgs
        self.structured_data["responses"] = resps
        print("structured_data: ", self.structured_data)
        # save to database
        return save_db_user_data(self.fname, self.lname, self.structured_data, self.unstructured_data)

    def chat_guardrails(self, human_message: str):
        """
        Used to check if the human message is within guardrails of medical/fitness/nutrition advice
        """
        if human_message == "":
            return False

        # invoke chat
        chain = ChatOpenAI(model="gpt-4o-mini") | PydanticOutputParser(pydantic_object=Guardrail)
        result = chain.invoke([HumanMessage(content="""
            Determine if the following message is within the realms of medical/fitness/nutrition advice.
            Message: {human_message}
            Return a JSON object with the following fields:
            - reasoning: a short explanation of your reasoning
            - is_health_related: True if the message is within the realms of medical/fitness/nutrition advice, False otherwise
        """.format(human_message=human_message))])
        if isinstance(result, Guardrail):
            return result.is_health_related
        else:
            return False

    
    def invoke_chat(self, messages: list[BaseMessage], ret_type: str):
        """ Used to invoke the chat model and return the result in the specified format """
        try:
            if self.model.startswith("gpt"):
                self.chat = ChatOpenAI(model=self.model)
            elif self.model.startswith("gemini"):
                self.chat = ChatGoogleGenerativeAI(model=self.model)
            elif self.requester_url.startswith("http://localhost"):
                self.chat = ChatOllama(model=self.model)   
        except Exception as e:
            print(e)
            return "The model is currently down. Please try again later."
        if ret_type == "json":
            parser = JsonOutputParser()
            try:
                result = self.chat.invoke(messages)
                parsed_result = parser.invoke(result)
                return parsed_result
            except Exception as e:
                reformat_msg = HumanMessage(content=f"""
                    Please reformat {result.content.strip()} as a valid JSON object.
                    RETURN ONLY THE REFORMATTED JSON OBJECT
                """)
                second_try = self.chat.invoke([reformat_msg])
                second_parsed = parser.invoke(second_try)
                return second_parsed
        elif ret_type == "str":
            chain = self.chat | StrOutputParser()
            result = chain.invoke(messages)
            return result
        else:
            raise ValueError("Invalid return type")

    def update_summary(self):
        "Called by API when summary needs to be updated (end of question-answer) Update the summary within the PT Data points"
        # update the summary
        sum_upd = HumanMessage(content="""
            Based on the the following summary, key facts and last 8 messages, update the summary.
            Make as few changes to the summary, keep the key pieces of information still there.
            If the summary is empty/meaningless, create a new summary. \n
            Summary: {summary} \n
            Here are the last 8 messages: {last_8_messages} \n
            RETURN ONLY THE SUMMARY AS A STRING
        """.format(
            summary=self.structured_data["summary"], 
            last_8_messages=("|||".join([ "Message "+str(i+1)+": "+m.content.strip()  for i, m in enumerate(self.msg_chain[-8:])]))
        ))

        # invoke chat
        self.structured_data["summary"] = self.invoke_chat(self.msg_chain + [sum_upd], "str")
        
    def update_key_facts(self):
        "Called by API when key facts need to be updated (end of question-answer) Update the key facts within the PT Data points"
        # update the messages and responses and limit to 20
        
        kf_upd = HumanMessage(content="""
            Based on the the following message chain and key facts, update the key facts. 
            The key facts should pertain to health, fitness and nutrition fact that are relevant to the user.
            Be efficient, only update the key facts that have changed. Have as few changes as possible.
            Both the key and value are strings. If there are nothing meaningful, return an empty dictionary.
            Summary of the conversation: {summary}
            Key Facts so far: {key_facts}
            RETURN ONLY THE KEY FACTS AS A DICTIONARY OF KEY VALUE PAIRS
        """.format(
            summary=self.structured_data["summary"],
            key_facts=self.unstructured_data["key_facts"], 
        ))
        # invoke chat
        try:
            output = self.invoke_chat(self.msg_chain + [kf_upd], "json")
            if type(output) == list:
                self.unstructured_data["key_facts"] = output
        except Exception as e:
            self.unstructured_data["key_facts"] = {}
            print("Error updating key facts: ", e)

    def call_chat(self, human_message: str):
        """
        Used to call the chat model and return the result in the specified format
        """
        # handle guardrails first
        guardrail_health_related = self.chat_guardrails(human_message)
        print("Passed Guardrails: ", guardrail_health_related)
        if not guardrail_health_related:
            return "The message sent is not within the realms of medical/fitness/nutrition advice. Please rephrase your question."
        # add human message to msg_chain
        start_time = time()
        if "meal plan" in human_message.lower():                
            self.change_meal_plan(human_message)
            ai_msg = "The meal plan needs to be changed. Please wait while I update it."
            self.msg_chain.append(AIMessage(content="Request Fullfilled."))
        else:
            human_msg = HumanMessage(content="""
                Here is the summary of the conversation: {summary}
                Here is the human message: {human_message}
                Here is the current meal plan: {meal_plan}
                Keep your answer short, concise and to the point. Don't use markdown, bold, italic, etc.
            """.format(
                # key_facts=self.unstructured_data["key_facts"],
                summary=self.structured_data["summary"],
                human_message=human_message,
                meal_plan=self.structured_data["meal_plan"]
            ))
            # invoke chat
            try: 
                ai_msg = self.invoke_chat(self.msg_chain[-6:] + [human_msg], "str")
                if ai_msg.strip() == "":
                    ai_msg = "I am not sure how to respond to that. Can you please rephrase your question?"
            except Exception as e:
                return "I am not sure how to respond to that. Can you please rephrase your question?"

        self.msg_chain.append(AIMessage(content=ai_msg))

        human_msg_simplified = HumanMessage(content=human_message)
        self.msg_chain.append(human_msg_simplified)
        end_time = time()
        self.last_langchain_rtt = end_time - start_time
        print(f"Lang to GPT and back RTT: {self.last_langchain_rtt} seconds")

        # update unstructured data
        self.update_summary()
        # self.update_key_facts()
        return ai_msg
    
    def determine_if_meal_plan_change_needed(self, human_message: str, ai_message:str):
        """
        Used to determine if the meal plan needs to be changed using key facts, summary and last 8 messages.
        Too inconsistent to use. Must be changed in the future
        """
        return False
        # invoke chat
        result = self.chat.invoke(
            [HumanMessage(content="""
            Here is the existing meal plan: {meal_plan}
            Here is the key facts: [ {key_facts} ]
            Here is the summary of the conversation: {summary}
            Here is what the user wants: {last_message}
            Response to the user's wants: {last_response}
            determine if the meal plan needs to be changed. 
            If the users wants is a question that doesn't explicitly mention the words "meal plan" return ONLY False
            If the response to the user's wants includes something that looks like a meal plan return ONLY True
            RETURN ONLY True OR False """
        .format(
            meal_plan=self.structured_data["meal_plan"],
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            last_message=human_message,
            last_response=ai_message
        ))])

        print(result.content.strip())
        result = True if result.content.strip() == "True" else False
        return result
    
    def change_meal_plan(self, human_message: str):
        """
        If the meal plan needs to be changed, change it
        """
        # invoke chat
        result = self.invoke_chat([HumanMessage(content="""
            Here is the existing meal plan: {meal_plan}
            Here is the summary of the conversation: {summary}
            Here is what the user wants: {last_message}
            The meal plan needs to change. What should the new meal plan be? Make minimal changes to the existing meal plan while PIORITIZING THE USERS WANTS.
            ONLY INCLUDE INFORMATION PERTAINING TO A MEAL PLAN
            RETURN ONLY THE NEW MEAL PLAN AS A STRING
        """.format(
            meal_plan=self.structured_data["meal_plan"],
            summary=self.structured_data["summary"],
            last_message=human_message
        ))], "str")
        self.structured_data["meal_plan"] = result