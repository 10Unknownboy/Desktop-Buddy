"""
tts.py - Text-to-Speech with async polling and interruption support.

Uses the TTS.ai REST API (Asynchronous Job System).
Correctly handles queued jobs, polls for completion, and downloads audio.

Flow:
    1. request_tts(text)  → returns job_id/uuid
    2. poll_tts(job_id)     → returns result_url
    3. download_audio(url) → returns audio binary
    4. play_audio(data)    → handles playback (internal or external)

Failsafes:
    * 10s timeout for polling
    * Retry logic for requests
    * Skips voice on failure (never crashes main loop)
"""

import base64
import json
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

# Polling Settings
POLL_INTERVAL = 1.5   # seconds
MAX_POLL_TIME = 10.0   # seconds

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
# Core TTS Flow Functions
# ---------------------------------------------------------------------------

def request_tts(text: str) -> str | dict | None:
    """
    Step 1: Send TTS request to create a job.
    Returns: job_id/uuid (str) or full JSON response (dict) if already completed.
    """
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
            "audioConfig": {"audioEncoding": "LINEAR16"}
        }
        
        resp = requests.post(TTS_API_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        # If already completed (cached), return the whole dict
        if data.get("status") == "completed":
            log.info(f"[TTS] Job cached and completed immediately: {data.get('uuid')}")
            return data
            
        uuid = data.get("uuid") or data.get("job_id")
        log.info(f"[TTS] Job created: {uuid} (status: {data.get('status')})")
        return uuid

    except Exception as e:
        log.error(f"[TTS] Request failed: {e}")
        return None


def poll_tts(job_uuid: str) -> str | None:
    """
    Step 2: Poll for job completion.
    Returns: result_url (str) if completed, or None on timeout/failure.
    """
    start_time = time.time()
    headers = {"Authorization": f"Bearer {TTS_AI_API_KEY}"}
    
    # Polling URL is typically the base URL + UUID for status
    poll_url = f"{TTS_API_URL}{job_uuid}"

    log.info(f"[TTS] Polling status for job: {job_uuid} …")

    while time.time() - start_time < MAX_POLL_TIME:
        try:
            resp = requests.get(poll_url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            status = data.get("status", "unknown")
            log.info(f"[TTS] Status: {status}")

            if status == "completed":
                url = data.get("result_url") or data.get("url")
                if url:
                    log.info(f"[TTS] Result URL found: {url}")
                    return url
                log.error(f"[TTS] Job completed but URL missing: {data}")
                return None
            
            # Use small sleep between polls
            time.sleep(POLL_INTERVAL)
            
        except Exception as e:
            log.warning(f"[TTS] Polling error: {e}")
            time.sleep(POLL_INTERVAL)

    log.error("[TTS] Polling timed out — skipping audio.")
    return None


def download_audio(url: str) -> bytes | None:
    """
    Step 3: Download the actual audio file.
    Returns: Audio data bytes or None.
    """
    try:
        log.info(f"[TTS] Downloading audio from: {url}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        
        content = resp.content
        header_peek = content[:10]
        log.info(f"[TTS] Audio header peek: {header_peek}")

        if not content.startswith(b'RIFF'):
            log.error(f"[TTS] Downloaded file is not WAV. Header: {header_peek}")
            return None
            
        return content

    except Exception as e:
        log.error(f"[TTS] Download failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Integrated Synthesis
# ---------------------------------------------------------------------------

def _synthesize(text: str) -> tuple[np.ndarray, int] | None:
    """Full async synthesis flow: Request -> Poll -> Download -> Load."""
    
    # Step 1: Request
    result = request_tts(text)
    if not result:
        return None

    # Step 2: Extract URL (handle immediate completion or polling)
    result_url = None
    if isinstance(result, dict):
        # Already completed
        result_url = result.get("result_url") or result.get("url")
    else:
        # Need to poll
        result_url = poll_tts(result)

    if not result_url:
        return None

    # Step 3: Download
    audio_bytes = download_audio(result_url)
    if not audio_bytes:
        return None

    # Step 4: Load for playback
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        sr, data = wavfile.read(tmp.name)
        return data, sr
    except Exception as e:
        log.error(f"[TTS] Error loading audio data: {e}")
        return None


# ---------------------------------------------------------------------------
# Playback API
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
        return True

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
