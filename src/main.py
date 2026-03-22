"""
main.py - Entry point for Desktop Buddy.

Runs an always-on listening loop with:
    * Decision-engine routing
    * Personality system
    * Advanced reaction system
    * Memory management (mood, engagement, presence)
    * Interruption handling
    * System awareness
    * Time awareness
    * Background listening mode

Press Ctrl+C to exit gracefully.
"""

import os

from src.audio_input import listen_continuous
from src.stt import transcribe
from src.decision_engine import decide, update_context
from src.response_engine import generate_response
from src.tts import speak, speak_interruptible
from src.reaction_system import play_silence_reaction, play_directed_reaction
from src.personality import load_personality, get_personality, get_personality_prompt, should_react
from src.interruption_handler import handle_interruption
from src.system_monitor import check_system
from src.engagement_manager import (
    init_engagement,
    record_interaction as record_eng_interaction,
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
)


def main() -> None:
    """Run the assistant loop."""

    # -- Startup ----------------------------------------------------------
    personality = load_personality()
    memory = load_memory()
    init_engagement()
    init_background()

    state: dict = {
        "advice_count": get_advice_count(),
        "current_mode": None,
    }

    print("=" * 50)
    print(f"  🤖  {personality.get('name', 'Desktop Buddy')} – Online")
    print("=" * 50)
    print(f"  Personality: {personality.get('tone', 'friendly')} · "
          f"Energy: {personality.get('energy_score', 5)}/10")
    print(f"  Time: {get_time_period()}")
    print("  Systems: listening · decision · interruptions · monitoring")
    print("  Press Ctrl+C to exit.\n")

    # Startup greeting
    greeting = get_greeting()
    print(f'👋  "{greeting}"')
    speak(greeting)

    try:
        while True:
            # -- System checks (self-throttled) ---------------------------
            _check_system_alerts(personality)

            # -- Engagement evaluation (self-throttled 7–10 min) ----------
            evaluate_engagement()

            # -- Background music check -----------------------------------
            if not bg_is_playing():
                bg_check_and_play(get_engagement_score())

            # -- Presence / rest check ------------------------------------
            _check_presence_and_rest()

            # -- Listen ---------------------------------------------------
            on_react = play_silence_reaction if should_react() else None
            audio_path = listen_continuous(on_micro_reaction=on_react)

            if not audio_path:
                print("⚠️  No audio captured. Listening again …\n")
                continue

            # -- Stop background audio if playing -------------------------
            if bg_is_playing():
                stop_background_audio()

            # -- Transcribe -----------------------------------------------
            stt_result = transcribe(audio_path)
            text = stt_result["text"]
            confidence = stt_result["confidence"]

            try:
                os.remove(audio_path)
            except OSError:
                pass

            if not text:
                print("⚠️  No speech detected. Listening again …\n")
                continue

            # -- Record interaction for all systems -----------------------
            update_last_interaction()
            record_eng_interaction(
                intent="",   # will be filled after decision
                emotion="",
                text_len=len(text),
            )

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

            # -- Record enriched interaction data -------------------------
            record_eng_interaction(
                intent=instruction.get("intent", ""),
                emotion=instruction.get("emotion", ""),
                text_len=len(text),
            )

            # -- Side effects: mood, memory, context ----------------------
            update_mood(instruction.get("emotion", "neutral"))

            if instruction.get("memory_write") and instruction.get("memory_field"):
                update_memory(instruction["memory_field"], "last_value", text)

            add_context_message("user", text)

            # -- Route ----------------------------------------------------
            _handle_instruction(instruction, state, personality)

            print()

    except KeyboardInterrupt:
        if bg_is_playing():
            stop_background_audio()
        print(f"\n\n👋  {personality.get('name', 'Desktop Buddy')} shutting down. Goodbye!")


def _check_system_alerts(personality: dict) -> None:
    """Check for system alerts and speak them."""
    events = check_system()
    for event in events:
        msg = event.get("message", "")
        if msg:
            print(f"🖥️  System alert: {msg}")
            speak(msg)
            add_context_message("system", msg)


def _check_presence_and_rest() -> None:
    """Check for presence prompt or rest suggestion."""
    # Rest reminder
    if should_suggest_rest():
        reminder = get_rest_reminder()
        # Use presence prompt mechanics (cooldown built in)
        prompt = get_presence_prompt(get_time_period())
        if prompt:
            print(f'💭  Presence: "{prompt}"')
            speak(prompt)
            add_context_message("assistant", prompt)
            return

    # Normal presence prompt
    prompt = get_presence_prompt(get_time_period())
    if prompt:
        print(f'💭  Presence: "{prompt}"')
        speak(prompt)
        add_context_message("assistant", prompt)


def _handle_instruction(instruction: dict, state: dict, personality: dict) -> None:
    """Route the instruction to the appropriate action."""
    mode = instruction.get("mode", "LISTEN")

    # -- IGNORE -----------------------------------------------------------
    if mode == "IGNORE":
        print("🤫  Ignoring input.")
        return

    # -- LISTEN (reaction only) -------------------------------------------
    if mode == "LISTEN":
        play_directed_reaction(instruction, personality)
        return

    # -- REDIRECT / SHORT_REPLY / ADVICE → generate response --------------
    response = generate_response(instruction)

    if response:
        completed = speak_interruptible(response)
        update_context("assistant", response)
        add_context_message("assistant", response)

        if not completed:
            new_instruction = handle_interruption(
                state=state,
                personality_prompt=get_personality_prompt(),
                mood_summary=get_mood_summary(),
            )
            if new_instruction:
                _handle_instruction(new_instruction, state, personality)

    # Track advice usage
    if mode == "ADVICE":
        increment_advice_count()
        state["advice_count"] = get_advice_count()
        print(f"📊  Advice count: {state['advice_count']}")


if __name__ == "__main__":
    main()
