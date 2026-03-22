"""
response_engine.py - Response Model (Writer).

Sends the instruction payload to OpenRouter and returns the model's
text response.  Now personality-aware: the personality prompt is
prepended to the system prompt for consistent tone/style.
"""

import requests

from src.config import OPENROUTER_API_KEY
from src.personality import get_personality_prompt

# ---------------------------------------------------------------------------
# OpenRouter settings
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2.5-7b-instruct"

# ---------------------------------------------------------------------------
# Token limits mapped from instruction max_length
# ---------------------------------------------------------------------------
LENGTH_TO_TOKENS: dict[str, int] = {
    "short": 80,
    "medium": 200,
    "long": 400,
}

# ---------------------------------------------------------------------------
# Tone-aware system prompts
# ---------------------------------------------------------------------------
TONE_PROMPTS: dict[str, str] = {
    "calm": "Answer concisely and calmly.",
    "friendly": "Keep answers brief and approachable.",
    "empathetic": "Acknowledge feelings and respond gently.",
    "professional": "Be precise and to the point.",
}

DEFAULT_TONE = "Answer concisely and clearly."

LOW_CONFIDENCE_RESPONSE = "Sorry, I didn't catch that… can you repeat?"


def generate_response(instruction: dict) -> str:
    """
    Generate a text response for the given instruction.

    The personality prompt is automatically prepended to the system prompt.
    """
    # -- Gate: no response needed ----------------------------------------
    if not instruction.get("response_needed", False):
        return ""

    # -- Low confidence shortcut -----------------------------------------
    if instruction.get("_low_confidence", False):
        print(f'💬  Response (canned): "{LOW_CONFIDENCE_RESPONSE}"')
        return LOW_CONFIDENCE_RESPONSE

    # -- Redirect shortcut -----------------------------------------------
    if instruction.get("external_redirect", False):
        redirect_msg = (
            "That sounds like something that might need more specialised help. "
            "I'd suggest checking online resources or asking an expert for that one."
        )
        print(f'💬  Response (redirect): "{redirect_msg}"')
        return redirect_msg

    # -- Normal LLM response ---------------------------------------------
    user_input: str = instruction.get("input", "")
    if not user_input:
        return "I didn't catch that. Could you say it again?"

    max_length = instruction.get("max_length", "short")
    tone = instruction.get("tone", "calm")
    max_tokens = LENGTH_TO_TOKENS.get(max_length, 80)
    tone_instr = TONE_PROMPTS.get(tone, DEFAULT_TONE)

    # Build system prompt: personality + tone
    personality = get_personality_prompt()
    system_prompt = f"{personality} {tone_instr}"

    print(f"💬  Generating response (length={max_length}, tone={tone}) …")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            OPENROUTER_URL, headers=headers, json=payload, timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        reply = data["choices"][0]["message"]["content"].strip()

        print(f'💬  Response: "{reply}"')
        return reply

    except requests.RequestException as e:
        print(f"[ERROR] OpenRouter request failed: {e}")
        return "Sorry, I couldn't generate a response right now."
    except (KeyError, IndexError) as e:
        print(f"[ERROR] Unexpected API response format: {e}")
        return "Sorry, something went wrong while parsing the response."
