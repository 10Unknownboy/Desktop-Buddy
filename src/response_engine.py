"""
response_engine.py - Response Model (Writer).

Sends the instruction payload to OpenRouter and returns the model's
text response.  Uses the Qwen 2.5 7B Instruct model.
"""

import requests

from src.config import OPENROUTER_API_KEY

# ---------------------------------------------------------------------------
# OpenRouter settings
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2.5-7b-instruct"

# Default system prompt (intentionally minimal – personality comes later)
SYSTEM_PROMPT = (
    "You are a helpful desktop assistant. "
    "Answer concisely and clearly."
)


def generate_response(instruction: dict) -> str:
    """
    Generate a text response for the given instruction.

    Args:
        instruction: Dict from the decision engine.
                     Expected key: ``instruction["input"]`` (str).

    Returns:
        The assistant's text reply, or a fallback error string.
    """
    user_input: str = instruction.get("input", "")

    if not user_input:
        return "I didn't catch that. Could you say it again?"

    print("💬  Generating response …")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": 256,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()

        print(f"💬  Response: \"{reply}\"")
        return reply

    except requests.RequestException as e:
        print(f"[ERROR] OpenRouter request failed: {e}")
        return "Sorry, I couldn't generate a response right now."
    except (KeyError, IndexError) as e:
        print(f"[ERROR] Unexpected API response format: {e}")
        return "Sorry, something went wrong while parsing the response."
