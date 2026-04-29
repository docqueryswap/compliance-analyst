# core/llm_client.py

import os
import logging
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        nvidia_api_key = os.getenv("NVIDIA_API_KEY")

        if not nvidia_api_key:
            raise ValueError("NVIDIA_API_KEY environment variable not set")

        import httpx

        # Fast model HTTP client (adequate for planner/retrieval)
        self.fast_http_client = httpx.Client(
            timeout=45.0,               # Fast model needs less time
            transport=httpx.HTTPTransport(retries=0)
        )

        # Reasoning model HTTP client – longer timeout for 1.6T MoE model
        self.reasoning_http_client = httpx.Client(
            timeout=180.0,              # Increased for DeepSeek‑V4‑Pro
            transport=httpx.HTTPTransport(retries=0)
        )

        # Fast model for planner / basic operations
        self.fast_model = "meta/llama-3.1-8b-instruct"

        # DeepSeek 1.6T reasoning model – state‑of‑the‑art agentic reasoning
        self.reasoning_model = "deepseek-ai/deepseek-v4-pro"

    def generate(
        self,
        prompt: str,
        system: str = None,
        json_mode: bool = False,
        max_tokens: int = 2048,
        use_reasoning: bool = False
    ) -> str:

        model_to_use = self.reasoning_model if use_reasoning else self.fast_model
        http_client = self.reasoning_http_client if use_reasoning else self.fast_http_client

        # Create OpenAI client with the appropriate HTTP client
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY"),
            http_client=http_client,
            max_retries=0
        )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content.strip()

            if json_mode and not content.startswith("{"):
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    content = match.group()

            return content

        except Exception as e:
            err_str = str(e).lower()
            # If reasoning model timed out, silently fall back to fast model
            if use_reasoning and ("timeout" in err_str or "timed out" in err_str):
                logger.warning(
                    f"Reasoning model ({self.reasoning_model}) timed out. "
                    f"Falling back to fast model ({self.fast_model})."
                )
                # Retry with fast model
                kwargs["model"] = self.fast_model
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content.strip()
                    if json_mode and not content.startswith("{"):
                        match = re.search(r"\{.*\}", content, re.DOTALL)
                        if match:
                            content = match.group()
                    return content
                except Exception as fallback_error:
                    logger.error(f"Fast model fallback also failed: {fallback_error}")

            logger.error(f"NVIDIA generation failed: {e}")
            if json_mode:
                return json.dumps({"error": str(e)})
            return f"⚠️ NVIDIA API error: {str(e)}"