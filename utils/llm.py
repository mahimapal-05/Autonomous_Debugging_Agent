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
    "groq_api_key": "",
    "gemini_api_key": "",
    "groq_model": "",
    "gemini_model": "",
    "llm_provider": ""
}

# Default Models
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

def set_groq_api_key(key: str):
    """Set Groq API key in memory and environment."""
    _IN_MEMORY_CONFIG["groq_api_key"] = key.strip()
    os.environ["GROQ_API_KEY"] = key.strip()

def set_gemini_api_key(key: str):
    """Set Gemini API key in memory and environment."""
    _IN_MEMORY_CONFIG["gemini_api_key"] = key.strip()
    os.environ["GEMINI_API_KEY"] = key.strip()

def set_llm_provider(provider: str):
    """Set preferred LLM provider."""
    _IN_MEMORY_CONFIG["llm_provider"] = provider.strip().lower()
    os.environ["LLM_PROVIDER"] = provider.strip().lower()

def get_groq_api_key() -> str:
    """Retrieve Groq API Key from memory or environment."""
    return _IN_MEMORY_CONFIG["groq_api_key"] or os.getenv("GROQ_API_KEY", "").strip()

def get_gemini_api_key() -> str:
    """Retrieve Gemini API Key from memory or environment."""
    return _IN_MEMORY_CONFIG["gemini_api_key"] or os.getenv("GEMINI_API_KEY", "").strip()

# Backwards compatible alias
get_api_key = get_gemini_api_key

def is_groq_available(api_key: Optional[str] = None) -> bool:
    """Check if a valid Groq API key is configured."""
    key = api_key if api_key is not None else get_groq_api_key()
    return bool(key and key != "your_groq_api_key_here" and key != "")

def is_gemini_available(api_key: Optional[str] = None) -> bool:
    """Check if a valid Gemini API key is configured."""
    key = api_key if api_key is not None else get_gemini_api_key()
    return bool(key and key != "your_gemini_api_key_here" and key != "")

def is_llm_available(provider: Optional[str] = None) -> bool:
    """Check if any LLM provider is available."""
    if provider == "groq":
        return is_groq_available()
    elif provider == "gemini":
        return is_gemini_available()
    return is_groq_available() or is_gemini_available()

def get_preferred_provider() -> str:
    """Determine the default active provider."""
    explicit_provider = _IN_MEMORY_CONFIG["llm_provider"] or os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit_provider in ["groq", "gemini"]:
        return explicit_provider
    if is_groq_available():
        return "groq"
    if is_gemini_available():
        return "gemini"
    return "mock"

def call_groq(prompt: str, system_instruction: str = "", model: Optional[str] = None, api_key: Optional[str] = None) -> Optional[str]:
    """
    Call the Groq API using the official groq SDK.
    """
    key = api_key if api_key is not None else get_groq_api_key()
    if not is_groq_available(key):
        logger.info("GROQ_API_KEY missing or invalid.")
        return None

    model_name = model or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
    try:
        from groq import Groq
        client = Groq(api_key=key)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            messages=messages,
            model=model_name,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"Groq API call failed: {e}")
        return None

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
        # Try google.genai
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
            model_inst = genai_legacy.GenerativeModel('gemini-1.5-flash')
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
    Unified LLM calling interface with automatic fallback between Groq, Gemini, and Mock mode.
    """
    selected_provider = provider or get_preferred_provider()

    # If user prefers Groq
    if selected_provider == "groq" or (selected_provider != "gemini" and is_groq_available(api_key)):
        res = call_groq(prompt, system_instruction, model=model, api_key=api_key)
        if res:
            return res
        # Fallback to Gemini if Groq fails
        if is_gemini_available():
            logger.info("Falling back from Groq to Gemini...")
            return call_gemini(prompt, system_instruction)

    # If user prefers Gemini
    elif selected_provider == "gemini" or is_gemini_available(api_key):
        res = call_gemini(prompt, system_instruction, model=model, api_key=api_key)
        if res:
            return res
        # Fallback to Groq if Gemini fails
        if is_groq_available():
            logger.info("Falling back from Gemini to Groq...")
            return call_groq(prompt, system_instruction)

    logger.info("All LLM providers unavailable or failed. Operating in Mock Fallback Mode.")
    return None
