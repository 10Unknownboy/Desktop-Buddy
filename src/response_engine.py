"""
response_engine.py - Response Model (Writer) with failsafes.

Sends the instruction payload to OpenRouter and returns the
model's text response.  Personality-aware with retry logic and
local fallback responses.

Failsafes:
    * Retry up to 2 times on API failure
    * Rate-limit detection → local fallback
    * Pre-defined fallback responses (no LLM)
"""

import time

import requests

from src.config import OPENROUTER_API_KEY
from src.personality import get_personality_prompt
from src.logger import get_logger

log = get_logger("response")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2.5-7b-instruct"

MAX_RETRIES = 2
RETRY_DELAY = 1.0

# Rate-limit tracking
_rate_limited_until: float = 0.0

# ---------------------------------------------------------------------------
# Token limits
# ---------------------------------------------------------------------------
LENGTH_TO_TOKENS: dict[str, int] = {
    "short": 80,
    "medium": 200,
    "long": 400,
}

TONE_PROMPTS: dict[str, str] = {
    "calm": "Answer concisely and calmly.",
    "friendly": "Keep answers brief and approachable.",
    "empathetic": "Acknowledge feelings and respond gently.",
    "professional": "Be precise and to the point.",
}

DEFAULT_TONE = "Answer concisely and clearly."

# ---------------------------------------------------------------------------
# Fallback responses (used when LLM is unavailable)
# ---------------------------------------------------------------------------
LOW_CONFIDENCE_RESPONSE = "Sorry, I didn't catch that… can you repeat?"

_FALLBACK_RESPONSES = [
    "Hmm, I'm having a bit of trouble right now. Can you try again?",
    "Something went wrong on my end… try again?",
    "I couldn't process that, sorry. Give me another shot?",
]


def generate_response(instruction: dict) -> str:
    """Generate a text response with retry + fallback."""

    if not instruction.get("response_needed", False):
        return ""

    # Low confidence shortcut
    if instruction.get("_low_confidence", False):
        log.info(f'💬  Response (canned): "{LOW_CONFIDENCE_RESPONSE}"')
        return LOW_CONFIDENCE_RESPONSE

    # Redirect shortcut
    if instruction.get("external_redirect", False):
        msg = (
            "That sounds like something that might need more specialised help. "
            "I'd suggest checking online resources or asking an expert for that one."
        )
        log.info(f'💬  Response (redirect): "{msg}"')
        return msg

    # Rate limited → fallback
    if time.time() < _rate_limited_until:
        log.warning("💬  Rate limited → local fallback")
        import random
        return random.choice(_FALLBACK_RESPONSES)

    # Normal LLM response
    user_input = instruction.get("input", "")
    if not user_input:
        return "I didn't catch that. Could you say it again?"

    max_length = instruction.get("max_length", "short")
    tone = instruction.get("tone", "calm")
    max_tokens = LENGTH_TO_TOKENS.get(max_length, 80)
    tone_instr = TONE_PROMPTS.get(tone, DEFAULT_TONE)

    personality = get_personality_prompt()
    system_prompt = f"{personality} {tone_instr}"

    log.info(f"💬  Generating response (length={max_length}, tone={tone}) …")

    response = _call_with_retry(system_prompt, user_input, max_tokens)
    if response:
        log.info(f'💬  Response: "{response}"')
    return response


def _call_with_retry(system_prompt: str, user_input: str, max_tokens: int) -> str:
    """Call OpenRouter with retry and rate-limit detection."""
    global _rate_limited_until

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

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                OPENROUTER_URL, headers=headers, json=payload, timeout=30,
            )

            if resp.status_code == 429:
                log.warning("[RESPONSE] Rate limited — backing off 60s")
                _rate_limited_until = time.time() + 60
                import random
                return random.choice(_FALLBACK_RESPONSES)

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            log.warning(f"[RESPONSE] Attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    log.error("[RESPONSE] All retries failed → fallback")
    import random
    return random.choice(_FALLBACK_RESPONSES)
