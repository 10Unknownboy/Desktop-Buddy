"""
personality.py - Configurable personality system.

Loads personality traits from data/personality.json and provides
helpers that inject personality into prompts and control behaviour.

At startup, assigns a random energy score (1–10) that influences
how expressive and reactive the assistant is during the session.
"""

import json
import random
from pathlib import Path

from src.config import DATA_DIR

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PERSONALITY_FILE: Path = DATA_DIR / "personality.json"

# ---------------------------------------------------------------------------
# Defaults (used if file is missing or incomplete)
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "name": "Buddy",
    "tone": "friendly",
    "style": "short",
    "energy_level": "dynamic",
    "reaction_style": "expressive",
}

# ---------------------------------------------------------------------------
# Module state (set once at load time)
# ---------------------------------------------------------------------------
_personality: dict = {}
_energy_score: int = 5   # 1–10, randomised each startup


def load_personality() -> dict:
    """
    Load personality from JSON and assign a random energy score.

    Call once at application startup.  Returns the personality dict
    enriched with ``energy_score``.
    """
    global _personality, _energy_score

    try:
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            _personality = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("[WARN] personality.json not found or invalid, using defaults.")
        _personality = dict(_DEFAULTS)

    # Merge defaults for any missing keys
    for k, v in _DEFAULTS.items():
        _personality.setdefault(k, v)

    # Assign random energy score for this session
    _energy_score = random.randint(1, 10)
    _personality["energy_score"] = _energy_score

    print(f"🎭  Personality loaded: {_personality['name']}  "
          f"(tone={_personality['tone']}, energy={_energy_score}/10)")

    return _personality


def get_personality() -> dict:
    """Return the current personality dict (call after load_personality)."""
    return _personality


def get_energy_score() -> int:
    """Return the session's energy score (1–10)."""
    return _energy_score


def get_personality_prompt() -> str:
    """
    Build a concise system-prompt fragment from personality config.

    This string is prepended to the response engine's system prompt
    so the LLM adopts the right tone and style.
    """
    p = _personality
    name = p.get("name", "Buddy")
    tone = p.get("tone", "friendly")
    style = p.get("style", "short")
    energy = _energy_score

    # Map energy to adjective
    if energy >= 8:
        energy_adj = "very energetic and enthusiastic"
    elif energy >= 5:
        energy_adj = "moderately expressive"
    else:
        energy_adj = "calm and reserved"

    # Map style to instruction
    style_map = {
        "short": "Keep responses brief (1–2 sentences).",
        "expressive": "Be a bit more expressive, use occasional emoji.",
        "minimal": "Respond in as few words as possible.",
    }
    style_instr = style_map.get(style, style_map["short"])

    return (
        f"Your name is {name}. "
        f"Speak in a {tone} tone. "
        f"You are {energy_adj} today. "
        f"{style_instr}"
    )


def should_react() -> bool:
    """
    Decide whether a micro-reaction should fire based on personality.

    Higher energy + expressive reaction_style → more reactions.
    """
    style = _personality.get("reaction_style", "expressive")

    if style == "expressive":
        threshold = 3   # fires if energy >= 3  (most of the time)
    elif style == "moderate":
        threshold = 5
    else:  # "minimal"
        threshold = 8

    return _energy_score >= threshold
