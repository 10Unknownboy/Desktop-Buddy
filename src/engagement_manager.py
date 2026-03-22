"""
engagement_manager.py - Conversation Engagement Meter.

Evaluates conversation quality every 7–10 minutes and produces
a score (0–10) that influences the decision engine's behavior:
    * Low  (0–3): calm tone, may trigger presence prompts
    * Mid  (4–6): normal behaviour
    * High (7–10): energetic tone, playful interactions

Scoring factors:
    * Interaction frequency (messages per minute)
    * Variety of intents (diverse > repetitive)
    * Emotional valence shifts (engaging if user shows emotion)
    * Message length trends (longer = more engaged)
"""

import random
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EVAL_INTERVAL_MIN = 7 * 60    # 7 minutes
EVAL_INTERVAL_MAX = 10 * 60   # 10 minutes
PRESENCE_COOLDOWN = 7 * 60    # don't prompt more than every 7 min

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_interaction_log: list[dict] = []   # {"ts", "intent", "emotion", "text_len"}
_engagement_score: int = 5
_last_eval_ts: float = 0.0
_last_presence_ts: float = 0.0
_next_eval_interval: float = 8 * 60   # randomised each eval

# ---------------------------------------------------------------------------
# Presence prompts
# ---------------------------------------------------------------------------
_PRESENCE_PROMPTS: list[str] = [
    "Hey, what are you working on?",
    "Everything going okay?",
    "Need any help with anything?",
    "Just checking in, you good?",
    "Let me know if you need anything.",
    "Anything on your mind?",
]

_TIME_PRESENCE: dict[str, list[str]] = {
    "morning": [
        "Good morning! Ready to start the day?",
        "Morning! Need any help today?",
    ],
    "afternoon": [
        "How's the afternoon going?",
        "Need anything this afternoon?",
    ],
    "evening": [
        "How's the evening going?",
        "Winding down for the day?",
    ],
    "night": [
        "Getting late, everything okay?",
        "You should probably get some rest soon.",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_engagement() -> None:
    """Initialise engagement tracking at startup."""
    global _last_eval_ts, _last_presence_ts, _next_eval_interval
    _last_eval_ts = time.time()
    _last_presence_ts = time.time()   # don't prompt immediately
    _next_eval_interval = random.uniform(EVAL_INTERVAL_MIN, EVAL_INTERVAL_MAX)


def record_interaction(intent: str = "", emotion: str = "", text_len: int = 0) -> None:
    """Record a user interaction for engagement analysis."""
    _interaction_log.append({
        "ts": time.time(),
        "intent": intent,
        "emotion": emotion,
        "text_len": text_len,
    })
    # Only keep last 30 min of data
    cutoff = time.time() - 30 * 60
    while _interaction_log and _interaction_log[0]["ts"] < cutoff:
        _interaction_log.pop(0)


def evaluate_engagement() -> int:
    """
    Re-evaluate engagement if enough time has elapsed.

    Returns the current engagement score (0–10).
    Self-throttled by randomised 7–10 min interval.
    """
    global _engagement_score, _last_eval_ts, _next_eval_interval

    now = time.time()
    if now - _last_eval_ts < _next_eval_interval:
        return _engagement_score

    _last_eval_ts = now
    _next_eval_interval = random.uniform(EVAL_INTERVAL_MIN, EVAL_INTERVAL_MAX)

    if not _interaction_log:
        _engagement_score = 0
        return 0

    # Factor 1: Interaction frequency (0–4 points)
    window_mins = max(1, (now - _interaction_log[0]["ts"]) / 60.0)
    ipm = len(_interaction_log) / window_mins
    freq_score = min(4, int(ipm * 2))

    # Factor 2: Intent diversity (0–3 points)
    unique_intents = set(e["intent"] for e in _interaction_log if e["intent"])
    diversity_score = min(3, len(unique_intents))

    # Factor 3: Emotional engagement (0–3 points)
    emotional_msgs = sum(
        1 for e in _interaction_log
        if e["emotion"] not in ("neutral", "")
    )
    emotion_score = min(3, emotional_msgs)

    _engagement_score = min(10, freq_score + diversity_score + emotion_score)

    print(f"📊  Engagement: {_engagement_score}/10  "
          f"(freq={freq_score}, diversity={diversity_score}, emotion={emotion_score})")

    return _engagement_score


def get_engagement_score() -> int:
    """Return the current engagement score without re-evaluating."""
    return _engagement_score


def get_engagement_context() -> str:
    """Return a short string for prompt injection."""
    score = _engagement_score
    if score >= 7:
        level = "high"
    elif score >= 4:
        level = "moderate"
    else:
        level = "low"
    return f"Engagement: {level} ({score}/10)"


def get_tone_adjustment() -> str:
    """Suggest a tone based on engagement level."""
    if _engagement_score >= 7:
        return "energetic and playful"
    elif _engagement_score >= 4:
        return "normal"
    else:
        return "calm and supportive"


def get_presence_prompt(time_period: str = "") -> str | None:
    """
    Return an idle prompt if engagement is low and enough time passed.

    Args:
        time_period: "morning"/"afternoon"/"evening"/"night" for
                     time-appropriate prompts.

    Returns None if no prompt should fire.
    """
    global _last_presence_ts

    now = time.time()

    # Only fire when engagement is low (≤ 3)
    if _engagement_score > 3:
        return None

    # Respect cooldown
    if now - _last_presence_ts < PRESENCE_COOLDOWN:
        return None

    _last_presence_ts = now

    # Use time-appropriate prompts if available
    if time_period and time_period in _TIME_PRESENCE:
        pool = _TIME_PRESENCE[time_period] + _PRESENCE_PROMPTS
    else:
        pool = _PRESENCE_PROMPTS

    return random.choice(pool)
