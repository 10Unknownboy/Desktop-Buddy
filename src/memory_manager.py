"""
memory_manager.py - User Digital Memory System.

Provides a lightweight JSON-backed memory that the decision engine
controls.  Supports:
    * Selective field loading (only read what you need)
    * Targeted writes (update one section at a time)
    * Mood tracking  (mood_score −10 to +10)
    * Engagement meter  (0–10, recalculated periodically)
    * Presence simulation  (idle prompts when engagement is low)
"""

import json
import random
import time
from pathlib import Path

from src.config import DATA_DIR

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
MEMORY_FILE: Path = DATA_DIR / "memory.json"

# Mood boundaries
MOOD_MIN = -10
MOOD_MAX = 10

# Engagement window (seconds) – roughly 7–10 minutes
ENGAGEMENT_WINDOW = 8 * 60   # 8 min average
MIN_PRESENCE_INTERVAL = 7 * 60   # don't prompt more than every 7 min

# Emotion → mood delta mapping
_EMOTION_DELTAS: dict[str, int] = {
    "happy": +2,
    "neutral": 0,
    "frustrated": -2,
    "sad": -3,
}

# Presence prompts (spoken when engagement is low)
_PRESENCE_PROMPTS: list[str] = [
    "Hey, what are you working on?",
    "Everything going okay?",
    "Need any help with anything?",
    "Just checking in – you good?",
    "Let me know if you need anything.",
]

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_memory: dict = {}
_last_presence_ts: float = 0.0   # timestamp of last presence prompt
_session_start_ts: float = 0.0


# ---------------------------------------------------------------------------
# Default memory template
# ---------------------------------------------------------------------------
_DEFAULT_MEMORY: dict = {
    "user_profile": {
        "name": "",
        "preferences": {},
        "behavior_patterns": {},
        "interests": {},
    },
    "mood_memory": {
        "recent_mood": "neutral",
        "mood_score": 0,
    },
    "activity_log": {
        "current_activity": "",
        "recent_apps": [],
    },
    "conversation_context": {
        "last_messages": [],
    },
    "advice_usage": {
        "count": 0,
    },
    "engagement": {
        "score": 5,
        "last_interaction_ts": 0,
        "interaction_count_window": 0,
    },
}


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def load_memory() -> dict:
    """
    Load the full memory from disk (call once at startup).

    Creates the file with defaults if it doesn't exist.
    """
    global _memory, _session_start_ts, _last_presence_ts

    _session_start_ts = time.time()
    _last_presence_ts = time.time()  # don't prompt immediately

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            _memory = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("[INFO] memory.json not found, creating with defaults.")
        _memory = _deep_copy_defaults()
        save()

    # Merge any missing top-level keys from defaults
    for key, default_val in _DEFAULT_MEMORY.items():
        if key not in _memory:
            _memory[key] = (
                dict(default_val) if isinstance(default_val, dict)
                else list(default_val) if isinstance(default_val, list)
                else default_val
            )

    print(f"📦  Memory loaded  (mood={_memory['mood_memory']['recent_mood']}, "
          f"engagement={_memory['engagement']['score']})")

    return _memory


def get_relevant_memory(*fields: str) -> dict:
    """
    Return only the requested sections of memory.

    Args:
        *fields: Section names to include, e.g.
                 ``get_relevant_memory("mood_memory", "user_profile")``

    Returns:
        Dict containing only the requested sections.
    """
    return {k: _memory[k] for k in fields if k in _memory}


def update_memory(field: str, key: str, value) -> None:
    """
    Update a single key inside a memory section.

    Args:
        field: Top-level section name (e.g. "user_profile").
        key:   Key within the section (e.g. "name").
        value: New value to set.
    """
    if field not in _memory:
        _memory[field] = {}

    section = _memory[field]
    if isinstance(section, dict):
        section[key] = value

    save()


