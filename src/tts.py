"""
tts.py - Text-to-Speech module with interruption support.

Uses the TTS.ai REST API (model: kokoro) to synthesize speech.
Supports interruptible playback via the ``speak_interruptible()``
function which polls for user speech during playback.

State management:
    is_speaking    – True while audio is playing
    _audio_data    – full audio array (for resume support)
    _sample_rate   – sample rate of current audio
    _stop_position – sample index where playback was interrupted
"""

import tempfile
import time

import numpy as np
import requests
import sounddevice as sd
from scipy.io import wavfile

from src.config import TTS_AI_API_KEY

# ---------------------------------------------------------------------------
# TTS.ai settings
# ---------------------------------------------------------------------------
TTS_API_URL = "https://api.tts.ai/v1/tts/"
TTS_MODEL = "kokoro"
TTS_VOICE = "af_bella"
TTS_FORMAT = "wav"

# ---------------------------------------------------------------------------
# Interruption detection settings
# ---------------------------------------------------------------------------
INTERRUPT_CHECK_INTERVAL = 0.05   # check mic every 50 ms during playback
INTERRUPT_RMS_THRESHOLD = 400     # slightly higher than silence threshold to avoid feedback
INTERRUPT_CHUNK_SAMPLES = 800     # 50 ms at 16 kHz
INTERRUPT_SAMPLE_RATE = 16_000

# ---------------------------------------------------------------------------
# Speaking state
# ---------------------------------------------------------------------------
is_speaking: bool = False

_audio_data: np.ndarray | None = None
_sample_rate: int = 0
_stop_position: int = 0   # sample index where we stopped
_current_text: str = ""


# ---------------------------------------------------------------------------
# Synthesis (shared between speak variants)
# ---------------------------------------------------------------------------

def _synthesize(text: str) -> tuple[np.ndarray, int] | None:
    """
    Call TTS.ai and return (audio_array, sample_rate) or None on failure.
    """
    print("🔊  Synthesizing speech …")

    try:
        headers = {
            "Authorization": f"Bearer {TTS_AI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": TTS_MODEL,
            "text": text,
            "voice": TTS_VOICE,
            "format": TTS_FORMAT,
        }

        response = requests.post(
            TTS_API_URL, headers=headers, json=payload, timeout=30,
        )
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(response.content)
        tmp.close()

        sr, data = wavfile.read(tmp.name)
        return data, sr

    except requests.RequestException as e:
        print(f"[ERROR] TTS.ai request failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] TTS synthesis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Simple blocking speak (used for short reactions / presence prompts)
# ---------------------------------------------------------------------------

def speak(text: str) -> None:
    """
    Synthesize and play audio (blocking, NOT interruptible).

    Use for micro-reactions and short phrases where interruption
    detection is unnecessary.
    """
    global is_speaking
    if not text:
        return

    result = _synthesize(text)
    if result is None:
        return

    data, sr = result
    is_speaking = True
    try:
        sd.play(data, samplerate=sr)
        sd.wait()
        print("🔊  Playback complete.")
    except Exception as e:
        print(f"[ERROR] Playback failed: {e}")
    finally:
        is_speaking = False


# ---------------------------------------------------------------------------
# Interruptible speak (used for full responses)
# ---------------------------------------------------------------------------

def speak_interruptible(text: str) -> bool:
    """
    Synthesize and play audio with interruption detection.

    Polls the microphone during playback.  If user speech is detected,
    playback is stopped instantly and state is saved for potential resume.

    Args:
        text: The text to speak.

    Returns:
        True if playback completed normally.
        False if playback was interrupted by user speech.
    """
    global is_speaking, _audio_data, _sample_rate, _stop_position, _current_text

    if not text:
        return True

    result = _synthesize(text)
    if result is None:
        return True

    data, sr = result

    # Save state for resume
    _audio_data = data
    _sample_rate = sr
    _stop_position = 0
    _current_text = text
    is_speaking = True

    try:
        sd.play(data, samplerate=sr)

        # Poll mic while playing
        total_samples = len(data)
        start_time = time.time()

        with sd.InputStream(
            samplerate=INTERRUPT_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=INTERRUPT_CHUNK_SAMPLES,
        ) as mic:
            while sd.get_stream().active:
                chunk, _ = mic.read(INTERRUPT_CHUNK_SAMPLES)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

                if rms > INTERRUPT_RMS_THRESHOLD:
                    # User is speaking — interrupt!
                    elapsed = time.time() - start_time
                    _stop_position = int(elapsed * sr)
                    sd.stop()
                    is_speaking = False
                    print("⚡  Interrupted by user!")
                    return False

                time.sleep(INTERRUPT_CHECK_INTERVAL)

        print("🔊  Playback complete.")
        is_speaking = False
        return True

    except Exception as e:
        print(f"[ERROR] Interruptible playback failed: {e}")
        is_speaking = False
        return True


# ---------------------------------------------------------------------------
# Stop & Resume
# ---------------------------------------------------------------------------

def stop_speaking() -> None:
    """Immediately stop any current playback."""
    global is_speaking
    sd.stop()
    is_speaking = False
    print("🔇  Speech stopped.")


def resume_speaking() -> bool:
    """
    Resume playback from where it was interrupted.

    Returns:
        True if resumed and completed, False if interrupted again,
        True if nothing to resume.
    """
    global is_speaking, _stop_position

    if _audio_data is None or _stop_position <= 0:
        return True

    remaining = _audio_data[_stop_position:]
    if len(remaining) == 0:
        return True

    print(f"🔊  Resuming from {_stop_position / _sample_rate:.1f}s …")
    is_speaking = True

    try:
        sd.play(remaining, samplerate=_sample_rate)

        start_time = time.time()

        with sd.InputStream(
            samplerate=INTERRUPT_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=INTERRUPT_CHUNK_SAMPLES,
        ) as mic:
            while sd.get_stream().active:
                chunk, _ = mic.read(INTERRUPT_CHUNK_SAMPLES)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

                if rms > INTERRUPT_RMS_THRESHOLD:
                    elapsed = time.time() - start_time
                    _stop_position += int(elapsed * _sample_rate)
                    sd.stop()
                    is_speaking = False
                    print("⚡  Interrupted again!")
                    return False

                time.sleep(INTERRUPT_CHECK_INTERVAL)

        print("🔊  Resume playback complete.")
        is_speaking = False
        _stop_position = 0
        return True

    except Exception as e:
        print(f"[ERROR] Resume playback failed: {e}")
        is_speaking = False
        return True


def get_speaking_state() -> dict:
    """Return current speaking state for the interruption handler."""
    return {
        "is_speaking": is_speaking,
        "current_text": _current_text,
        "stop_position": _stop_position,
        "has_remaining": (
            _audio_data is not None
            and _stop_position > 0
            and _stop_position < len(_audio_data) if _audio_data is not None else False
        ),
    }
