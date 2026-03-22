"""
main.py - Entry point for Desktop Buddy.

Runs an always-on listening loop with decision-engine routing:
    listen → transcribe → decide → route → respond/react → speak

The decision engine controls whether a full LLM response is generated,
a micro-reaction is played, or the input is silently ignored.

Press Ctrl+C to exit gracefully.
"""

import os

from src.audio_input import listen_continuous
from src.stt import transcribe
from src.decision_engine import decide, update_context
from src.response_engine import generate_response
from src.tts import speak
from src.micro_reaction import play_micro_reaction, play_directed_reaction


# ---------------------------------------------------------------------------
# Session state (persists across turns within a single run)
# ---------------------------------------------------------------------------
_state: dict = {
    "advice_count": 0,
    "current_mode": None,
}


def main() -> None:
    """Run the assistant loop with decision-engine routing."""
    print("=" * 50)
    print("  🤖  Desktop Buddy – Online")
    print("=" * 50)
    print("  Always-on listening · Decision Engine active")
    print("  Speak naturally – I'll respond when you pause.")
    print("  Press Ctrl+C to exit.\n")

    try:
        while True:
            # 1. Listen until speech + final silence detected
            audio_path = listen_continuous(
                on_micro_reaction=play_micro_reaction,
            )

            # Skip if no usable audio was captured
            if not audio_path:
                print("⚠️  No audio captured. Listening again …\n")
                continue

            # 2. Transcribe speech to text (now returns dict)
            stt_result = transcribe(audio_path)
            text = stt_result["text"]
            confidence = stt_result["confidence"]

            # Clean up the temporary audio file
            try:
                os.remove(audio_path)
            except OSError:
                pass

            # Skip empty transcriptions
            if not text:
                print("⚠️  No speech detected. Listening again …\n")
                continue

            # 3. Run through the decision engine
            instruction = decide(text, confidence, _state)

            # Update session state
            _state["current_mode"] = instruction["mode"]

            # 4. Route based on decision
            _handle_instruction(instruction)

            print()  # visual separator between turns

    except KeyboardInterrupt:
        print("\n\n👋  Desktop Buddy shutting down. Goodbye!")


def _handle_instruction(instruction: dict) -> None:
    """
    Route the instruction to the appropriate action.

    Modes:
        LISTEN   → play directed micro-reaction only
        IGNORE   → do nothing
        REDIRECT → speak redirect message (no LLM)
        SHORT_REPLY / ADVICE → generate + speak full response
    """
    mode = instruction.get("mode", "LISTEN")
    reaction_type = instruction.get("micro_reaction", "none")

    # ── IGNORE ────────────────────────────────────────────────
    if mode == "IGNORE":
        print("🤫  Ignoring input.")
        return

    # ── LISTEN (no full response, just react) ─────────────────
    if mode == "LISTEN":
        play_directed_reaction(reaction_type)
        return

    # ── REDIRECT / SHORT_REPLY / ADVICE → generate response ──
    response = generate_response(instruction)

    if response:
        speak(response)
        update_context("assistant", response)

    # Track advice usage
    if mode == "ADVICE":
        _state["advice_count"] = _state.get("advice_count", 0) + 1
        print(f"📊  Advice count: {_state['advice_count']}")


if __name__ == "__main__":
    main()
