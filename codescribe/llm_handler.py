"""This module provides the `LLMHandler` class, which facilitates interaction with various Large Language Models (LLMs) like Groq and Gemini.  It manages multiple API keys, handles rate limits and errors gracefully, and provides methods for generating both structured JSON documentation and plain text responses from the chosen LLM."""
import time
import json
from typing import Dict, List, Callable, Any, Union
import google.generativeai as genai
from groq import Groq, RateLimitError
from dataclasses import dataclass

@dataclass
class APIKey:
    """Dataclass to store API key information for different LLM providers.

:param provider: The name of the LLM provider (e.g., "groq", "gemini").
:type provider: str
:param key: The API key for the provider.
:type key: str
:param model: The specific model to use with the provider.
:type model: str"""
    provider: str
    key: str
    model: str

def no_op_callback(message: str):
    """A simple callback function that prints a message to the console.  Used as a default for progress updates when no custom callback is provided."""
    print(message)

class LLMHandler:

    def __init__(self, api_keys: List[APIKey], progress_callback: Callable[[str], None]=no_op_callback):
        """Initializes a new instance of the `LLMHandler` class.

:param api_keys: A list of `APIKey` objects, each specifying an LLM provider, API key, and model.
:type api_keys: List[APIKey]
:param progress_callback: A callback function to report progress updates. Defaults to `no_op_callback`.
:type progress_callback: Callable[[str], None]"""
        self.clients = []
        self.progress_callback = progress_callback
        for key in api_keys:
            try:
                if key.provider == 'groq':
                    client = Groq(api_key=key.key, max_retries=0)
                    self.clients.append({'provider': 'groq', 'client': client, 'model': key.model, 'id': f'groq_{key.key[-4:]}'})
                elif key.provider == 'gemini':
                    genai.configure(api_key=key.key)
                    self.clients.append({'provider': 'gemini', 'client': genai.GenerativeModel(key.model), 'model': key.model, 'id': f'gemini_{key.key[-4:]}'})
                self.progress_callback(f"Successfully configured client: {self.clients[-1]['id']}")
            except Exception as e:
                self.progress_callback(f'Failed to configure client for key ending in {key.key[-4:]}: {e}')
        if not self.clients:
            self.progress_callback('Warning: No LLM clients were successfully configured.')
        self.cooldowns: Dict[str, float] = {}
        self.cooldown_period = 30

    def _attempt_generation(self, generation_logic: Callable[[Dict], Any]) -> Any:
        """A private generic method to handle the client iteration, cooldown, and error handling logic.

This method iterates through configured LLM clients, checking for cooldowns and handling potential errors like rate limits and API key issues.  It executes the provided generation logic and returns the result. If all clients fail, it raises a RuntimeError.

:param generation_logic: A function that takes a client_info dictionary and executes the specific LLM call, returning the processed content.
:type generation_logic: Callable[[Dict], Any]
:raises ValueError: If no LLM clients are configured.
:raises RuntimeError: If all clients fail to generate a response."""
        if not self.clients:
            raise ValueError('No LLM clients configured.')
        for client_info in self.clients:
            client_id = client_info['id']
            if client_id in self.cooldowns:
                if time.time() - self.cooldowns[client_id] < self.cooldown_period:
                    self.progress_callback(f'Skipping {client_id} (on cooldown).')
                    continue
                else:
                    self.progress_callback(f'Cooldown expired for {client_id}.')
                    del self.cooldowns[client_id]
            try:
                return generation_logic(client_info)
            except RateLimitError:
                self.progress_callback(f'Rate limit hit for {client_id}. Placing it on a {self.cooldown_period}s cooldown.')
                self.cooldowns[client_id] = time.time()
                continue
            except Exception as e:
                self.progress_callback(f'An error occurred with {client_id}: {e}. Placing on cooldown and trying next client.')
                self.cooldowns[client_id] = time.time()
                continue
        raise RuntimeError('Failed to get a response from any available LLM provider.')

    def generate_documentation(self, prompt: str) -> Dict:
        """Generates structured JSON documentation using available clients.

This method uses the `_attempt_generation` method to iterate through clients and generate JSON documentation using the specified prompt. The prompt should be formatted for the expected JSON output. Gemini requires the prompt to explicitly specify JSON generation.

:param prompt: The prompt for the LLM, formatted to generate JSON.
:type prompt: str
:return: A dictionary containing the generated JSON documentation.
:rtype: Dict"""

        def _generate(client_info: Dict) -> Dict:
            client_id = client_info['id']
            self.progress_callback(f"Attempting to generate JSON docs with {client_id} ({client_info['model']})...")
            if client_info['provider'] == 'groq':
                response = client_info['client'].chat.completions.create(messages=[{'role': 'user', 'content': prompt}], model=client_info['model'], temperature=0.1, response_format={'type': 'json_object'})
                content = response.choices[0].message.content
            elif client_info['provider'] == 'gemini':
                response = client_info['client'].generate_content(prompt)
                content = response.text.strip().lstrip('```json').rstrip('```').strip()
            return json.loads(content)
        return self._attempt_generation(_generate)

    def generate_text_response(self, prompt: str) -> str:
        """Generates a plain text response using available clients.

This method leverages the `_attempt_generation` helper to manage client selection and error handling.  It is designed to return plain text, unlike the JSON-specific documentation method.

:param prompt: The prompt for the LLM.
:type prompt: str
:return: The generated text response.
:rtype: str"""

        def _generate(client_info: Dict) -> str:
            client_id = client_info['id']
            self.progress_callback(f"Attempting to generate text with {client_id} ({client_info['model']})...")
            if client_info['provider'] == 'groq':
                response = client_info['client'].chat.completions.create(messages=[{'role': 'user', 'content': prompt}], model=client_info['model'], temperature=0.2)
                return response.choices[0].message.content
            elif client_info['provider'] == 'gemini':
                response = client_info['client'].generate_content(prompt)
                return response.text.strip()
        return self._attempt_generation(_generate)