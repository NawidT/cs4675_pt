import openai # For OpenRouter API
import google.generativeai
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import certifi
import os

class LLMQuery:
    def __init__(self, chat_history, information, question):
        self.chat_history = chat_history
        self.information = information
        self.question = question
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

    def _prompt_openrouter(self, prompt : str, model: str):
        client = openai.OpenAI(
            api_key=self.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a plain text assistant. Do not use tool calls or function calls."},
                {"role": "user", "content": prompt}
            ]
        )
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                print(tool_call.function.name)
                print(tool_call.function.arguments)
        return response.choices[0].message.content
    def _prompt_gemini(self, prompt : str):
        google.generativeai.configure(api_key=self.GEMINI_API_KEY)
        model = google.generativeai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text

    def _evaluate_responses(self, responses):
        evaluation_prompt = self._create_evaluation_query(responses)
        best_response_idx = self._prompt_openrouter(evaluation_prompt, "anthropic/claude-3-haiku")
        best_response_model = list(responses.keys())[int(best_response_idx) - 1] # Get the model name from the index
        best_response = responses[best_response_model]
        return best_response
    def _prompt_llms(self, prompt: str):
        results = {}
        # Send the prompts in parallel to the LLMs
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._prompt_openrouter, prompt, "deepseek/deepseek-r1:free"): "deepseek",
                executor.submit(self._prompt_gemini, prompt): "gemini",
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
