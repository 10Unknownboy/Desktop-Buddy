"""
audio_input.py - Advanced microphone recording module.

Provides two recording modes:
    1. listen_continuous() – Always-on listener with two-stage silence
       detection and micro-reaction support.
    2. record_audio_fixed() – Legacy fixed-duration recording (kept for
       backward compatibility).

Silence Detection Logic (RMS-based):
    Every 100 ms chunk of audio is measured for loudness via RMS
    (root-mean-square amplitude).  When the RMS drops below
    SILENCE_THRESHOLD the system starts accumulating silence time:

        ≥ 1.0 s  →  Stage 1:  fire a micro-reaction ("hmm…")
        ≥ 3.0 s  →  Stage 2:  finalize the buffer, save WAV, return

    Any speech chunk resets both timers.
"""

import tempfile
import time

import numpy as np
import sounddevice as sd
from scipy.io import wavfile


# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
SAMPLE_RATE: int = 16_000          # 16 kHz – good for speech, low CPU
CHANNELS: int = 1                  # mono
CHUNK_DURATION: float = 0.1        # 100 ms per read

SILENCE_THRESHOLD: int = 300       # RMS amplitude below this → silence
STAGE_1_SILENCE: float = 1.0       # seconds of silence → micro-reaction
STAGE_2_SILENCE: float = 3.0       # seconds of silence → finalize input
MIN_SPEECH_DURATION: float = 0.3   # ignore noise bursts shorter than this

MICRO_REACTION_DELAY: float = 0.4  # slight pause before reacting (0.3–0.5 s)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_rms(chunk: np.ndarray) -> float:
    """Return the root-mean-square amplitude of an int16 audio chunk."""
    return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))


def _save_buffer_to_wav(
    buffer: list[np.ndarray],
    sample_rate: int = SAMPLE_RATE,
) -> str:
    """Concatenate buffered chunks and write to a temporary WAV file.

    Returns:
        Absolute path to the temporary WAV file.
    """
    audio = np.concatenate(buffer, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(tmp.name, sample_rate, audio)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def listen_continuous(
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
    on_micro_reaction=None,
) -> str:
    """
    Listen continuously until the user finishes speaking.

    The microphone stays open.  Audio chunks are buffered while speech
    is detected.  Silence triggers a two-stage flow:

        Stage 1 (≥1 s silence) → call *on_micro_reaction* callback
        Stage 2 (≥3 s silence) → save buffer to WAV and return path

    Args:
        sample_rate:        Sample rate in Hz.
        channels:           Number of audio channels (1 = mono).
        on_micro_reaction:  Optional callable invoked at Stage 1 silence.

    Returns:
        Path to a temporary WAV file containing the captured speech.
        Returns an empty string if no meaningful speech was recorded.
    """
    chunk_samples = int(CHUNK_DURATION * sample_rate)

    buffer: list[np.ndarray] = []
    speech_started = False
    speech_time: float = 0.0       # accumulated duration of speech chunks
    silence_time: float = 0.0      # accumulated duration of silence
    reaction_fired = False         # ensure micro-reaction fires only once

    print("👂  Listening … (speak whenever you're ready)")

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            blocksize=chunk_samples,
        ) as stream:
            while True:
                chunk, overflowed = stream.read(chunk_samples)
                rms = _compute_rms(chunk)

                if rms > SILENCE_THRESHOLD:
                    # ── Speech detected ──────────────────────────
                    if not speech_started:
                        speech_started = True
                        print("🗣️  Speech detected …")

                    buffer.append(chunk.copy())
                    speech_time += CHUNK_DURATION
                    silence_time = 0.0
                    reaction_fired = False  # allow re-reaction if user pauses again

                elif speech_started:
                    # ── Silence after speech ─────────────────────
                    buffer.append(chunk.copy())   # keep tail silence in buffer
                    silence_time += CHUNK_DURATION

                    # Stage 1 – micro-reaction
                    if (
                        silence_time >= STAGE_1_SILENCE
                        and not reaction_fired
                        and on_micro_reaction is not None
                    ):
                        time.sleep(MICRO_REACTION_DELAY)
                        on_micro_reaction()
                        reaction_fired = True

                    # Stage 2 – finalize
                    if silence_time >= STAGE_2_SILENCE:
                        # Ignore very short bursts of noise
                        if speech_time < MIN_SPEECH_DURATION:
                            print("⚠️  Too short – ignoring noise burst.")
                            buffer.clear()
                            speech_started = False
                            speech_time = 0.0
                            silence_time = 0.0
                            reaction_fired = False
                            continue

                        print("✅  Speech finalized.")
                        return _save_buffer_to_wav(buffer, sample_rate)

                # If no speech started yet, just keep looping (mic stays on)

    except Exception as e:
        print(f"[ERROR] Listening failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Legacy fixed-duration recorder (backward compatibility)
# ---------------------------------------------------------------------------

def record_audio_fixed(
    duration: int = 5,
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
) -> str:
    """
    Record a fixed duration of audio (original behaviour).

    Args:
        duration:    Recording length in seconds.
        sample_rate: Sample rate in Hz.
        channels:    Number of audio channels.

    Returns:
        Path to the temporary WAV file.
    """
    print(f"🎙️  Recording for {duration} seconds …")

    audio_data: np.ndarray = sd.rec(
        frames=int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    )
    sd.wait()

    print("✅  Recording complete.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(tmp.name, sample_rate, audio_data)
    tmp.close()

    return tmp.name
