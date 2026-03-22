"""
decision_engine.py - Decision Model (Brain) with failsafes.

Analyses user input and outputs a structured Instruction Object.
Uses OpenRouter (Qwen 2.5 7B) as a lightweight classifier.

Failsafes:
    * Retry up to 2 times on API failure
    * Rate-limit detection → switch to LISTEN mode
    * Local fallback if LLM unavailable
    * Token-optimised prompts
"""

import json
import time

import requests

from src.config import OPENROUTER_API_KEY
from src.logger import get_logger

log = get_logger("decision")

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2.5-7b-instruct"

ADVICE_QUOTA = 5
LOW_CONFIDENCE_THRESHOLD = 0.4

MAX_RETRIES = 2
RETRY_DELAY = 1.0

MAX_CONTEXT = 2
_context_buffer: list[dict] = []

# Rate-limit tracking
_rate_limited_until: float = 0.0

# ---------------------------------------------------------------------------
# System prompt (token-optimised)
# ---------------------------------------------------------------------------
_BASE_DECISION_PROMPT = """\
Decision classifier. Return STRICT JSON only.

PERSONALITY: {personality_info}
MOOD: {mood_info}
ENGAGEMENT: {engagement_info}
TIME: {time_info}

RULES:
- Casual/not question → LISTEN
- Question → SHORT_REPLY
- Step-by-step help → ADVICE
- Tech troubleshoot → REDIRECT, external_redirect=true
- Noise → IGNORE
- advice_count >= quota → no ADVICE

JSON:
{{
  "mode": "LISTEN|SHORT_REPLY|ADVICE|REDIRECT|IGNORE",
  "emotion": "happy|neutral|frustrated|sad",
  "intent": "rant|question|thinking_aloud|greeting|technical_issue|emotional_support",
  "response_needed": true/false,
  "response_type": "text",
  "max_length": "short|medium|long",
  "tone": "calm|friendly|empathetic|professional",
  "interrupt_action": "stop|continue|switch",
  "memory_write": true/false,
  "memory_field": "preferences|behavior|activity|mood|null",
  "micro_reaction": "hmm|oh|laugh|aww|none",
  "external_redirect": true/false
}}"""

# ---------------------------------------------------------------------------
# Default instruction
# ---------------------------------------------------------------------------
_DEFAULT_INSTRUCTION: dict = {
    "mode": "LISTEN",
    "emotion": "neutral",
    "intent": "thinking_aloud",
    "response_needed": False,
    "response_type": "text",
    "max_length": "short",
    "tone": "calm",
    "interrupt_action": "continue",
    "memory_write": False,
    "memory_field": None,
    "micro_reaction": "hmm",
    "external_redirect": False,
}

# Local fallback responses (no LLM needed)
_LOCAL_FALLBACKS: list[str] = [
    "hmm…", "okay…", "got it…", "I see…", "right…",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decide(
    user_text: str,
    confidence: float,
    state: dict,
    personality_prompt: str = "",
    mood_summary: str = "",
    engagement_context: str = "",
    time_context: str = "",
) -> dict:
    """Analyse user input and return a structured instruction object."""

    # -- Pre-check: Low confidence ---------------------------------------
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        log.info("🧠  LOW_CONFIDENCE → asking user to repeat")
        return {
            **_DEFAULT_INSTRUCTION,
            "mode": "SHORT_REPLY",
            "response_needed": True,
            "max_length": "short",
            "tone": "friendly",
            "micro_reaction": "hmm",
            "input": user_text,
            "_low_confidence": True,
        }

    # -- Pre-check: Rate limited -----------------------------------------
    if time.time() < _rate_limited_until:
        log.warning("🧠  Rate limited → LISTEN fallback")
        return {
            **_DEFAULT_INSTRUCTION,
            "mode": "LISTEN",
            "micro_reaction": "hmm",
            "input": user_text,
        }

    # -- Build context ---------------------------------------------------
    context_str = ""
    if _context_buffer:
        context_lines = [
            f"- {c['role']}: {c['text']}" for c in _context_buffer[-MAX_CONTEXT:]
        ]
        context_str = "\nContext:\n" + "\n".join(context_lines)

    system_prompt = _BASE_DECISION_PROMPT.format(
        personality_info=personality_prompt or "default",
        mood_info=mood_summary or "unknown",
        engagement_info=engagement_context or "moderate",
        time_info=time_context or "unknown",
    )

    user_message = (
        f'User: "{user_text}"\n'
        f"conf:{confidence:.2f} advice:{state.get('advice_count', 0)}/{ADVICE_QUOTA}"
        f"{context_str}"
    )

    # -- Call with retry -------------------------------------------------
    log.info("🧠  Thinking …")
    instruction = _call_with_retry(system_prompt, user_message)

    # -- Post-processing -------------------------------------------------
    advice_count = state.get("advice_count", 0)
    if instruction["mode"] == "ADVICE" and advice_count >= ADVICE_QUOTA:
        log.info(f"🧠  Advice quota ({advice_count}/{ADVICE_QUOTA}) → SHORT_REPLY")
        instruction["mode"] = "SHORT_REPLY"
        instruction["max_length"] = "short"

    if instruction["mode"] in ("LISTEN", "IGNORE"):
        instruction["response_needed"] = False
    else:
        instruction["response_needed"] = True

    instruction["input"] = user_text

    _context_buffer.append({"role": "user", "text": user_text})
    if len(_context_buffer) > MAX_CONTEXT * 2:
        _context_buffer.pop(0)

    log.info(f"🧠  Decision: mode={instruction['mode']}  "
             f"emotion={instruction['emotion']}  respond={instruction['response_needed']}")

    return instruction


def update_context(role: str, text: str) -> None:
    """Append an entry to the context buffer."""
    _context_buffer.append({"role": role, "text": text})
    if len(_context_buffer) > MAX_CONTEXT * 2:
        _context_buffer.pop(0)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _call_with_retry(system_prompt: str, user_message: str) -> dict:
    """Call OpenRouter with retry logic and rate-limit detection."""
    global _rate_limited_until

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 180,
        "temperature": 0.1,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                OPENROUTER_URL, headers=headers, json=payload, timeout=15,
            )

            # Rate limit detection
            if resp.status_code == 429:
                log.warning("[DECISION] Rate limited — backing off 60s")
                _rate_limited_until = time.time() + 60
                return dict(_DEFAULT_INSTRUCTION)

            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            return _parse_instruction(raw)

        except Exception as e:
            log.warning(f"[DECISION] Attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    log.error("[DECISION] All retries failed → local fallback")
    return dict(_DEFAULT_INSTRUCTION)


def _parse_instruction(raw: str) -> dict:
    """Parse LLM JSON output with validation."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning(f"[DECISION] JSON parse failed: {raw[:100]}")
        return dict(_DEFAULT_INSTRUCTION)

    result = dict(_DEFAULT_INSTRUCTION)
    for key in _DEFAULT_INSTRUCTION:
        if key in parsed:
            result[key] = parsed[key]

    if result["mode"] not in {"LISTEN", "SHORT_REPLY", "ADVICE", "REDIRECT", "IGNORE"}:
        result["mode"] = "LISTEN"
    if result["emotion"] not in {"happy", "neutral", "frustrated", "sad"}:
        result["emotion"] = "neutral"
    if result["max_length"] not in {"short", "medium", "long"}:
        result["max_length"] = "short"

    return result
