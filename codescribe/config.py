"""Configures API keys for AI models from environment variables."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing import List

@dataclass
class APIKey:
    """APIKey provider, key, and model."""
    provider: str
    key: str
    model: str

    def __repr__(self):
        """Returns a string representation of the APIKey object."""
        return f"APIKey(provider='{self.provider}', model='{self.model}')"

@dataclass
class Config:
    """Config object to store API keys."""
    api_keys: List[APIKey] = field(default_factory=list)

def load_config() -> Config:
    """Loads API keys from .env file into a Config object."""
    load_dotenv()
    config = Config()
    i = 1
    while True:
        key = os.getenv(f'GROQ_API_KEY_{i}')
        if not key:
            break
        config.api_keys.append(APIKey(provider='groq', key=key, model='llama3-70b-8192'))
        i += 1
    i = 1
    while True:
        key = os.getenv(f'GEMINI_API_KEY_{i}')
        if not key:
            break
        config.api_keys.append(APIKey(provider='gemini', key=key, model='gemini-1.5-flash'))
        i += 1
    if not config.api_keys:
        print('Warning: No API keys found in .env file. Please create a .env file with GROQ_API_KEY_1 or GEMINI_API_KEY_1.')
    return config