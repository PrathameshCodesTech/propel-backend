"""
Gemini AI client wrapper for natural language to query plan conversion.
"""
import os
from typing import Optional, Tuple

# Load .env from backend directory (where manage.py lives)
try:
    from dotenv import load_dotenv
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_backend_dir, ".env"))
except ImportError:
    pass

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Last error message (so API can return why Gemini failed)
_last_gemini_error: Optional[str] = None


def get_last_gemini_error() -> Optional[str]:
    """Return the last Gemini error message (for API to show user)."""
    return _last_gemini_error


def get_gemini_client():
    """Initialize and return Gemini client."""
    global _last_gemini_error
    if genai is None:
        _last_gemini_error = "google-generativeai is not installed. Run: pip install google-generativeai"
        raise ImportError(_last_gemini_error)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        _last_gemini_error = "GEMINI_API_KEY not set. Add it to .env in the backend folder (propel-insights-backend/.env)."
        raise ValueError(_last_gemini_error)

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    return genai.GenerativeModel(model_name)


def ask_gemini(prompt: str, system_prompt: str) -> Optional[str]:
    """
    Send prompt to Gemini and return response text.

    Returns:
        Response text from Gemini, or None on error. Use get_last_gemini_error() for why it failed.
    """
    global _last_gemini_error
    _last_gemini_error = None
    try:
        model = get_gemini_client()
        full_prompt = f"{system_prompt}\n\nUser question: {prompt}\n\nResponse (JSON only):"
        response = model.generate_content(full_prompt)

        if not response:
            _last_gemini_error = "Gemini returned no response object."
            print(_last_gemini_error)
            return None

        # Blocked or empty: response.text can throw or be empty
        if not response.candidates:
            fb = getattr(response, "prompt_feedback", None)
            if fb and getattr(fb, "block_reason", None):
                _last_gemini_error = f"Gemini blocked the prompt: {getattr(fb, 'block_reason', 'unknown')}"
            else:
                _last_gemini_error = "Gemini returned no candidates (empty or blocked)."
            print(_last_gemini_error)
            return None

        c0 = response.candidates[0]
        finish = getattr(c0, "finish_reason", None)
        if finish and str(finish) not in ("FINISH_REASON_UNSPECIFIED", "STOP", "1"):
            _last_gemini_error = f"Gemini stopped: {finish}"
            print(_last_gemini_error)
        try:
            text = response.text
        except Exception as e:
            _last_gemini_error = f"Gemini response not readable: {e}"
            print(_last_gemini_error)
            return None

        if not (text and text.strip()):
            _last_gemini_error = "Gemini returned empty text."
            print(_last_gemini_error)
            return None

        print(f"Gemini response: {text[:200]}...")
        return text

    except ImportError as e:
        _last_gemini_error = str(e) or "google-generativeai not installed. Run: pip install google-generativeai"
        print(f"Gemini import error: {_last_gemini_error}")
        return None
    except ValueError as e:
        _last_gemini_error = str(e)
        print(f"Gemini config error: {_last_gemini_error}")
        return None
    except Exception as e:
        _last_gemini_error = f"{type(e).__name__}: {e}"
        print(f"Gemini API error: {_last_gemini_error}")
        return None
