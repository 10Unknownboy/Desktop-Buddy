"""
main.py - Entry point for Desktop Buddy.

Final integrated loop with:
    * Clean startup / shutdown
    * Global state management
    * All modules connected
    * Behaviour limiters
    * Error handling at every stage

Press Ctrl+C to exit gracefully.
"""

import os
import sys
import time

from src.logger import setup_logging, get_logger
from src.audio_input import listen_continuous
from src.stt import transcribe
from src.decision_engine import decide, update_context
from src.response_engine import generate_response
from src.tts import speak, stop_speaking
from src.reaction_system import play_silence_reaction, play_directed_reaction
from src.personality import load_personality, get_personality_prompt, should_react
from src.interruption_handler import handle_interruption
from src.system_monitor import check_system
from src.engagement_manager import (
    init_engagement,
    record_interaction as record_eng,
    evaluate_engagement,
    get_engagement_score,
    get_engagement_context,
    get_presence_prompt,
)
from src.time_awareness import (
    get_time_period,
    get_time_context,
    get_greeting,
    should_suggest_rest,
    get_rest_reminder,
)
from src.background_mode import (
    init_background,
    update_last_interaction,
    is_playing as bg_is_playing,
    stop_background_audio,
    check_and_play as bg_check_and_play,
)
from src.memory_manager import (
    load_memory,
    update_memory,
    update_mood,
    get_mood_summary,
    get_advice_count,
    increment_advice_count,
    add_context_message,
    save as save_memory,
)

log = get_logger("main")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
state: dict = {
    "is_listening": False,
    "is_speaking": False,
    "current_mode": None,
    "advice_count": 0,
    "engagement_score": 0,
    "mood_score": 0,
    "turns_this_session": 0,
}

# Behaviour limiters
ADVICE_DAILY_LIMIT = 15
PRESENCE_MIN_TURNS = 3       # don't prompt until N turns into session
REST_REMINDER_COOLDOWN = 30 * 60   # 30 min between rest reminders
_last_rest_ts: float = 0.0


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _startup() -> dict:
    """Initialise all systems. Returns personality dict."""
    setup_logging()
    log.info("=" * 50)

    personality = load_personality()
    load_memory()
    init_engagement()
    init_background()

    state["advice_count"] = get_advice_count()

    log.info(f"  🤖  {personality.get('name', 'Desktop Buddy')} – Online")
    log.info(f"  Personality: {personality.get('tone', 'friendly')} · "
             f"Energy: {personality.get('energy_score', 5)}/10")
    log.info(f"  Time: {get_time_period()}")
    log.info("  All systems active. Press Ctrl+C to exit.")
    log.info("=" * 50)

    # Startup greeting
    greeting = get_greeting()
    log.info(f'👋  "{greeting}"')
    speak(greeting)

    return personality


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

def _shutdown(personality: dict) -> None:
    """Clean shutdown: save state, stop audio, log farewell."""
    log.info("Shutting down …")

    if bg_is_playing():
        stop_background_audio()

    save_memory()
    log.info("💾  Memory saved.")

    name = personality.get("name", "Desktop Buddy")
    log.info(f"👋  {name} shutting down. Goodbye!")


# ---------------------------------------------------------------------------
# Background checks (called every loop iteration, self-throttled)
# ---------------------------------------------------------------------------

def _run_background_checks(personality: dict) -> None:
    """System alerts, engagement eval, background audio, presence."""

    # System monitoring
    try:
        for event in check_system():
            msg = event.get("message", "")
            if msg:
                log.info(f"🖥️  System: {msg}")
                speak(msg)
                add_context_message("system", msg)
    except Exception as e:
        log.warning(f"[MONITOR] {e}")

    # Engagement evaluation
    try:
        evaluate_engagement()
        state["engagement_score"] = get_engagement_score()
    except Exception as e:
        log.warning(f"[ENGAGEMENT] {e}")

    # Background audio
    try:
        if not bg_is_playing():
            bg_check_and_play(get_engagement_score())
    except Exception as e:
        log.warning(f"[BACKGROUND] {e}")

    # Presence / rest prompts
    try:
        _check_presence_and_rest()
    except Exception as e:
        log.warning(f"[PRESENCE] {e}")


