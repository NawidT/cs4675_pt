import firebase_admin
from firebase_admin import credentials, firestore
from typing_extensions import TypedDict
from PIL import Image
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage


# TECHNICAL DECISION: support only one conversation per user    
class StructuredData(TypedDict):
    messages: list[str] # store last 20 messages
    responses: list[str] # store last 20 responses
    summary: str # summary of the conversation
    last_updated: str # last updated timestamp
    fname: str
    lname: str
    age: int
    prev_static_data: dict[str, Image.Image] # previous static data of the conversation

# TECHNICAL DECISION: focused on data made/changed this session and for short term use
class UnstructuredData(TypedDict):
    key_facts: dict[str, str] # key facts of the conversation
    static_data: dict[str, Image.Image] # static data of the conversation

class PTData(TypedDict):
    structured_data: StructuredData
    unstructured_data: UnstructuredData

class HumanExternalDataStore:
    def __init__(self, user_fname: str, user_lname: str):
        cred = credentials.Certificate("backend/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()

        self.chat = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # use fname and lname to get user id
        try:
            self.user_id = self.db.collection("convos").where("fname", "==", user_fname).where("lname", "==", user_lname).get()[0].id
            print(f"User {user_fname} {user_lname} found with id {self.user_id}")
        except:
            raise ValueError("User not found")
        
        # fetch data from db
        self.structured_data = self.db.collection("convos").document(self.user_id).get().to_dict()
        print(self.structured_data)
        
        # manually create unstructured data
        self.unstructured_data = UnstructuredData(
            key_facts={},
            static_data={}
        )

        self.init_facts()

        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data
        )
    
    def get_structured_data(self):
        return self.structured_data
    
    def get_unstructured_data(self):
        return self.unstructured_data
    
    def get_pt_data(self):
        return self.pt_data
    
    def update_structured_data(self, structured_data: StructuredData):
        self.structured_data = structured_data
        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data)
    
    def update_unstructured_data(self, unstructured_data: UnstructuredData):
        self.unstructured_data = unstructured_data
        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data)
    
    def update_db(self):
        self.db.collection("convos").document(self.user_id).update({
            "age": self.structured_data["age"],
            "fname": self.structured_data["fname"],
            "lname": self.structured_data["lname"],
            "messages": self.structured_data["messages"],
            "responses": self.structured_data["responses"],
            "summary": self.structured_data["summary"],
            "last_updated": self.structured_data["last_updated"]
        })

    def init_facts(self):
        """ Initialize facts from messages, responses, and summary """
        # get last 20 messages and responses
        messages = self.structured_data["messages"]
        responses = self.structured_data["responses"]
        summary = self.structured_data["summary"]

        messages = []
        for i, m in enumerate(messages):
            messages.insert(0, HumanMessage(content=m))
            messages.insert(0, AIMessage(content=responses[i]))

        print(messages)

        # parse into structured data
        prompt = """
            Based on the following message chain and summary, extract the key facts of the conversation.
            Summary: {summary}

            Return the key facts in a JSON format with list of key-value pairs.
            Example:
            {{
                key_facts:[
                    key1: description of fact 1,
                    key2: description of fact 2,
                ]
            }}

            Return the JSON format only, nothing else.
        """.format(summary=summary)
        # parse into structured data
        parser = PydanticOutputParser(pydantic_object=list[dict[str, str]])
        prompt = PromptTemplate(
            template=prompt
        )
        chain = prompt | self.chat
        result = chain.invoke(messages)
        print(result)
        

    def parse_chat(self, human_input: str, ai_input: str, static_data: list[Image.Image]):
        # parse chat into structured data
        pass

    
HumanExternalDataStore("Bukayo", "Saka")