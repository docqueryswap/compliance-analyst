import os
import logging
import json
import re
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        if not nvidia_api_key:
            raise ValueError("NVIDIA_API_KEY environment variable not set")

        import httpx
        http_client = httpx.Client(
            timeout=60.0,
            transport=httpx.HTTPTransport(retries=0)
        )
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key,
            http_client=http_client,
            max_retries=0
        )
        self.model = "meta/llama-3.1-8b-instruct"

    def generate(
        self,
        prompt: str,
        system: str = None,
        json_mode: bool = False,
        max_tokens: int = 1024,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content.strip()
            # If JSON was expected but we got plain text, try to extract JSON
            if json_mode and not content.startswith("{"):
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    content = match.group()
            return content
        except Exception as e:
            logger.error(f"NVIDIA generation failed: {e}")
            if json_mode:
                return json.dumps({"error": str(e)})
            return f"⚠️ NVIDIA API error: {str(e)}"