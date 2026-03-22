"""
interruption_handler.py - Manages user interruptions during speech.

When the user speaks while the assistant is talking, the TTS module
detects it and returns ``False``.  This module then:
    1. Captures the new user speech
    2. Sends it through the decision engine
    3. Routes based on ``interrupt_action``:
        - "stop"     → discard previous response
        - "continue" → resume previous response
        - "switch"   → drop previous, start new response flow
"""

from src.audio_input import listen_continuous
from src.stt import transcribe
from src.tts import resume_speaking, get_speaking_state

import os


def handle_interruption(
    state: dict,
    personality_prompt: str,
    mood_summary: str,
) -> dict | None:
    """
    Handle a user interruption after TTS was stopped.

    Captures new speech, transcribes it, runs through the decision
    engine, and returns the instruction — OR handles continue/stop
    internally.

    Args:
        state:              Current system state (advice_count, etc.).
        personality_prompt:  Personality fragment for decision engine.
        mood_summary:        Mood summary string.

    Returns:
        The new instruction dict if action is "switch" (caller must
        handle it).  Returns None if handled internally (stop/continue).
    """
    # Import here to avoid circular imports
    from src.decision_engine import decide

    print("\n🎤  Capturing interruption …")

    # Capture the user's new speech (short window, no micro-reaction)
    audio_path = listen_continuous(on_micro_reaction=None)

    if not audio_path:
        print("⚠️  No speech captured after interruption. Resuming …")
        _try_resume()
        return None

    # Transcribe
    stt_result = transcribe(audio_path)
    text = stt_result["text"]
    confidence = stt_result["confidence"]

    try:
        os.remove(audio_path)
    except OSError:
        pass

    if not text:
        print("⚠️  Empty transcription after interruption. Resuming …")
        _try_resume()
        return None

    # Run through decision engine (it will set interrupt_action)
    instruction = decide(
        user_text=text,
        confidence=confidence,
        state=state,
        personality_prompt=personality_prompt,
        mood_summary=mood_summary,
    )

    action = instruction.get("interrupt_action", "switch")
    speaking = get_speaking_state()

    print(f"⚡  Interrupt action: {action}")

    # -- STOP: discard previous, do nothing ------------------------------
    if action == "stop":
        print("🛑  Previous response discarded.")
        return None

    # -- CONTINUE: resume previous response ------------------------------
    if action == "continue" and speaking.get("has_remaining", False):
        print("▶️  Resuming previous response …")
        completed = resume_speaking()
        if not completed:
            # Interrupted again during resume — recurse
            return handle_interruption(state, personality_prompt, mood_summary)
        return None

    # -- SWITCH: return instruction for caller to process ----------------
    print("🔄  Switching to new context.")
    return instruction


def _try_resume() -> None:
    """Attempt to resume previous speech if there's remaining audio."""
    state = get_speaking_state()
    if state.get("has_remaining", False):
        resume_speaking()