def add_context_message(role: str, text: str, max_messages: int = 6) -> None:
    """Append a message to conversation_context.last_messages."""
    msgs = _memory.setdefault("conversation_context", {}).setdefault("last_messages", [])
    msgs.append({"role": role, "text": text, "ts": time.time()})
    # Keep only the most recent messages
    if len(msgs) > max_messages:
        _memory["conversation_context"]["last_messages"] = msgs[-max_messages:]
    save()


# ---------------------------------------------------------------------------
# Mood system
# ---------------------------------------------------------------------------

def update_mood(emotion: str) -> None:
    """
    Adjust mood_score based on the detected emotion.

    Clamps to [MOOD_MIN, MOOD_MAX].
    """
    delta = _EMOTION_DELTAS.get(emotion, 0)
    mood = _memory.setdefault("mood_memory", {"recent_mood": "neutral", "mood_score": 0})
    mood["mood_score"] = max(MOOD_MIN, min(MOOD_MAX, mood["mood_score"] + delta))
    mood["recent_mood"] = emotion
    save()


def get_mood_summary() -> str:
    """Return a short summary string for injection into prompts."""
    mood = _memory.get("mood_memory", {})
    score = mood.get("mood_score", 0)
    mood_type = mood.get("recent_mood", "neutral")

    if score >= 5:
        feel = "good"
    elif score >= 0:
        feel = "okay"
    elif score >= -5:
        feel = "a bit down"
    else:
        feel = "not great"

    return f"User mood: {mood_type} (feels {feel}, score {score})"


# ---------------------------------------------------------------------------
# Engagement meter
# ---------------------------------------------------------------------------

def record_interaction() -> None:
    """Record that an interaction just happened (called each turn)."""
    eng = _memory.setdefault("engagement", {
        "score": 5, "last_interaction_ts": 0, "interaction_count_window": 0
    })
    eng["last_interaction_ts"] = time.time()
    eng["interaction_count_window"] = eng.get("interaction_count_window", 0) + 1
    _recalculate_engagement()
    save()


def _recalculate_engagement() -> None:
    """Compute engagement score (0–10) based on interaction frequency."""
    eng = _memory.get("engagement", {})
    count = eng.get("interaction_count_window", 0)
    elapsed = time.time() - _session_start_ts

    if elapsed < 60:
        eng["score"] = 5  # not enough data yet
        return

    # interactions per minute
    ipm = count / (elapsed / 60.0)

    # Map: 0 ipm → 0, 2+ ipm → 10
    score = min(10, int(ipm * 5))
    eng["score"] = score


def get_engagement_score() -> int:
    """Return the current engagement score (0–10)."""
    return _memory.get("engagement", {}).get("score", 5)


# ---------------------------------------------------------------------------
# Presence simulation
# ---------------------------------------------------------------------------

def get_presence_prompt() -> str | None:
    """
    Return an idle prompt if engagement is low and enough time has passed.

    Returns None if no prompt should be spoken.
    """
    global _last_presence_ts

    now = time.time()
    score = get_engagement_score()

    # Only fire when engagement is low (≤ 3)
    if score > 3:
        return None

    # Respect minimum interval
    if now - _last_presence_ts < MIN_PRESENCE_INTERVAL:
        return None

    _last_presence_ts = now
    return random.choice(_PRESENCE_PROMPTS)


# ---------------------------------------------------------------------------
# Advice tracking (bridges main.py _state)
# ---------------------------------------------------------------------------

def get_advice_count() -> int:
    """Return the stored advice usage count."""
    return _memory.get("advice_usage", {}).get("count", 0)


def increment_advice_count() -> None:
    """Increment and persist the advice count."""
    adv = _memory.setdefault("advice_usage", {"count": 0})
    adv["count"] = adv.get("count", 0) + 1
    save()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save() -> None:
    """Flush current memory state to disk."""
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_memory, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save memory: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy_defaults() -> dict:
    """Return a deep copy of the default memory template."""
    return json.loads(json.dumps(_DEFAULT_MEMORY))
