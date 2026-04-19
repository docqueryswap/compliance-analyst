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
            timeout=60.0,  # Increased timeout for longer generations
            transport=httpx.HTTPTransport(retries=0)
        )
        self.nvidia_client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_api_key,
            http_client=http_client,
            max_retries=0
        )
        self.nvidia_model = "mistralai/mistral-7b-instruct-v0.3"

    def _generate_with_nvidia(self, messages: list, json_mode: bool, max_tokens: int) -> str:
        """Generate with NVIDIA NIM, with fallback for JSON mode."""
        kwargs = {
            "model": self.nvidia_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }

        # Some NVIDIA models don't support response_format; we'll try without first if it fails
        try:
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = self.nvidia_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e)
            # If JSON mode caused an error, retry without it
            if json_mode and ("response_format" in error_str or "json" in error_str.lower()):
                logger.warning("NVIDIA JSON mode failed, retrying without response_format")
                kwargs.pop("response_format", None)
                response = self.nvidia_client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content.strip()
                # If JSON was requested but we got plain text, attempt to extract JSON
                return self._extract_json_from_text(content)
            raise e

    def _extract_json_from_text(self, text: str) -> str:
        """Try to extract a JSON object from plain text."""
        # Look for a JSON block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                json.loads(match.group())  # Validate
                return match.group()
            except:
                pass
        # If no valid JSON, wrap in a simple JSON structure as fallback
        logger.warning("Could not extract valid JSON, returning wrapped response")
        return json.dumps({"raw_response": text})

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
            # Return a JSON error object if JSON mode was requested, otherwise plain error
            if json_mode:
                return json.dumps({"error": f"NVIDIA API error: {error_str}"})
            return f"⚠️ NVIDIA API error: {error_str}"