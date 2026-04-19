import os
import logging
import time
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        # --- NVIDIA setup (sole provider) ---
        nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        if not nvidia_api_key:
            raise ValueError("NVIDIA_API_KEY environment variable not set")
        
        import httpx
        http_client = httpx.Client(
            timeout=45.0,
            transport=httpx.HTTPTransport(retries=0)
        )
        self.nvidia_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key,
            http_client=http_client,
            max_retries=0
        )
        self.nvidia_model = "mistralai/mistral-7b-instruct-v0.3"   # ✅ Free NVIDIA endpoint

    def _generate_with_nvidia(self, messages: list, json_mode: bool, max_tokens: int) -> str:
        """Generate with NVIDIA NIM."""
        kwargs = {
            "model": self.nvidia_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.nvidia_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    def generate(
        self,
        prompt: str,
        system: str = None,
        json_mode: bool = False,
        max_tokens: int = 800,
    ) -> str:
        """
        Generate a response using NVIDIA NIM.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            return self._generate_with_nvidia(messages, json_mode, max_tokens)
        except Exception as e:
            error_str = str(e)
            logger.error(f"NVIDIA generation failed: {error_str}")
            return f"⚠️ NVIDIA API error: {error_str}"