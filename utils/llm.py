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
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

def normalize_gemini_model(model_name: Optional[str]) -> str:
    """Normalize user or environment model name to official Google Gemini model IDs."""
    if not model_name:
        return DEFAULT_GEMINI_MODEL
    
    clean = model_name.strip().lower()
    if "2.5" in clean:
        return "gemini-2.0-flash"
    if "flash" in clean:
        if "1.5" in clean:
            return "gemini-1.5-flash"
        return "gemini-2.0-flash"
    if "pro" in clean:
        if "1.5" in clean:
            return "gemini-1.5-pro"
        return "gemini-2.0-pro-exp-02-05"
    return clean

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
    return bool(key and key != "your_gemini_api_key_here" and len(key) > 10)

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

def _call_gemini_rest(prompt: str, api_key: str, model_name: str) -> Optional[str]:
    """Fallback REST caller for Gemini API using standard urllib."""
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as e:
        logger.warning(f"Gemini REST call failed for {model_name}: {e}")
    return None

def call_gemini(prompt: str, system_instruction: str = "", model: Optional[str] = None, api_key: Optional[str] = None) -> Optional[str]:
    """
    Call the Gemini API using Google GenAI SDK with automatic fallbacks and REST retry.
    """
    key = api_key if api_key is not None else get_gemini_api_key()
    if not is_gemini_available(key):
        return None

    raw_model = model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    model_name = normalize_gemini_model(raw_model)
    full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt

    # 1. Try google.genai (modern SDK)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt
        )
        if response and response.text:
            return response.text
    except Exception as e:
        logger.debug(f"google.genai SDK attempt failed: {e}")

    # 2. Try google.generativeai (legacy SDK)
    try:
        import google.generativeai as genai_legacy
        genai_legacy.configure(api_key=key)
        model_inst = genai_legacy.GenerativeModel(model_name)
        response = model_inst.generate_content(full_prompt)
        if response and response.text:
            return response.text
    except Exception as e:
        logger.debug(f"google.generativeai SDK attempt failed: {e}")

    # 3. Direct REST HTTP API Fallback
    rest_res = _call_gemini_rest(full_prompt, key, model_name)
    if rest_res:
        return rest_res

    # 4. If primary model failed, try gemini-1.5-flash fallback
    if model_name != "gemini-1.5-flash":
        rest_res_fallback = _call_gemini_rest(full_prompt, key, "gemini-1.5-flash")
        if rest_res_fallback:
            return rest_res_fallback

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

    logger.info("Operating in Intelligent Multi-Pass Rule-Based / AST Mode.")
    return None

