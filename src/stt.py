"""
stt.py - Speech-to-Text module.

Uses the Groq API with the Whisper model to transcribe audio files.
"""

from groq import Groq

from src.config import GROQ_API_KEY

# ---------------------------------------------------------------------------
# Groq client (initialised once at module level)
# ---------------------------------------------------------------------------
_client = Groq(api_key=GROQ_API_KEY)

# Model to use for transcription
MODEL = "whisper-large-v3-turbo"


def transcribe(audio_path: str) -> str:
    """
    Transcribe an audio file to text using Groq's Whisper API.

    Args:
        audio_path: Path to a WAV audio file.

    Returns:
        The transcribed text, or an empty string on failure.
    """
    print("📝  Transcribing audio …")

    try:
        with open(audio_path, "rb") as audio_file:
            transcription = _client.audio.transcriptions.create(
                model=MODEL,
                file=audio_file,
                language="en",
                response_format="text",
            )

        text = transcription.strip() if isinstance(transcription, str) else str(transcription).strip()
        print(f"📝  Transcription: \"{text}\"")
        return text

    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return ""
