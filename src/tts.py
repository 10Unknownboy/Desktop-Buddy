"""
tts.py - Text-to-Speech with interruption support and failsafes.

Uses the TTS.ai REST API.  Supports interruptible playback.

Failsafes:
    * Retry up to 2 times on API failure
    * On total failure: log text to console (skip voice)
    * Never crashes the main loop
"""

import tempfile
import time

import numpy as np
import requests
import sounddevice as sd
from scipy.io import wavfile

from src.config import TTS_AI_API_KEY
from src.logger import get_logger

log = get_logger("tts")

# ---------------------------------------------------------------------------
# TTS.ai settings
# ---------------------------------------------------------------------------
TTS_API_URL = "https://api.tts.ai/v1/tts/"
TTS_MODEL = "kokoro"
TTS_VOICE = "af_bella"
TTS_FORMAT = "wav"

# Retry
MAX_RETRIES = 2
RETRY_DELAY = 0.5

# Interruption detection
INTERRUPT_CHECK_INTERVAL = 0.05
INTERRUPT_RMS_THRESHOLD = 400
INTERRUPT_CHUNK_SAMPLES = 800
INTERRUPT_SAMPLE_RATE = 16_000

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
is_speaking: bool = False
_audio_data: np.ndarray | None = None
_sample_rate: int = 0
_stop_position: int = 0
_current_text: str = ""


# ---------------------------------------------------------------------------
# Synthesis with retry
# ---------------------------------------------------------------------------

def _synthesize(text: str) -> tuple[np.ndarray, int] | None:
    """Call TTS.ai with retry. Returns (audio, sample_rate) or None."""
    for attempt in range(1, MAX_RETRIES + 1):
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
            resp = requests.post(
                TTS_API_URL, headers=headers, json=payload, timeout=30,
            )
            resp.raise_for_status()

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(resp.content)
            tmp.close()

            sr, data = wavfile.read(tmp.name)
            return data, sr

        except Exception as e:
            log.warning(f"[TTS] Attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    log.error(f'[TTS] All retries failed. Text was: "{text}"')
    return None


# ---------------------------------------------------------------------------
# Blocking speak (for reactions / short phrases)
# ---------------------------------------------------------------------------

def speak(text: str) -> None:
    """Synthesize and play audio (blocking, NOT interruptible)."""
    global is_speaking
    if not text:
        return

    log.info("🔊  Synthesizing speech …")
    result = _synthesize(text)
    if result is None:
        log.warning(f'🔊  TTS failed — text: "{text}"')
        return

    data, sr = result
    is_speaking = True
    try:
        sd.play(data, samplerate=sr)
        sd.wait()
        log.info("🔊  Playback complete.")
    except Exception as e:
        log.error(f"[TTS] Playback failed: {e}")
    finally:
        is_speaking = False


# ---------------------------------------------------------------------------
# Interruptible speak
# ---------------------------------------------------------------------------

def speak_interruptible(text: str) -> bool:
    """
    Speak with interrupt detection. Returns True if completed, False if interrupted.
    """
    global is_speaking, _audio_data, _sample_rate, _stop_position, _current_text

    if not text:
        return True

    log.info("🔊  Synthesizing speech …")
    result = _synthesize(text)
    if result is None:
        log.warning(f'🔊  TTS failed — text: "{text}"')
        return True  # treat as "completed" so main loop continues

    data, sr = result
    _audio_data = data
    _sample_rate = sr
    _stop_position = 0
    _current_text = text
    is_speaking = True

    try:
        sd.play(data, samplerate=sr)
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
                    _stop_position = int(elapsed * sr)
                    sd.stop()
                    is_speaking = False
                    log.info("⚡  Interrupted by user!")
                    return False

                time.sleep(INTERRUPT_CHECK_INTERVAL)

        log.info("🔊  Playback complete.")
        is_speaking = False
        return True

    except Exception as e:
        log.error(f"[TTS] Interruptible playback failed: {e}")
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


def resume_speaking() -> bool:
    """Resume from where interrupted. Returns True if completed."""
    global is_speaking, _stop_position

    if _audio_data is None or _stop_position <= 0:
        return True

    remaining = _audio_data[_stop_position:]
    if len(remaining) == 0:
        return True

    log.info(f"🔊  Resuming from {_stop_position / _sample_rate:.1f}s …")
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
                    log.info("⚡  Interrupted again!")
                    return False

                time.sleep(INTERRUPT_CHECK_INTERVAL)

        log.info("🔊  Resume playback complete.")
        is_speaking = False
        _stop_position = 0
        return True

    except Exception as e:
        log.error(f"[TTS] Resume failed: {e}")
        is_speaking = False
        return True


def get_speaking_state() -> dict:
    """Return current speaking state."""
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