def _check_presence_and_rest() -> None:
    """Time-aware presence prompts with limiters."""
    global _last_rest_ts

    # Don't prompt too early in session
    if state["turns_this_session"] < PRESENCE_MIN_TURNS:
        return

    # Rest reminder (late night only, with cooldown)
    if should_suggest_rest():
        now = time.time()
        if now - _last_rest_ts >= REST_REMINDER_COOLDOWN:
            reminder = get_rest_reminder()
            log.info(f'😴  Rest: "{reminder}"')
            speak(reminder)
            add_context_message("assistant", reminder)
            _last_rest_ts = now
            return

    # Normal presence prompt
    prompt = get_presence_prompt(get_time_period())
    if prompt:
        log.info(f'💭  Presence: "{prompt}"')
        speak(prompt)
        add_context_message("assistant", prompt)


# ---------------------------------------------------------------------------
# Instruction routing
# ---------------------------------------------------------------------------

def _handle_instruction(instruction: dict, personality: dict) -> None:
    """Route the instruction to the appropriate action."""
    mode = instruction.get("mode", "LISTEN")

    # -- IGNORE -----------------------------------------------------------
    if mode == "IGNORE":
        log.info("🤫  Ignoring input.")
        return

    # -- LISTEN (reaction only) -------------------------------------------
    if mode == "LISTEN":
        play_directed_reaction(instruction, personality)
        return

    # -- ADVICE daily limit check -----------------------------------------
    if mode == "ADVICE" and state["advice_count"] >= ADVICE_DAILY_LIMIT:
        log.info("📊  Daily advice limit reached → SHORT_REPLY")
        instruction["mode"] = "SHORT_REPLY"
        instruction["max_length"] = "short"

    # -- Generate + speak response ----------------------------------------
    try:
        response = generate_response(instruction)
    except Exception as e:
        log.error(f"[RESPONSE] {e}")
        response = "Something went wrong… try again?"

    if response:
        completed = speak(response)
        update_context("assistant", response)
        add_context_message("assistant", response)

        # Handle interruption
        if not completed:
            try:
                new_instruction = handle_interruption(
                    state=state,
                    personality_prompt=get_personality_prompt(),
                    mood_summary=get_mood_summary(),
                )
                if new_instruction:
                    _handle_instruction(new_instruction, personality)
            except Exception as e:
                log.error(f"[INTERRUPT] {e}")

    # Advice tracking
    if instruction.get("mode") == "ADVICE":
        increment_advice_count()
        state["advice_count"] = get_advice_count()
        log.info(f"📊  Advice: {state['advice_count']}/{ADVICE_DAILY_LIMIT}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the assistant."""

    personality = _startup()

    try:
        while True:
            state["is_listening"] = True
            state["is_speaking"] = False

            # -- Background checks (self-throttled) -----------------------
            _run_background_checks(personality)

            # -- Listen ---------------------------------------------------
            on_react = play_silence_reaction if should_react() else None
            audio_path = listen_continuous(on_micro_reaction=on_react)

            if not audio_path:
                continue

            # Stop background audio on speech
            if bg_is_playing():
                stop_background_audio()

            state["is_listening"] = False

            # -- Transcribe -----------------------------------------------
            stt_result = transcribe(audio_path)
            text = stt_result["text"]
            confidence = stt_result["confidence"]

            try:
                os.remove(audio_path)
            except OSError:
                pass

            if not text:
                continue

            # -- Record interaction for all systems -----------------------
            update_last_interaction()
            record_eng(intent="", emotion="", text_len=len(text))
            state["turns_this_session"] += 1

            # -- Decide ---------------------------------------------------
            instruction = decide(
                user_text=text,
                confidence=confidence,
                state=state,
                personality_prompt=get_personality_prompt(),
                mood_summary=get_mood_summary(),
                engagement_context=get_engagement_context(),
                time_context=get_time_context(),
            )

            state["current_mode"] = instruction["mode"]

            # Enrich engagement data
            record_eng(
                intent=instruction.get("intent", ""),
                emotion=instruction.get("emotion", ""),
                text_len=len(text),
            )

            # -- Side effects ---------------------------------------------
            update_mood(instruction.get("emotion", "neutral"))

            if instruction.get("memory_write") and instruction.get("memory_field"):
                update_memory(instruction["memory_field"], "last_value", text)

            add_context_message("user", text)

            # -- Route ----------------------------------------------------
            state["is_speaking"] = True
            _handle_instruction(instruction, personality)
            state["is_speaking"] = False

    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.error(f"[FATAL] Unhandled error: {e}", exc_info=True)
    finally:
        _shutdown(personality)


if __name__ == "__main__":
    main()
