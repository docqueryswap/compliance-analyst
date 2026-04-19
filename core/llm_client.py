import os
import logging
import time
from groq import Groq
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        # --- Groq setup (primary) ---
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        # 🔥 创建禁用重试、超时 45 秒的 HTTP 客户端
        import httpx
        http_client = httpx.Client(
            timeout=45.0,
            transport=httpx.HTTPTransport(retries=0)
        )
        self.groq_client = Groq(
            api_key=groq_api_key,
            http_client=http_client,
            max_retries=0
        )
        self.groq_model = "llama-3.1-8b-instant"

        # --- Gemini setup (fallback) ---
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            logger.warning("GEMINI_API_KEY not set. Gemini fallback will be unavailable.")
            self.gemini_model = None

    def _generate_with_groq(self, messages: list, json_mode: bool, max_tokens: int) -> str:
        """Attempt generation with Groq."""
        kwargs = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    def _generate_with_gemini(self, prompt: str, system: str, json_mode: bool, max_tokens: int) -> str:
        """Fallback generation with Gemini."""
        if self.gemini_model is None:
            raise RuntimeError("Gemini fallback requested but not configured (missing GEMINI_API_KEY)")

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        # 🔥 为 Gemini 添加 45 秒超时（毫秒）
        response = self.gemini_model.generate_content(
            full_prompt,
            generation_config=generation_config,
            request_options={"timeout": 45000}
        )
        return response.text.strip()

    def generate(
        self,
        prompt: str,
        system: str = None,
        json_mode: bool = False,
        max_tokens: int = 800,   # 🔥 默认值从 1024 降为 800，缩短生成时间
    ) -> str:
        """
        Generate a response using Groq (primary). If a rate limit error occurs,
        automatically fall back to Gemini.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Try Groq first
        try:
            return self._generate_with_groq(messages, json_mode, max_tokens)
        except Exception as e:
            error_str = str(e)
            if "rate_limit" in error_str.lower():
                logger.warning(
                    f"Groq rate limit reached. Falling back to Gemini. "
                    f"(Original error: {error_str[:100]}...)"
                )
                if self.gemini_model is None:
                    logger.error("Gemini fallback unavailable – no API key configured.")
                    return f"⚠️ Rate limit reached and no fallback available. Original error: {error_str}"
                try:
                    return self._generate_with_gemini(prompt, system, json_mode, max_tokens)
                except Exception as gemini_error:
                    logger.error(f"Gemini fallback also failed: {gemini_error}")
                    return f"⚠️ Both Groq and Gemini failed. Error: {gemini_error}"
            else:
                # Non‑rate‑limit error – log and re‑raise
                logger.error(f"Groq generation failed with non‑rate‑limit error: {e}")
                return f"⚠️ Groq API error: {error_str}"