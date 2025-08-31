import time
import json
from typing import Dict, List, Callable, Any, Union
import google.generativeai as genai
from groq import Groq, RateLimitError

# Assuming your config.py looks something like this for the example to be runnable
from dataclasses import dataclass
@dataclass
class APIKey:
    provider: str
    key: str
    model: str

# A simple callback for demonstration
def no_op_callback(message: str):
    print(message)

class LLMHandler:
    def __init__(self, api_keys: List[APIKey], progress_callback: Callable[[str], None] = no_op_callback):
        self.clients = []
        self.progress_callback = progress_callback
        for key in api_keys:
            try:
                if key.provider == "groq":
                    # --- SOLUTION ---
                    # Disable the library's internal retries. Let our handler manage failovers.
                    # This gives us immediate control when a rate limit is hit.
                    client = Groq(api_key=key.key, max_retries=0) 
                    self.clients.append({
                        "provider": "groq",
                        "client": client,
                        "model": key.model,
                        "id": f"groq_{key.key[-4:]}"
                    })
                elif key.provider == "gemini":
                    # Note: Gemini's library is less explicit about HTTP retries in its
                    # standard configuration, but the principle remains the same. The main
                    # offender is usually HTTP-based libraries like Groq's or OpenAI's.
                    genai.configure(api_key=key.key)
                    self.clients.append({
                        "provider": "gemini",
                        "client": genai.GenerativeModel(key.model),
                        "model": key.model,
                        "id": f"gemini_{key.key[-4:]}"
                    })
                self.progress_callback(f"Successfully configured client: {self.clients[-1]['id']}")
            except Exception as e:
                self.progress_callback(f"Failed to configure client for key ending in {key.key[-4:]}: {e}")
        
        if not self.clients:
            self.progress_callback("Warning: No LLM clients were successfully configured.")

        self.cooldowns: Dict[str, float] = {}
        self.cooldown_period = 30  # 30 seconds

    def _attempt_generation(self, generation_logic: Callable[[Dict], Any]) -> Any:
        """
        A private generic method to handle the client iteration, cooldown, and error handling logic.
        
        Args:
            generation_logic: A function that takes a client_info dictionary and executes
                              the specific LLM call, returning the processed content.
        """
        if not self.clients:
            raise ValueError("No LLM clients configured.")

        # Iterate through a copy of the clients list to allow for potential future modifications
        for client_info in self.clients:
            client_id = client_info["id"]

            # Check and manage cooldown
            if client_id in self.cooldowns:
                if time.time() - self.cooldowns[client_id] < self.cooldown_period:
                    self.progress_callback(f"Skipping {client_id} (on cooldown).")
                    continue
                else:
                    self.progress_callback(f"Cooldown expired for {client_id}.")
                    del self.cooldowns[client_id]
            
            try:
                # Execute the specific generation logic passed to this method
                return generation_logic(client_info)
            
            except RateLimitError:
                self.progress_callback(f"Rate limit hit for {client_id}. Placing it on a {self.cooldown_period}s cooldown.")
                self.cooldowns[client_id] = time.time()
                continue # Try the next client
            except Exception as e:
                # This catches other errors like API key issues, parsing errors, etc.
                self.progress_callback(f"An error occurred with {client_id}: {e}. Placing on cooldown and trying next client.")
                self.cooldowns[client_id] = time.time() # Put faulty clients on cooldown too
                continue

        # If the loop completes without returning, all clients have failed.
        raise RuntimeError("Failed to get a response from any available LLM provider.")

    def generate_documentation(self, prompt: str) -> Dict:
        """
        Generates structured JSON documentation using available clients.
        """
        def _generate(client_info: Dict) -> Dict:
            client_id = client_info["id"]
            self.progress_callback(f"Attempting to generate JSON docs with {client_id} ({client_info['model']})...")
            
            if client_info["provider"] == "groq":
                response = client_info["client"].chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=client_info["model"],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
            
            elif client_info["provider"] == "gemini":
                # For Gemini, you must explicitly ask for JSON in the prompt
                # e.g., prompt = "Generate JSON... " + original_prompt
                response = client_info["client"].generate_content(prompt)
                content = response.text.strip().lstrip("```json").rstrip("```").strip()

            return json.loads(content)

        return self._attempt_generation(_generate)

    def generate_text_response(self, prompt: str) -> str:
        """
        Generates a plain text response using available clients.
        """
        def _generate(client_info: Dict) -> str:
            client_id = client_info["id"]
            self.progress_callback(f"Attempting to generate text with {client_id} ({client_info['model']})...")
            
            if client_info["provider"] == "groq":
                response = client_info["client"].chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=client_info["model"],
                    temperature=0.2,
                )
                return response.choices[0].message.content
            
            elif client_info["provider"] == "gemini":
                response = client_info["client"].generate_content(prompt)
                return response.text.strip()
        
        return self._attempt_generation(_generate)