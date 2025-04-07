import firebase_admin
from firebase_admin import credentials, firestore
from typing_extensions import TypedDict
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser, PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from pydantic import BaseModel


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

cred = credentials.Certificate("backend/serviceAccountKey.json")
firebase_admin.initialize_app(cred)


# pydantic model with reasoning and is_health_related
class Guardrail(BaseModel):
    reasoning: str
    is_health_related: bool

class HumanExternalDataStore:
    def __init__(self, user_fname: str, user_lname: str):
        self.db = firestore.client()
        self.msg_chain = []
        self.chat = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.kf_ref = ""

        # use fname and lname to get user id
        print("retrieving user id...")
        try:
            self.user_id = self.db.collection("convos") \
                .where(filter=firestore.firestore.FieldFilter("fname", "==", user_fname)) \
                .where(filter=firestore.firestore.FieldFilter("lname", "==", user_lname)) \
                .get()[0].id
            print(f"User {user_fname} {user_lname} found with id {self.user_id}")
        except:
            # create new user
            # Create a new document in keyfacts collection
            self.kf_ref = self.db.collection("keyfacts").document()
            # Initialize the key_facts document with empty data
            self.kf_ref.set({})
            # Create a new user document in convos collection with reference to keyfacts
            user_ref = self.db.collection("convos").document()
            user_ref.set({
                "fname": user_fname,
                "lname": user_lname,
                "messages": [],
                "responses": [],
                "summary": "",
                "kf_ref": self.kf_ref
            })
            self.user_id = user_ref.id
            print(f"New user {user_fname} {user_lname} created")
        
        # fetch data from db
        self.structured_data = self.db.collection("convos").document(self.user_id).get().to_dict()

        # populate msg_chain
        for i, m in enumerate(self.structured_data["messages"]):
            self.msg_chain.append(HumanMessage(content=m))
            self.msg_chain.append(AIMessage(content=self.structured_data["responses"][i]))
        
        # manually create unstructured data
        self.unstructured_data = UnstructuredData(
            key_facts={},
            static_data={}
        )

        # load key facts
        self.kf_ref, self.unstructured_data["key_facts"] = self.init_facts()
        if not self.kf_ref:
            raise ValueError("Key facts not found")

        self.pt_data = PTData(
            structured_data=self.structured_data, 
            unstructured_data=self.unstructured_data
        )

    def close(self):
        # save summary and key facts
        self.update_summary()
        self.update_key_facts()

        # split messages in msg_chain into messages (HumanMessage) and responses (AIMessage)
        # reset messages and responses to ensure double entries into Firestore dont happen
        self.structured_data["messages"] = []
        self.structured_data["responses"] = []
        for m in self.msg_chain:
            if isinstance(m, HumanMessage):
                self.structured_data["messages"].append(m.content.strip())
            elif isinstance(m, AIMessage):
                self.structured_data["responses"].append(m.content.strip())
        
        # limit messages and responses to 20
        self.structured_data["messages"] = self.structured_data["messages"][-20:]
        self.structured_data["responses"] = self.structured_data["responses"][-20:]

        # save to database
        self.save_to_db(self.structured_data, self.unstructured_data)

        self.db.close()

    def chat_guardrails(self, human_message: str):
        """
        Used to check if the human message is within guardrails of medical/fitness/nutrition advice
        """
        if human_message == "":
            return False

        # invoke chat
        chain = self.chat | PydanticOutputParser(pydantic_object=Guardrail)
        result = chain.invoke([HumanMessage(content="""
            Determine if the following message is within the realms of medical/fitness/nutrition advice.
            Message: {human_message}
            Return a JSON object with the following fields:
            - reasoning: a short explanation of your reasoning
            - is_health_related: True if the message is within the realms of medical/fitness/nutrition advice, False otherwise
        """.format(human_message=human_message))])
        print(result)
        if isinstance(result, Guardrail):
            return result.is_health_related
        else:
            return False

    
    def invoke_chat(self, messages: list[BaseMessage], ret_type: str):
        """ Used to invoke the chat model and return the result in the specified format """
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
        
    def init_facts(self):
        """
        Retrieves key facts document from Firestore if it exists.
        """
        # Get the document reference for key facts from the user's document
        user_doc = self.db.collection("convos").document(self.user_id).get().to_dict()
        kf_ref = user_doc.get('kf_ref')
        
        # Retrieve the key facts document using the reference
        key_facts = kf_ref.get().to_dict()
        print("Retrieved key facts:", key_facts)
        return kf_ref, key_facts
    
    def save_to_db(self, structured_data: StructuredData, unstructured_data: UnstructuredData):
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

        # update key facts in kf_ref'
        if self.unstructured_data["key_facts"] != {}:
            self.kf_ref.update({
                k: v for k, v in self.unstructured_data["key_facts"].items()
            })

    def update_summary(self):
        "Called by API when summary needs to be updated (end of question-answer) Update the summary within the PT Data points"
        # update the summary
        sum_upd = HumanMessage(content="""
            Based on the the following message chain and summary, update the summary.
            Make as few changes to the summary, keep the key pieces of information still there.
            Summary: {summary}                 
            Here are the key facts as key value pairs: {key_facts}. 
            If there are nothing meaningful, return an empty string.
            RETURN ONLY THE SUMMARY AS A STRING
        """.format(
            summary=self.structured_data["summary"], 
            key_facts=(", ".join([str(k)+" : "+str(v)  for k,v in self.unstructured_data["key_facts"].items()]))
        ))

        # invoke chat
        self.structured_data["summary"] = self.invoke_chat(self.msg_chain + [sum_upd], "str")
        
    def update_key_facts(self):
        "Called by API when key facts need to be updated (end of question-answer) Update the key facts within the PT Data points"
        # update the messages and responses and limit to 20
        
        kf_upd = HumanMessage(content="""
            Based on the the following message chain and key facts, update the key facts.
            Be efficient, only update the key facts that have changed. Have as few changes as possible.
            Both the key and value are strings. If there are nothing meaningful, return an empty dictionary.
            Key Facts so far: {key_facts}
            RETURN ONLY THE KEY FACTS AS A DICTIONARY OF KEY VALUE PAIRS
        """.format(
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])), 
        ))

        # invoke chat
        self.unstructured_data["key_facts"] = self.invoke_chat(self.msg_chain + [kf_upd], "json")

    def call_chat(self, human_message: str):
        """
        Used to call the chat model and return the result in the specified format
        """
        # handle guardrails first
        print("checking guardrails...")
        guardrail_health_related = self.chat_guardrails(human_message)
        print(guardrail_health_related)
        if not guardrail_health_related:
            return "The message sent is not within the realms of medical/fitness/nutrition advice. Please rephrase your question."

        # add human message to msg_chain
        human_msg = HumanMessage(content="""
            Here is the key facts: {key_facts}
            Here is the summary: {summary}
            Here is the human message: {human_message}
            Keep your answer short, concise and to the point.
        """.format(
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            human_message=human_message
        ))
        print("invoking chat...")
        # invoke chat
        ai_msg = self.invoke_chat(self.msg_chain + [human_msg], "str")
        # add ai message to msg_chain
        human_msg_simplified = HumanMessage(content=human_message)
        self.msg_chain.append(human_msg_simplified)
        self.msg_chain.append(AIMessage(content=ai_msg))

        # update structured data
        self.structured_data["messages"].append(human_message)
        self.structured_data["responses"].append(ai_msg)

        # update unstructured data
        self.update_summary()
        self.update_key_facts()
        return ai_msg
        
    
# db = HumanExternalDataStore("Nawid", "Tahmid")

# db.call_chat("What are some tips I can use to improve my sleep?")

# del db