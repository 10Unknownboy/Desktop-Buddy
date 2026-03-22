"""
time_awareness.py - Time-of-Day Awareness.

Detects the current time period and provides context that
influences the assistant's tone, greetings, and behaviour.

Time periods:
    morning      (5:00–12:00)  → light, fresh tone
    afternoon    (12:00–17:00) → normal tone
    evening      (17:00–21:00) → warm, winding-down tone
    night        (21:00–0:00)  → calm, soft tone
    late_night   (0:00–5:00)   → suggest rest
"""

from datetime import datetime

# ---------------------------------------------------------------------------
# Time period definitions
# ---------------------------------------------------------------------------
_PERIODS = [
    (5, "morning"),
    (12, "afternoon"),
    (17, "evening"),
    (21, "night"),
    (24, "late_night"),  # 0:00–5:00 wraps
]

# ---------------------------------------------------------------------------
# Tone map per time period
# ---------------------------------------------------------------------------
_TONE_MAP: dict[str, str] = {
    "morning": "light and fresh",
    "afternoon": "normal and friendly",
    "evening": "warm and relaxed",
    "night": "calm and soft",
    "late_night": "gentle, suggest rest",
}

# ---------------------------------------------------------------------------
# Greeting suggestions
# ---------------------------------------------------------------------------
_GREETINGS: dict[str, list[str]] = {
    "morning": [
        "Good morning! Ready to start?",
        "Morning! What's on the agenda today?",
    ],
    "afternoon": [
        "Good afternoon!",
        "Hey, how's your afternoon going?",
    ],
    "evening": [
        "Good evening!",
        "Hey, how's the evening treating you?",
    ],
    "night": [
        "Hey, getting late! Don't forget to rest.",
        "Evening! Need anything before you wind down?",
    ],
    "late_night": [
        "Hey, it's pretty late. You should probably get some rest!",
        "Still up? Don't forget to take a break!",
    ],
}

# ---------------------------------------------------------------------------
# Rest reminders (late_night only)
# ---------------------------------------------------------------------------
_REST_REMINDERS: list[str] = [
    "You should probably get some rest.",
    "It's getting really late, take care of yourself!",
    "Maybe time to call it a night?",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_time_period() -> str:
    """
    Return the current time period as a string.

    Returns one of: "morning", "afternoon", "evening", "night", "late_night".
    """
    hour = datetime.now().hour

    if hour < 5:
        return "late_night"

    for threshold, period in _PERIODS:
        if hour < threshold:
            return period

    return "late_night"  # fallback (shouldn't reach)


def get_time_context() -> str:
    """Return a short context string for prompt injection."""
    period = get_time_period()
    hour = datetime.now().hour
    tone = _TONE_MAP.get(period, "friendly")
    return f"Time: {period} ({hour}:00). Suggested tone: {tone}"


def get_tone_for_time() -> str:
    """Return the suggested tone modifier for the current time."""
    period = get_time_period()
    return _TONE_MAP.get(period, "friendly")


def get_greeting() -> str:
    """Return a time-appropriate greeting (for startup or idle prompt)."""
    import random
    period = get_time_period()
    pool = _GREETINGS.get(period, _GREETINGS["afternoon"])
    return random.choice(pool)


def should_suggest_rest() -> bool:
    """Return True if it's late enough to suggest rest."""
    return get_time_period() == "late_night"


def get_rest_reminder() -> str:
    """Return a rest reminder (only use if should_suggest_rest is True)."""
    import random
    return random.choice(_REST_REMINDERS)
