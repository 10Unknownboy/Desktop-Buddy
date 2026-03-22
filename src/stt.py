"""
stt.py - Speech-to-Text module.

Uses the Groq API with the Whisper model to transcribe audio files.
Returns both the transcribed text and a confidence score.
"""

from groq import Groq

from src.config import GROQ_API_KEY

# ---------------------------------------------------------------------------
# Groq client (initialised once at module level)
# ---------------------------------------------------------------------------
_client = Groq(api_key=GROQ_API_KEY)

# Model to use for transcription
MODEL = "whisper-large-v3-turbo"


def transcribe(audio_path: str) -> dict:
    """
    Transcribe an audio file to text using Groq's Whisper API.

    Args:
        audio_path: Path to a WAV audio file.

    Returns:
        A dict with keys:
            - ``text``  (str):   The transcribed text, or empty on failure.
            - ``confidence`` (float): 0.0–1.0 estimate of transcription
              quality derived from Whisper's avg_logprob.
    """
    print("📝  Transcribing audio …")

    try:
        with open(audio_path, "rb") as audio_file:
            result = _client.audio.transcriptions.create(
                model=MODEL,
                file=audio_file,
                language="en",
                response_format="verbose_json",
            )

        # Extract text
        text = getattr(result, "text", "") or ""
        text = text.strip()

        # Extract confidence from avg_logprob of segments
        # avg_logprob is negative; closer to 0 = higher confidence
        confidence = _estimate_confidence(result)

        print(f'📝  Transcription: "{text}"  (confidence: {confidence:.2f})')
        return {"text": text, "confidence": confidence}

    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return {"text": "", "confidence": 0.0}


def _estimate_confidence(result) -> float:
    """
    Convert Whisper's avg_logprob into a 0.0–1.0 confidence score.

    Whisper log-probs are typically in the range [-1.0, 0.0].
    We clamp and linearly map:
        -1.0  →  0.0  (low confidence)
         0.0  →  1.0  (high confidence)
    """
    try:
        segments = getattr(result, "segments", None) or []
        if not segments:
            return 0.5  # neutral fallback when no segments available

        avg_logprobs = [
            seg.get("avg_logprob", -0.5) if isinstance(seg, dict)
            else getattr(seg, "avg_logprob", -0.5)
            for seg in segments
        ]
        mean_logprob = sum(avg_logprobs) / len(avg_logprobs)

        # Clamp to [-1.0, 0.0] then map to [0.0, 1.0]
        clamped = max(-1.0, min(0.0, mean_logprob))
        return round(1.0 + clamped, 3)

    except Exception:
        return 0.5
