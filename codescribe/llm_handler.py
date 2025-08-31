import time
import json
from typing import Dict, List, Callable
import google.generativeai as genai
from groq import Groq, RateLimitError



from .config import APIKey

def no_op_callback(message: str):
    print(message)

class LLMHandler:
    def __init__(self, api_keys: List[APIKey], progress_callback: Callable[[str], None] = no_op_callback):
        self.clients = []
        self.progress_callback = progress_callback # NEW
        for key in api_keys:
            if key.provider == "groq":
                self.clients.append({
                    "provider": "groq",
                    "client": Groq(api_key=key.key),
                    "model": key.model,
                    "id": f"groq_{key.key[-4:]}"
                })
            elif key.provider == "gemini":
                genai.configure(api_key=key.key)
                self.clients.append({
                    "provider": "gemini",
                    "client": genai.GenerativeModel(key.model),
                    "model": key.model,
                    "id": f"gemini_{key.key[-4:]}"
                })
        
        self.cooldowns: Dict[str, float] = {}
        self.cooldown_period = 30  # 30 seconds

    def generate_documentation(self, prompt: str) -> Dict:
        """
        Tries to generate documentation using available clients, handling rate limits and failovers.
        """
        if not self.clients:
            raise ValueError("No LLM clients configured.")

        for client_info in self.clients:
            client_id = client_info["id"]

            # Check if the client is on cooldown
            if client_id in self.cooldowns:
                if time.time() - self.cooldowns[client_id] < self.cooldown_period:
                    self.progress_callback(f"Skipping {client_id} (on cooldown).")
                    continue
                else:
                    # Cooldown has expired
                    del self.cooldowns[client_id]
            
            try:
                self.progress_callback(f"Attempting to generate docs with {client_id} ({client_info['model']})...")
                if client_info["provider"] == "groq":
                    response = client_info["client"].chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=client_info["model"],
                        temperature=0.1,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content
                
                elif client_info["provider"] == "gemini":
                    response = client_info["client"].generate_content(prompt)
                    # Gemini might wrap JSON in ```json ... ```
                    content = response.text.strip().replace("```json", "").replace("```", "").strip()

                return json.loads(content)

            except RateLimitError:
                self.progress_callback(f"Rate limit hit for {client_id}. Placing it on a {self.cooldown_period}s cooldown.")
                self.cooldowns[client_id] = time.time()
                continue
            except Exception as e:
                self.progress_callback(f"An error occurred with {client_id}: {e}. Trying next client.")
                continue

        raise RuntimeError("Failed to generate documentation from all available LLM providers.")
    
    
    def generate_text_response(self, prompt: str) -> str:
        """
        Generates a plain text response from LLMs, handling failovers.
        """
        if not self.clients:
            raise ValueError("No LLM clients configured.")

        for client_info in self.clients:
            client_id = client_info["id"]
            if client_id in self.cooldowns and time.time() - self.cooldowns[client_id] < self.cooldown_period:
                self.progress_callback(f"Skipping {client_id} (on cooldown).")
                continue
            elif client_id in self.cooldowns:
                 del self.cooldowns[client_id]

            try:
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

            except RateLimitError:
                self.progress_callback(f"Rate limit hit for {client_id}. Placing it on a {self.cooldown_period}s cooldown.")
                self.cooldowns[client_id] = time.time()
                continue
            except Exception as e:
                self.progress_callback(f"An error occurred with {client_id}: {e}. Trying next client.")
                continue

        raise RuntimeError("Failed to generate text response from all available LLM providers.")