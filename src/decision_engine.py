"""
decision_engine.py - Decision Model (Brain).

Analyses user input and outputs a structured Instruction Object that
controls every downstream module.  Uses OpenRouter (Qwen 2.5 7B) as
a lightweight classifier – NOT for generating final responses.

Key features:
    * Mode classification  (LISTEN / SHORT_REPLY / ADVICE / REDIRECT / IGNORE)
    * Emotion + intent detection
    * Cost-control gating  (advice quota, casual-talk bypass)
    * Response length + tone control
    * Memory-write flags
    * Micro-reaction selection
    * Interruption awareness
"""

import json

import requests

from src.config import OPENROUTER_API_KEY

# ---------------------------------------------------------------------------
# OpenRouter settings (decision model)
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2.5-7b-instruct"

# ---------------------------------------------------------------------------
# Cost-control constants
# ---------------------------------------------------------------------------
ADVICE_QUOTA = 5                 # max ADVICE responses per session
LOW_CONFIDENCE_THRESHOLD = 0.4   # below this → skip LLM, ask to repeat

# ---------------------------------------------------------------------------
# Minimal context buffer (last N exchanges)
# ---------------------------------------------------------------------------
MAX_CONTEXT = 2
_context_buffer: list[dict] = []

# ---------------------------------------------------------------------------
# System prompt – kept ultra-tight to minimize tokens
# ---------------------------------------------------------------------------
DECISION_PROMPT = """\
You are a decision-only classifier. Analyse the user message and return STRICT JSON.

RULES:
- Casual talk / not a question → mode=LISTEN
- Clear question → mode=SHORT_REPLY (prefer short)
- Step-by-step help needed → mode=ADVICE
- Technical troubleshooting → mode=REDIRECT, external_redirect=true
- Nonsense / noise → mode=IGNORE
- If advice_count >= quota → never use ADVICE, use SHORT_REPLY or LISTEN

Return ONLY this JSON (no markdown, no explanation):
{
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
}"""

# ---------------------------------------------------------------------------
# Default instruction (used as fallback / merge base)
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def decide(user_text: str, confidence: float, state: dict) -> dict:
    """
    Analyse user input and return a structured instruction object.

    Args:
        user_text:   Transcribed text from STT.
        confidence:  STT confidence score (0.0–1.0).
        state:       System state dict with keys:
                     - ``advice_count`` (int)
                     - ``current_mode`` (str | None)

    Returns:
        Instruction dict matching the schema above.
        Always includes key ``"input"`` with the original user text.
    """
    # ------------------------------------------------------------------
    # Pre-check 1: Low STT confidence → ask to repeat (no LLM cost)
    # ------------------------------------------------------------------
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        print("🧠  Decision: LOW_CONFIDENCE → asking user to repeat")
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

    # ------------------------------------------------------------------
    # Pre-check 2: Build context string
    # ------------------------------------------------------------------
    context_str = ""
    if _context_buffer:
        context_lines = [
            f"- {c['role']}: {c['text']}" for c in _context_buffer[-MAX_CONTEXT:]
        ]
        context_str = "\nRecent context:\n" + "\n".join(context_lines)

    # ------------------------------------------------------------------
    # Build the user message for the classifier
    # ------------------------------------------------------------------
    user_message = (
        f"User said: \"{user_text}\"\n"
        f"STT confidence: {confidence:.2f}\n"
        f"advice_count: {state.get('advice_count', 0)}/{ADVICE_QUOTA}\n"
        f"current_mode: {state.get('current_mode', 'none')}"
        f"{context_str}"
    )

    # ------------------------------------------------------------------
    # Call the decision model
    # ------------------------------------------------------------------
    print("🧠  Thinking …")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": DECISION_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 200,
        "temperature": 0.1,  # low temp for deterministic classification
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

        raw = response.json()["choices"][0]["message"]["content"].strip()
        instruction = _parse_instruction(raw)

    except Exception as e:
        print(f"[ERROR] Decision engine failed: {e}")
        instruction = dict(_DEFAULT_INSTRUCTION)

    # ------------------------------------------------------------------
    # Post-processing: enforce cost-control rules
    # ------------------------------------------------------------------
    advice_count = state.get("advice_count", 0)

    # Enforce advice quota
    if instruction["mode"] == "ADVICE" and advice_count >= ADVICE_QUOTA:
        print(f"🧠  Advice quota reached ({advice_count}/{ADVICE_QUOTA}) → SHORT_REPLY")
        instruction["mode"] = "SHORT_REPLY"
        instruction["max_length"] = "short"

    # Set response_needed based on mode
    if instruction["mode"] in ("LISTEN", "IGNORE"):
        instruction["response_needed"] = False
    else:
        instruction["response_needed"] = True

    # Attach original text
    instruction["input"] = user_text

    # Update context buffer
    _context_buffer.append({"role": "user", "text": user_text})
    if len(_context_buffer) > MAX_CONTEXT * 2:
        _context_buffer.pop(0)

    print(f"🧠  Decision: mode={instruction['mode']}  "
          f"emotion={instruction['emotion']}  "
          f"intent={instruction['intent']}  "
          f"respond={instruction['response_needed']}")

    return instruction


def update_context(role: str, text: str) -> None:
    """Append an entry to the context buffer (called from main.py)."""
    _context_buffer.append({"role": role, "text": text})
    if len(_context_buffer) > MAX_CONTEXT * 2:
        _context_buffer.pop(0)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_instruction(raw: str) -> dict:
    """
    Parse the LLM's raw text output into a validated instruction dict.

    Tries to extract JSON even if the model wraps it in markdown fences.
    Falls back to defaults for any missing or invalid fields.
    """
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[WARN] Could not parse decision JSON, using defaults. Raw: {raw[:120]}")
        return dict(_DEFAULT_INSTRUCTION)

    # Merge with defaults so every key is guaranteed
    result = dict(_DEFAULT_INSTRUCTION)
    for key in _DEFAULT_INSTRUCTION:
        if key in parsed:
            result[key] = parsed[key]

    # Validate enum values
    valid_modes = {"LISTEN", "SHORT_REPLY", "ADVICE", "REDIRECT", "IGNORE"}
    if result["mode"] not in valid_modes:
        result["mode"] = "LISTEN"

    valid_emotions = {"happy", "neutral", "frustrated", "sad"}
    if result["emotion"] not in valid_emotions:
        result["emotion"] = "neutral"

    valid_lengths = {"short", "medium", "long"}
    if result["max_length"] not in valid_lengths:
        result["max_length"] = "short"

    return result
