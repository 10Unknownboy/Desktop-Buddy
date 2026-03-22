"""
micro_reaction.py - Lightweight micro-reaction system.

Two modes of operation:
    1. play_micro_reaction()          – Random filler (silence-detection callback)
    2. play_directed_reaction(type)   – Decision-engine directed reaction
"""

import random

from src.tts import speak

# ---------------------------------------------------------------------------
# Silence-detection fillers (random, used during listening)
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

# ---------------------------------------------------------------------------
# Decision-engine directed reactions (mapped by type)
# ---------------------------------------------------------------------------
DIRECTED_REACTIONS: dict[str, list[str]] = {
    "hmm":   ["hmm...", "hmm, I see...", "hmm..."],
    "oh":    ["oh...", "oh!", "oh, okay..."],
    "laugh": ["haha", "heh", "ha!"],
    "aww":   ["aww...", "aww, I see...", "oh no..."],
    "none":  [],
}


def play_micro_reaction() -> None:
    """
    Select a random filler phrase and speak it immediately.

    Called as a callback from the silence-detection system.
    Lightweight: no LLM call, no decision logic.
    """
    phrase = random.choice(REACTIONS)
    print(f'🎭  Micro-reaction: "{phrase}"')
    speak(phrase)


def play_directed_reaction(reaction_type: str) -> None:
    """
    Play a reaction directed by the decision engine.

    Args:
        reaction_type: One of "hmm", "oh", "laugh", "aww", "none".
                       If "none" or unrecognised, does nothing.
    """
    phrases = DIRECTED_REACTIONS.get(reaction_type, [])
    if not phrases:
        return

    phrase = random.choice(phrases)
    print(f'🎭  Directed reaction ({reaction_type}): "{phrase}"')
    speak(phrase)
