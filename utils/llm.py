"""Small Gemini helper shared by the research pipeline and MVP.

The original ``generate_json`` function returned JSON arrays and is used by
the completed review-analysis pipeline. Its public signature and array
parsing contract are intentionally preserved. The MVP uses the separate
``generate_json_object`` function for its single recommendation object.
"""

import json
import os
import re
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used in minimal test runtimes
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


load_dotenv()

# Kept as a module-level name for compatibility with code that may inspect it.
# Client construction is deliberately lazy so importing this module is safe
# when the app is running without a configured secret.
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-3.1-flash-lite"
client = None


class LLMConfigurationError(RuntimeError):
    """Raised when Gemini cannot be used because configuration is missing."""


def get_api_key() -> str | None:
    """Read the Gemini key from environment variables or Streamlit secrets."""

    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key

    # Streamlit secrets are optional and imported only when requested.
    try:
        import streamlit as st

        secret_key = st.secrets.get("GEMINI_API_KEY")
        return str(secret_key) if secret_key else None
    except Exception:
        return None


def _get_client():
    global client

    api_key = get_api_key()
    if not api_key:
        raise LLMConfigurationError(
            "GEMINI_API_KEY is not configured. Add it to the environment "
            "or Streamlit secrets to enable Gemini recommendations."
        )

    if client is None:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise LLMConfigurationError(
                "The google-genai package is not installed."
            ) from exc
        client = genai.Client(api_key=api_key)

    return client


def _generate_content(system_prompt: str, user_prompt: str):
    """Call Gemini once. Kept separate to make parsing independently testable."""

    active_client = _get_client()
    return active_client.models.generate_content(
        model=MODEL,
        contents=f"{system_prompt}\n\n{user_prompt}",
    )


def _clean_response_text(response) -> str:
    text = (getattr(response, "text", "") or "").strip()
    return text.replace("```json", "").replace("```", "").strip()


def generate_json(system_prompt: str, user_prompt: str):
    """Return the JSON array expected by the existing research pipeline.

    This intentionally retains the original array-only parsing behavior.
    """

    response = _generate_content(system_prompt, user_prompt)
    text = _clean_response_text(response)

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in Gemini response")
    return json.loads(match.group())


def generate_json_object(system_prompt: str, user_prompt: str) -> dict:
    """Return one strict JSON object for the MVP recommendation flow."""

    response = _generate_content(system_prompt, user_prompt)
    text = _clean_response_text(response)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini response was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Gemini response must be a JSON object")

    return parsed
