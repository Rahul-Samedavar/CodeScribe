import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing import List

@dataclass
class APIKey:
    provider: str
    key: str
    model: str

    def __repr__(self):
        return f"APIKey(provider='{self.provider}', model='{self.model}')"

@dataclass
class Config:
    api_keys: List[APIKey] = field(default_factory=list)

def load_config() -> Config:
    """Loads API keys from .env file into a Config object."""
    load_dotenv()
    
    config = Config()
    
    # Load Groq keys (GROQ_API_KEY_1, GRO-API_KEY_2, etc.)
    i = 1
    while True:
        key = os.getenv(f"GROQ_API_KEY_{i}")
        if not key:
            break
        config.api_keys.append(APIKey(provider="groq", key=key, model="llama3-70b-8192"))
        i += 1

    # Load Gemini keys (GEMINI_API_KEY_1, etc.)
    i = 1
    while True:
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if not key:
            break
        config.api_keys.append(APIKey(provider="gemini", key=key, model="gemini-1.5-flash"))
        i += 1
        
    if not config.api_keys:
        print("Warning: No API keys found in .env file. Please create a .env file with GROQ_API_KEY_1 or GEMINI_API_KEY_1.")
        
    return config