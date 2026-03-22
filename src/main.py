"""
main.py - Entry point for Desktop Buddy.

Runs an always-on listening loop:
    listen continuously → transcribe → decide → respond → speak

The microphone stays open between turns.
Press Ctrl+C to exit gracefully.
"""

import os

from src.audio_input import listen_continuous
from src.stt import transcribe
from src.decision_engine import decide
from src.response_engine import generate_response
from src.tts import speak
from src.micro_reaction import play_micro_reaction


def main() -> None:
    """Run the assistant loop with continuous listening."""
    print("=" * 50)
    print("  🤖  Desktop Buddy – Online")
    print("=" * 50)
    print("  Always-on listening mode.")
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

            # 2. Transcribe speech to text
            text = transcribe(audio_path)

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
            instruction = decide(text)

            # 4. Generate a response
            response = generate_response(instruction)

            # 5. Speak the response
            speak(response)

            print()  # visual separator between turns

    except KeyboardInterrupt:
        print("\n\n👋  Desktop Buddy shutting down. Goodbye!")


if __name__ == "__main__":
    main()
