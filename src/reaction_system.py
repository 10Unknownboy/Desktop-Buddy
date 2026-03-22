"""
reaction_system.py - Advanced Reaction System.

Provides emotion-aware, personality-influenced micro-reactions that
feel natural and human-like.  NO LLM calls — pure local logic.

Features:
    * Emotion × intent reaction pools
    * Personality-driven gating + style
    * Recent-history variation (no repeats in last 5)
    * Randomised natural delay (0.3–0.8 s)
    * Two entry points:
        - get_silence_reaction()   → for the silence-detection callback
        - get_directed_reaction()  → for decision-engine LISTEN mode
"""

import random
import time

from src.tts import speak

# ---------------------------------------------------------------------------
# Reaction pools — organised by emotion
# ---------------------------------------------------------------------------
_EMOTION_POOLS: dict[str, list[str]] = {
    "happy": [
        "haha", "hehe", "nice!", "ohh nice...", "haha nice",
        "yeah!", "oh wow", "awesome",
    ],
    "neutral": [
        "hmm...", "hmm okay...", "yeah...", "uh-huh...",
        "mhm...", "right...", "okay...", "I see...",
    ],
    "frustrated": [
        "hmm...", "oh...", "hmm I see...", "oh okay...",
        "right...", "hmm...",
    ],
    "sad": [
        "aww...", "oh...", "hmm...", "oh no...",
        "aww I see...", "hmm...",
    ],
}

# ---------------------------------------------------------------------------
# Intent modifiers — if intent matches, prefer these
# ---------------------------------------------------------------------------
_INTENT_EXTRAS: dict[str, list[str]] = {
    "rant":              ["hmm...", "oh...", "right...", "I see..."],
    "question":          ["hmm...", "hmm okay...", "oh..."],
    "thinking_aloud":    ["hmm...", "mhm...", "yeah...", "hmm interesting..."],
    "greeting":          ["hey!", "oh hey!", "hi!"],
    "technical_issue":   ["hmm...", "oh okay...", "hmm I see..."],
    "emotional_support": ["aww...", "oh...", "hmm...", "I see..."],
}

# ---------------------------------------------------------------------------
# Directed type pools (used when decision engine sends a specific type)
# ---------------------------------------------------------------------------
_DIRECTED_POOLS: dict[str, list[str]] = {
    "hmm":   ["hmm...", "hmm okay...", "hmm I see...", "hmm interesting..."],
    "oh":    ["oh...", "oh!", "oh okay...", "oh wow", "ohh nice..."],
    "laugh": ["haha", "hehe", "ha!", "haha nice"],
    "aww":   ["aww...", "aww I see...", "oh no...", "oh..."],
    "none":  [],
}

# ---------------------------------------------------------------------------
# Silence-detection generic pool (fallback, emotion-unaware)
# ---------------------------------------------------------------------------
_SILENCE_POOL: list[str] = [
    "hmm...", "hmm okay...", "oh...", "yeah...",
    "uh-huh...", "mhm...", "right...", "okay...", "I see...",
]

# ---------------------------------------------------------------------------
# Variation history (prevents repeating same reaction)
# ---------------------------------------------------------------------------
_HISTORY_SIZE = 5
_recent_history: list[str] = []


# ---------------------------------------------------------------------------
# Core selection logic
# ---------------------------------------------------------------------------

def _pick_varied(pool: list[str]) -> str:
    """
    Pick a reaction from *pool* that hasn't been used recently.

    Falls back to random if all candidates are in history.
    """
    # Filter out recently used
    candidates = [r for r in pool if r not in _recent_history]
    if not candidates:
        candidates = pool  # fallback: allow repeats

    choice = random.choice(candidates)

    # Update history
    _recent_history.append(choice)
    if len(_recent_history) > _HISTORY_SIZE:
        _recent_history.pop(0)

    return choice


def _natural_delay() -> None:
    """Sleep a randomised 0.3–0.8 seconds for a natural feel."""
    time.sleep(random.uniform(0.3, 0.8))


# ---------------------------------------------------------------------------
# Public API — silence-detection callback
# ---------------------------------------------------------------------------

def get_silence_reaction() -> str | None:
    """
    Select a generic reaction for the silence-detection callback.

    Returns the phrase to speak, or None if personality says skip.
    This is emotion-unaware (no instruction available at silence time).
    """
    return _pick_varied(_SILENCE_POOL)


def play_silence_reaction() -> None:
    """
    Silence-detection callback: pick a reaction, wait, speak.

    Designed to be passed as ``on_micro_reaction`` to
    ``listen_continuous()``.
    """
    phrase = get_silence_reaction()
    if not phrase:
        return

    _natural_delay()
    print(f'🎭  Reaction: "{phrase}"')
    speak(phrase)


# ---------------------------------------------------------------------------
# Public API — decision-engine directed reactions
# ---------------------------------------------------------------------------

def get_directed_reaction(
    instruction: dict,
    personality: dict | None = None,
) -> str | None:
    """
    Select a reaction based on decision-engine output + personality.

    Uses emotion, intent, and micro_reaction type for best match.

    Args:
        instruction:  Instruction dict from the decision engine.
        personality:  Personality dict (optional).

    Returns:
        Phrase to speak, or None if reaction should be skipped.
    """
    reaction_type = instruction.get("micro_reaction", "none")

    # Decision engine says no reaction
    if reaction_type == "none":
        return None

    # Personality gating
    if personality:
        style = personality.get("reaction_style", "expressive")
        energy = personality.get("energy_score", 5)

        if style == "minimal" and energy < 5:
            return None  # skip reaction
        if style == "moderate" and energy < 3:
            return None

    # Build a merged candidate pool
    emotion = instruction.get("emotion", "neutral")
    intent = instruction.get("intent", "thinking_aloud")

    pool: list[str] = []

    # 1. Start with directed type pool
    pool.extend(_DIRECTED_POOLS.get(reaction_type, []))

    # 2. Add emotion-appropriate reactions
    pool.extend(_EMOTION_POOLS.get(emotion, _EMOTION_POOLS["neutral"]))

    # 3. Sprinkle in intent-specific extras
    pool.extend(_INTENT_EXTRAS.get(intent, []))

    if not pool:
        pool = _SILENCE_POOL

    return _pick_varied(pool)


def play_directed_reaction(
    instruction: dict,
    personality: dict | None = None,
) -> None:
    """
    Select and play an emotion/personality-aware reaction.

    Called from main.py when mode=LISTEN.
    """
    phrase = get_directed_reaction(instruction, personality)
    if not phrase:
        print("🎭  Reaction: skipped (personality/decision)")
        return

    _natural_delay()
    emotion = instruction.get("emotion", "neutral")
    print(f'🎭  Reaction ({emotion}): "{phrase}"')
    speak(phrase)
