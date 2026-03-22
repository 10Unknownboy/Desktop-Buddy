"""
main.py - Entry point for Desktop Buddy.

Runs a simple synchronous loop:
    listen → transcribe → decide → respond → speak

Press Ctrl+C to exit gracefully.
"""

import os

from src.audio_input import record_audio
from src.stt import transcribe
from src.decision_engine import decide
from src.response_engine import generate_response
from src.tts import speak


def main() -> None:
    """Run the assistant loop."""
    print("=" * 50)
    print("  🤖  Desktop Buddy – Online")
    print("=" * 50)
    print("  Press Ctrl+C to exit.\n")

    try:
        while True:
            # 1. Record audio from microphone
            audio_path = record_audio()

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
