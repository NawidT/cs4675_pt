from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
import certifi
import os

class LLMQuery:
    def __init__(self, chat_history, information, question):
        self.chat_history = chat_history
        self.information = information
        self.question = question
        # more temperature for more creativity
        self.deepseek_model = ChatOpenAI(model="deepseek/deepseek-r1:free", temperature=0.8, openai_api_key=os.getenv("OPENROUTER_API_KEY"), openai_api_base='https://openrouter.ai/api/v1')
        self.claude_model = ChatOpenAI(model="anthropic/claude-3-haiku", temperature=0.8, openai_api_key=os.getenv("OPENROUTER_API_KEY"), openai_api_base='https://openrouter.ai/api/v1')
        self.gemini_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.8, google_api_key=os.getenv("GEMINI_API_KEY"))
    def _create_base_query(self):
        history = f"Given the following past chat history:\n{self.chat_history}\n\n"
        health_info = f"Given the following health information of the user:\n {self.information}\n\n"
        return history + health_info
    def _create_query(self):
        base_query = self._create_base_query()
        role = f"Assume the role of a health coach and answer the following question:\n {self.question}"
        return base_query + role
    def _create_evaluation_query(self, responses):
        base_query = self._create_base_query()
        role = f"Assume the role of a health coach and pick the best of these 3 responses:\n"
        for i, response_type in enumerate(responses):
            role += f"{i+1}:\n {responses[response_type]}\n\n" 
        role += f"Please output ONLY the number of the best response (1, 2, or 3), and nothing else. No explanation, no quotes, no labels. Just a single number."
        return base_query + role

    def _promp_model(self, prompt : str, model):
        response = model.invoke([HumanMessage(content=prompt), 
                                SystemMessage(content="You are a plain text assistant. Do not use tool calls or function calls.")
        ])
        return response.content

    def _evaluate_responses(self, responses):
        evaluation_prompt = self._create_evaluation_query(responses)
        best_response_idx = self._promp_model(evaluation_prompt, self.deepseek_model)
        try:
            best_response_idx = int(best_response_idx) 
            return responses[best_response_idx]
        except Exception:
            print(f"Evaluation failed: {best_response_idx}. Using fallback response.")
            return responses[1] 
    def _prompt_llms(self, prompt: str):
        results = {}
        # Send the prompts in parallel to the LLMs
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._promp_model, prompt, self.gemini_model): 1,
                executor.submit(self._promp_model, prompt, self.claude_model): 2,
            }
            for future in as_completed(futures):
                llm = futures[future]
                try:
                    results[llm] = future.result()
                except Exception as e:
                    results[llm] = f"Error: {e}"
        return results
    def evaluate_user_query(self):
        query = self._create_query()
        responses = self._prompt_llms(query)
        best_response = self._evaluate_responses(responses)
        return responses, best_response

if __name__ == "__main__":
    load_dotenv()
    # Fix an cert error
    os.environ["SSL_CERT_FILE"] = certifi.where()

    chat_history = "User: How can I improve my diet?\nCoach: Focus on whole foods and balance your meals."
    information = "User is 30 years old, 70 kg, and exercises 3 times a week."
    question = "What should I eat for breakfast?"

    llm_query = LLMQuery(chat_history, information, question)
    responses, best_response = llm_query.evaluate_user_query()
    print(best_response)