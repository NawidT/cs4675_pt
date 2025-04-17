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
    meal_plan: str # meal plan of the conversation
# TECHNICAL DECISION: focused on data made/changed this session and for short term use
class UnstructuredData(TypedDict):
    key_facts: dict[str, str] # key facts of the conversation

cred = credentials.Certificate("backend/serviceAccountKey.json")
firebase_admin.initialize_app(cred)


# pydantic model with reasoning and is_health_related
class Guardrail(BaseModel):
    reasoning: str
    is_health_related: bool


def create_db_user(user_fname: str, user_lname: str):
    """
    Stateless API. Used to create a new user in the database
    """
    db = firestore.client()

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
        "kf_ref": kf_ref,
        "meal_plan": ""
    })
    # close db
    db.close()

    return user_ref.to_dict(), kf_ref.to_dict()

def grab_db_user_data(user_fname: str, user_lname: str):
    """
    Stateless API. Used to grab user data from the database
    """
    db = firestore.client()
    user_ref = db.collection("convos")\
        .where(filter=firestore.firestore.FieldFilter("fname", "==", user_fname))\
        .where(filter=firestore.firestore.FieldFilter("lname", "==", user_lname))\
        .get()
    
    if user_ref == []:
        return create_db_user(user_fname, user_lname)
    
    # get first user data
    user_ref = user_ref[0]
    
    # get key facts
    kf_ref = user_ref.get("kf_ref")
    key_facts = kf_ref.get().to_dict()

    user_data = user_ref.to_dict()

    # close db
    db.close()

    # return user data and key facts
    return user_data, key_facts

def save_db_user_data(fname: str, lname: str, user_data: dict, key_facts: dict) -> tuple[bool, str]:
    """
    Stateless API. Used to save user data to the database
    """
    db = firestore.client()
    # find the user
    user_ref = db.collection("convos").where(filter=firestore.firestore.FieldFilter("fname", "==", fname))\
        .where(filter=firestore.firestore.FieldFilter("lname", "==", lname)).get()[0]
    
    if len(user_ref) == 0:
        return False, "User not found"
    
    # update user data
    user_ref.update(user_data)
    # update key facts
    kf_ref = user_ref.get("kf_ref")
    kf_ref.update(key_facts)
    # close db
    db.close()

    return True, "User data saved"

class HumanExternalDataStore:
    def __init__(self, user_fname: str, user_lname: str):
        self.msg_chain = list[BaseMessage]() # list of HumanMessage and AIMessage
        self.chat = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.fname = user_fname
        self.lname = user_lname
        self.structured_data = StructuredData(messages=[], responses=[], summary="", meal_plan="")
        self.unstructured_data = UnstructuredData(key_facts={})

        # use fname and lname to get user id. Thats our authentication
        print("retrieving user id...")
        self.structured_data, self.unstructured_data["key_facts"] = grab_db_user_data(user_fname, user_lname)


        # populate msg_chain
        for i, m in enumerate(self.structured_data["messages"]):
            self.msg_chain.append(HumanMessage(content=m))
            self.msg_chain.append(AIMessage(content=self.structured_data["responses"][i]))

        # remove messages and responses from structured data, since we are using msg_chain
        # self.structured_data.pop("messages")
        # self.structured_data.pop("responses")

    def close(self):
        # save summary and key facts
        self.update_summary()
        self.update_key_facts()

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

        # save to database
        save_db_user_data(self.fname, self.lname, self.structured_data, self.unstructured_data)

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

    def update_summary(self):
        "Called by API when summary needs to be updated (end of question-answer) Update the summary within the PT Data points"
        # update the summary
        sum_upd = HumanMessage(content="""
            Based on the the following summary, key facts and last 8 messages, update the summary.
            Make as few changes to the summary, keep the key pieces of information still there.
            If the summary is empty/meaningless, create a new summary. \n
            Summary: {summary} \n
            Key Facts: {key_facts}. \n
            Here are the last 8 messages: {last_8_messages} \n
            RETURN ONLY THE SUMMARY AS A STRING
        """.format(
            summary=self.structured_data["summary"], 
            key_facts=(", ".join([str(k)+" : "+str(v)  for k,v in self.unstructured_data["key_facts"].items()])),
            last_8_messages=("|||".join([ "Message "+str(i+1)+": "+m.content.strip()  for i, m in enumerate(self.msg_chain[-8:])]))
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
            Here is the meal plan: {meal_plan}
            Keep your answer short, concise and to the point. Don't use markdown, bold, italic, etc.
            If the meal plan needs to be changed, just mention that "The meal plan needs to be changed" and nothing else.             
        """.format(
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            human_message=human_message,
            meal_plan=self.structured_data["meal_plan"]
        ))
        print("invoking chat...")
        # invoke chat
        ai_msg = self.invoke_chat(self.msg_chain + [human_msg], "str")
        # add ai message to msg_chain
        human_msg_simplified = HumanMessage(content=human_message)
        self.msg_chain.append(human_msg_simplified)
        self.msg_chain.append(AIMessage(content=ai_msg))

        # update unstructured data
        self.update_summary()
        self.update_key_facts()

        # check if meal plan needs to be changed
        meal_plan_change_needed = self.determine_if_meal_plan_change_needed()
        if meal_plan_change_needed:
            self.change_meal_plan()

        return ai_msg
    
    def determine_if_meal_plan_change_needed(self):
        """
        Used to determine if the meal plan needs to be changed using key facts, summary and last 8 messages
        """
        # print chat prompt
        print("""
            Based on the the following, determine if the meal plan needs to be changed.
            Key Facts: {key_facts}
            Summary: {summary}
            Existing Meal Plan: {meal_plan}
            Here are the last 8 messages: {last_8_messages}
            RETURN ONLY True OR False
        """.format(
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            meal_plan=self.structured_data["meal_plan"],
            last_8_messages=("|||".join([ "Message "+str(i+1)+": "+m.content  for i, m in enumerate(self.msg_chain[-8:])]))
        ))

        # invoke chat
        result = self.chat.invoke([HumanMessage(content="""
            Based on the the following, determine if the meal plan needs to be changed.
            Key Facts: {key_facts}
            Summary: {summary}
            Existing Meal Plan: {meal_plan}
            RETURN ONLY True OR False
        """.format(
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            meal_plan=self.structured_data["meal_plan"]
        ))])
        print(result.content.strip())
        result = True if result.content.strip() == "True" else False
        return result

    def change_meal_plan(self):
        """
        If the meal plan needs to be changed, change it
        """
        # invoke chat
        result = self.invoke_chat([HumanMessage(content="""
            Here is the exisitng meal plan: {meal_plan}
            Here is the key facts: [ {key_facts} ]
            Here is the summary: {summary}
            Here is the last message: {last_message}
            The meal plan needs to change. What should the new meal plan be?
            RETURN ONLY THE NEW MEAL PLAN
        """.format(
            meal_plan=self.structured_data["meal_plan"],
            key_facts=(", ".join([k+" : "+v  for k,v in self.unstructured_data["key_facts"].items()])),
            summary=self.structured_data["summary"],
            last_message=self.msg_chain[-1].content
        ))], "str")
        self.structured_data["meal_plan"] = result
    
# db = HumanExternalDataStore("Nawid", "Tahmid")

# db.call_chat("What are some tips I can use to improve my sleep?")

# del db