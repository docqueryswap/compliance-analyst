import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"
    
    def generate(self, prompt: str, system: str = None, json_mode: bool = False) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1000,
            "timeout": 30.0
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            return f"Error: {str(e)}"