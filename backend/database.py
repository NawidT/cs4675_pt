import firebase_admin
from firebase_admin import credentials, firestore
from typing_extensions import TypedDict
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# TECHNICAL DECISION: support only one conversation per user    
class StructuredData(TypedDict):
    messages: list[str] # store last 20 messages
    responses: list[str] # store last 20 responses
    summary: str # summary of the conversation

# TECHNICAL DECISION: focused on data made/changed this session and for short term use
class UnstructuredData(TypedDict):
    key_facts: dict[str, str] # key facts of the conversation

class PTData(TypedDict):
    structured_data: StructuredData
    unstructured_data: UnstructuredData

class HumanExternalDataStore:
    def __init__(self, user_fname: str, user_lname: str):
        cred = credentials.Certificate("backend/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        self.msg_chain = []
        self.chat = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.kf_ref = ""

        # use fname and lname to get user id
        try:
            self.user_id = self.db.collection("convos") \
                .where(filter=firestore.firestore.FieldFilter("fname", "==", user_fname)) \
                .where(filter=firestore.firestore.FieldFilter("lname", "==", user_lname)) \
                .get()[0].id
            print(f"User {user_fname} {user_lname} found with id {self.user_id}")
        except:
            raise ValueError("User not found")
        
        # fetch data from db
        self.structured_data = self.db.collection("convos").document(self.user_id).get().to_dict()
        print(self.structured_data)

        # populate msg_chain
        for i, m in enumerate(self.structured_data["messages"]):
            self.msg_chain.insert(0, HumanMessage(content=m))
            self.msg_chain.insert(0, AIMessage(content=self.structured_data["responses"][i]))
        
        # manually create unstructured data
        self.unstructured_data = UnstructuredData(
            key_facts={},
            static_data={}
        )

        # load key facts
        self.kf_ref = self.init_facts()
        if not self.kf_ref:
            raise ValueError("Key facts not found")
            

        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data
        )

    def __del__(self):
        # save summary and key facts
        self.update_summary()
        self.update_key_facts()

        # split messages in msg_chain into messages (HumanMessage) and responses (AIMessage)
        for m in self.msg_chain:
            if isinstance(m, HumanMessage):
                self.structured_data["messages"].append(m.content.strip())
            elif isinstance(m, AIMessage):
                self.structured_data["responses"].append(m.content.strip())
        
        # limit messages and responses to 20
        self.structured_data["messages"] = self.structured_data["messages"][-20:]
        self.structured_data["responses"] = self.structured_data["responses"][-20:]

        # save to database
        self.update_db(self.structured_data, self.unstructured_data)

        self.db.close()
    
    def invoke_chat(self, messages: list[BaseMessage], ret_type: str):
        """ Used to invoke the chat model and return the result in the specified format """
        if ret_type == "json":
            chain = self.chat | JsonOutputParser()
            try:
                result = chain.invoke(messages)
                print(result)
                if isinstance(result, dict):
                    return result
                else:
                    raise ValueError("Invalid JSON object")
            except Exception as e:
                reformat_msg = HumanMessage(content=f"""
                    Please reformat {result} as a valid JSON object.
                    RETURN ONLY THE REFORMATTED JSON OBJECT
                """)
                second_try = self.chat.invoke([reformat_msg])
                print(second_try)
                return second_try
        elif ret_type == "str":
            chain = self.chat | StrOutputParser()
            result = chain.invoke(messages)
            return result
        else:
            raise ValueError("Invalid return type")
    
    def update_db(self, structured_data: StructuredData, unstructured_data: UnstructuredData):
        """First update unstructured data, then structured data, then save to db"""
        self.structured_data = structured_data
        self.unstructured_data = unstructured_data
        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data
        )

        self.db.collection("convos").document(self.user_id).update({
            "messages": self.structured_data["messages"],
            "responses": self.structured_data["responses"],
            "summary": self.structured_data["summary"],
        })

        # update key facts in kf_ref
        user_doc = self.db.collection("convos").document(self.user_id).get().to_dict()
        kf_ref = user_doc.get('kf_ref')
        kf_ref.update({
            "key_facts": self.unstructured_data["key_facts"]
        })

    def init_facts(self):
        """
        Retrieves key facts document from Firestore if it exists.
        """
        # Get the document reference for key facts from the user's document
        user_doc = self.db.collection("convos").document(self.user_id).get().to_dict()
        kf_ref = user_doc.get('kf_ref')
        
        # Retrieve the key facts document using the reference
        if kf_ref:
            key_facts = kf_ref.get().to_dict()
            print("Retrieved key facts:", key_facts)
            return key_facts
        else:
            print("No key facts reference found for this user")
            return None


    def update_summary(self):
        "Called by API when summary needs to be updated (end of question-answer) Update the summary within the PT Data points"
        # update the summary
        sum_upd = HumanMessage(content="""
            Based on the the following message chain and summary, update the summary.
            Make as few changes to the summary, keep the key pieces of information still there.
            Summary: {summary}                 
            Here are the key facts as key value pairs: {key_facts}. 
            RETURN ONLY THE SUMMARY AS A STRING
        """.format(
            summary=self.structured_data["summary"], 
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()]))
        ))

        # invoke chat
        self.structured_data["summary"] = self.invoke_chat(self.msg_chain + [sum_upd], "str")
        

    def update_key_facts(self):
        "Called by API when key facts need to be updated (end of question-answer) Update the key facts within the PT Data points"
        # update the messages and responses and limit to 20
        
        kf_upd = HumanMessage(content="""
            Based on the the following message chain and key facts, update the key facts.
            Summary: {summary}      
            Key Facts: {key_facts}
            RETURN ONLY THE KEY FACTS AS A LIST OF KEY VALUE PAIRS
        """.format(
            summary=self.structured_data["summary"],
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])), 
        ))

        # invoke chat
        self.unstructured_data["key_facts"] = self.invoke_chat(self.msg_chain + [kf_upd], "json")
        print(self.unstructured_data["key_facts"])
        
        
    
HumanExternalDataStore("Bukayo", "Saka")