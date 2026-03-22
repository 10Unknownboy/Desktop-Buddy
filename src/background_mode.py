"""
background_mode.py - Background Listening / Ambient Mode.

Plays soft background audio when the system is idle for an extended
period.  Stops instantly when user speech is detected.

Trigger conditions:
    * No active conversation for ~20 minutes
    * Engagement score is low
    * No heavy apps running (CPU < 60%)

Audio:
    * Plays from local WAV files in data/ambient/
    * Very low volume (10–15% of normal)
    * Loops until interrupted
"""

import os
import time
import threading

import numpy as np
import sounddevice as sd

from src.config import DATA_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IDLE_THRESHOLD = 20 * 60      # 20 minutes of no interaction
VOLUME_SCALE = 0.12           # 12% volume (very quiet)
CPU_THRESHOLD = 60.0          # don't play if CPU is above this

AMBIENT_DIR = DATA_DIR / "ambient"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_is_playing: bool = False
_play_thread: threading.Thread | None = None
_stop_event = threading.Event()
_last_interaction_ts: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_background(last_interaction_ts: float = 0.0) -> None:
    """Initialise background mode with current interaction timestamp."""
    global _last_interaction_ts
    _last_interaction_ts = last_interaction_ts or time.time()
    # Create ambient directory if it doesn't exist
    AMBIENT_DIR.mkdir(parents=True, exist_ok=True)


def update_last_interaction() -> None:
    """Call this whenever the user interacts."""
    global _last_interaction_ts
    _last_interaction_ts = time.time()


def is_idle() -> bool:
    """Return True if the user has been idle for >= IDLE_THRESHOLD."""
    return time.time() - _last_interaction_ts >= IDLE_THRESHOLD


def is_playing() -> bool:
    """Return True if background audio is currently playing."""
    return _is_playing


def check_and_play(engagement_score: int) -> bool:
    """
    Check if conditions are met and start background audio.

    Args:
        engagement_score: Current engagement level (0–10).

    Returns:
        True if background audio was started.
    """
    if _is_playing:
        return False

    if not is_idle():
        return False

    # Only play when engagement is low
    if engagement_score > 3:
        return False

    # Check CPU isn't too high
    try:
        import psutil
        if psutil.cpu_percent(interval=0) > CPU_THRESHOLD:
            return False
    except ImportError:
        pass

    # Check if we have any ambient files
    ambient_files = _get_ambient_files()
    if not ambient_files:
        return False

    play_background_audio(ambient_files[0])
    return True


def play_background_audio(filepath: str) -> None:
    """
    Start playing background audio in a separate thread.

    Audio is played at very low volume and loops until stopped.
    """
    global _is_playing, _play_thread

    if _is_playing:
        return

    _stop_event.clear()
    _play_thread = threading.Thread(
        target=_play_loop,
        args=(filepath,),
        daemon=True,
    )
    _play_thread.start()
    print(f"🎵  Background audio started (very low volume)")


def stop_background_audio() -> None:
    """Immediately stop any background audio."""
    global _is_playing
    _stop_event.set()
    sd.stop()
    _is_playing = False
    print("🔇  Background audio stopped.")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _play_loop(filepath: str) -> None:
    """Play audio at low volume, looping until stop event is set."""
    global _is_playing

    try:
        from scipy.io import wavfile
        sample_rate, data = wavfile.read(filepath)
    except Exception as e:
        print(f"[ERROR] Could not read ambient file: {e}")
        return

    # Scale volume down
    if data.dtype == np.int16:
        data = (data.astype(np.float32) * VOLUME_SCALE).astype(np.int16)
    else:
        data = (data * VOLUME_SCALE).astype(data.dtype)

    _is_playing = True

    while not _stop_event.is_set():
        try:
            sd.play(data, samplerate=sample_rate)
            # Poll for stop event instead of sd.wait()
            while sd.get_stream().active and not _stop_event.is_set():
                time.sleep(0.1)
            if _stop_event.is_set():
                sd.stop()
                break
        except Exception:
            break

    _is_playing = False


def _get_ambient_files() -> list[str]:
    """Return list of WAV files in the ambient directory."""
    if not AMBIENT_DIR.exists():
        return []
    return [
        str(AMBIENT_DIR / f)
        for f in os.listdir(AMBIENT_DIR)
        if f.lower().endswith((".wav", ".mp3"))
    ]
