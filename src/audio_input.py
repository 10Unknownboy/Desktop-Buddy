"""
audio_input.py - Microphone recording module.

Records audio from the default input device and saves it as a
temporary WAV file for downstream processing.
"""

import tempfile

import numpy as np
import sounddevice as sd
from scipy.io import wavfile


# ---------------------------------------------------------------------------
# Default recording settings (optimised for speech on low-end hardware)
# ---------------------------------------------------------------------------
DEFAULT_SAMPLE_RATE = 16_000   # 16 kHz – sufficient for speech recognition
DEFAULT_DURATION = 5           # seconds
DEFAULT_CHANNELS = 1           # mono


def record_audio(
    duration: int = DEFAULT_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
) -> str:
    """
    Record audio from the default microphone.

    Args:
        duration:    Recording length in seconds.
        sample_rate: Sample rate in Hz.
        channels:    Number of audio channels (1 = mono).

    Returns:
        Path to the temporary WAV file containing the recording.
    """
    print(f"🎙️  Recording for {duration} seconds …")

    audio_data: np.ndarray = sd.rec(
        frames=int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
    )
    sd.wait()  # block until recording finishes

    print("✅  Recording complete.")

    # Save to a temporary WAV file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(tmp.name, sample_rate, audio_data)
    tmp.close()

    return tmp.name
