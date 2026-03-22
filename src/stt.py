"""
stt.py - Speech-to-Text module with retry logic.

Uses the Groq API with the Whisper model to transcribe audio files.
Returns both the transcribed text and a confidence score.

Failsafes:
    * Retries up to 2 times on failure
    * Returns empty result gracefully (never crashes)
"""

import time

from groq import Groq

from src.config import GROQ_API_KEY
from src.logger import get_logger

log = get_logger("stt")

# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------
_client = Groq(api_key=GROQ_API_KEY)
MODEL = "whisper-large-v3-turbo"

# Retry settings
MAX_RETRIES = 2
RETRY_DELAY = 1.0   # seconds between retries


def transcribe(audio_path: str) -> dict:
    """
    Transcribe an audio file with retry logic.

    Returns:
        {"text": str, "confidence": float}
        Returns empty text on total failure.
    """
    log.info("📝  Transcribing audio …")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(audio_path, "rb") as audio_file:
                result = _client.audio.transcriptions.create(
                    model=MODEL,
                    file=audio_file,
                    language="en",
                    response_format="verbose_json",
                )

            text = (getattr(result, "text", "") or "").strip()
            confidence = _estimate_confidence(result)

            log.info(f'📝  Transcription: "{text}"  (confidence: {confidence:.2f})')
            return {"text": text, "confidence": confidence}

        except Exception as e:
            log.warning(f"[STT] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    log.error("[STT] All retries exhausted. Returning empty result.")
    return {"text": "", "confidence": 0.0}


def _estimate_confidence(result) -> float:
    """Convert Whisper's avg_logprob into 0.0–1.0 confidence."""
    try:
        segments = getattr(result, "segments", None) or []
        if not segments:
            return 0.5

        avg_logprobs = [
            seg.get("avg_logprob", -0.5) if isinstance(seg, dict)
            else getattr(seg, "avg_logprob", -0.5)
            for seg in segments
        ]
        mean_logprob = sum(avg_logprobs) / len(avg_logprobs)
        clamped = max(-1.0, min(0.0, mean_logprob))
        return round(1.0 + clamped, 3)
    except Exception:
        return 0.5
