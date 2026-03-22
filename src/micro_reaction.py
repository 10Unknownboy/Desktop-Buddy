"""
micro_reaction.py - Lightweight micro-reaction system.

Plays a quick filler phrase via TTS when the user pauses briefly
(Stage 1 silence).  No LLM call – purely random selection from a
short list of conversational fillers.
"""

import random

from src.tts import speak

# ---------------------------------------------------------------------------
# Reaction phrases – kept intentionally short for instant TTS synthesis
# ---------------------------------------------------------------------------
REACTIONS: list[str] = [
    "hmm...",
    "oh...",
    "yeah...",
    "uh-huh...",
    "mhm...",
    "right...",
    "okay...",
    "I see...",
]


def play_micro_reaction() -> None:
    """
    Select a random filler phrase and speak it immediately.

    This function is designed to be called as a callback from the
    silence-detection system.  It must be lightweight and fast:
        - No LLM call
        - No network round-trip beyond the TTS API
        - Random selection is O(1)

    The ~0.3–0.5 s delay before this function is called is handled
    by the caller (audio_input.listen_continuous).
    """
    phrase = random.choice(REACTIONS)
    print(f"🎭  Micro-reaction: \"{phrase}\"")
    speak(phrase)
