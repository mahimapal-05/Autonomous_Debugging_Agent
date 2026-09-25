import os
import json
import logging
from typing import Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("LLM_Utility")

# Global in-memory overrides for live UI session persistence
_IN_MEMORY_CONFIG = {
    "gemini_api_key": "",
    "gemini_model": "",
    "llm_provider": "gemini"
}

# Default Model
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

def set_gemini_api_key(key: str):
    """Set Gemini API key in memory and environment."""
    _IN_MEMORY_CONFIG["gemini_api_key"] = key.strip()
    os.environ["GEMINI_API_KEY"] = key.strip()

def set_llm_provider(provider: str):
    """Set preferred LLM provider (gemini or mock)."""
    _IN_MEMORY_CONFIG["llm_provider"] = provider.strip().lower()
    os.environ["LLM_PROVIDER"] = provider.strip().lower()

def get_gemini_api_key() -> str:
    """Retrieve Gemini API Key from memory or environment."""
    return _IN_MEMORY_CONFIG["gemini_api_key"] or os.getenv("GEMINI_API_KEY", "").strip()

# Backwards compatible alias
get_api_key = get_gemini_api_key

def is_gemini_available(api_key: Optional[str] = None) -> bool:
    """Check if a valid Gemini API key is configured."""
    key = api_key if api_key is not None else get_gemini_api_key()
    return bool(key and key != "your_gemini_api_key_here" and key != "")

def is_llm_available(provider: Optional[str] = None) -> bool:
    """Check if Gemini LLM provider is available."""
    return is_gemini_available()

def get_preferred_provider() -> str:
    """Determine active provider."""
    explicit_provider = _IN_MEMORY_CONFIG["llm_provider"] or os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit_provider == "mock":
        return "mock"
    if is_gemini_available():
        return "gemini"
    return "mock"

def call_gemini(prompt: str, system_instruction: str = "", model: Optional[str] = None, api_key: Optional[str] = None) -> Optional[str]:
    """
    Call the Gemini API using Google Generative AI / GenAI SDK.
    """
    key = api_key if api_key is not None else get_gemini_api_key()
    if not is_gemini_available(key):
        logger.info("GEMINI_API_KEY missing or invalid.")
        return None

    model_name = model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    try:
        # Try new google.genai client
        try:
            from google import genai
            client = genai.Client(api_key=key)
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )
            return response.text
        except ImportError:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=key)
            model_inst = genai_legacy.GenerativeModel(model_name)
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            response = model_inst.generate_content(full_prompt)
            return response.text
    except Exception as e:
        logger.warning(f"Gemini API call failed: {e}")
        return None

def call_llm(
    prompt: str,
    system_instruction: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Primary LLM calling interface using Google Gemini with Mock fallback.
    """
    selected_provider = provider or get_preferred_provider()

    if selected_provider != "mock" and is_gemini_available(api_key):
        res = call_gemini(prompt, system_instruction, model=model, api_key=api_key)
        if res:
            return res

    logger.info("Gemini unavailable or mock mode selected. Operating in Intelligent Rule-Based Fallback Mode.")
    return None

