"""
main.py - Entry point for Desktop Buddy.

Runs an always-on listening loop with:
    * Decision-engine routing
    * Personality system
    * Advanced reaction system
    * Memory management (mood, engagement, presence)
    * Interruption handling (user can interrupt during speech)

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
from src.memory_manager import (
    load_memory,
    update_memory,
    update_mood,
    record_interaction,
    get_mood_summary,
    get_presence_prompt,
    get_advice_count,
    increment_advice_count,
    add_context_message,
)


def main() -> None:
    """Run the assistant loop."""

    # -- Startup ----------------------------------------------------------
    personality = load_personality()
    memory = load_memory()

    state: dict = {
        "advice_count": get_advice_count(),
        "current_mode": None,
    }

    print("=" * 50)
    print(f"  🤖  {personality.get('name', 'Desktop Buddy')} – Online")
    print("=" * 50)
    print(f"  Personality: {personality.get('tone', 'friendly')} · "
          f"Energy: {personality.get('energy_score', 5)}/10")
    print("  Always-on listening · Interruptions enabled")
    print("  Press Ctrl+C to exit.\n")

    try:
        while True:
            # -- Presence check -------------------------------------------
            presence = get_presence_prompt()
            if presence:
                print(f'💭  Presence: "{presence}"')
                speak(presence)
                add_context_message("assistant", presence)

            # -- Listen ---------------------------------------------------
            on_react = play_silence_reaction if should_react() else None
            audio_path = listen_continuous(on_micro_reaction=on_react)

            if not audio_path:
                print("⚠️  No audio captured. Listening again …\n")
                continue

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

            # -- Record interaction ---------------------------------------
            record_interaction()

            # -- Decide ---------------------------------------------------
            instruction = decide(
                user_text=text,
                confidence=confidence,
                state=state,
                personality_prompt=get_personality_prompt(),
                mood_summary=get_mood_summary(),
            )

            state["current_mode"] = instruction["mode"]

            # -- Side effects: mood, memory, context ----------------------
            update_mood(instruction.get("emotion", "neutral"))

            if instruction.get("memory_write") and instruction.get("memory_field"):
                update_memory(instruction["memory_field"], "last_value", text)

            add_context_message("user", text)

            # -- Route ----------------------------------------------------
            _handle_instruction(instruction, state, personality)

            print()

    except KeyboardInterrupt:
        print(f"\n\n👋  {personality.get('name', 'Desktop Buddy')} shutting down. Goodbye!")


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
        # Use interruptible speech for full responses
        completed = speak_interruptible(response)
        update_context("assistant", response)
        add_context_message("assistant", response)

        # If interrupted, hand off to the interruption handler
        if not completed:
            new_instruction = handle_interruption(
                state=state,
                personality_prompt=get_personality_prompt(),
                mood_summary=get_mood_summary(),
            )
            # If handler returned a "switch" instruction, process it
            if new_instruction:
                _handle_instruction(new_instruction, state, personality)

    # Track advice usage
    if mode == "ADVICE":
        increment_advice_count()
        state["advice_count"] = get_advice_count()
        print(f"📊  Advice count: {state['advice_count']}")


if __name__ == "__main__":
    main()
