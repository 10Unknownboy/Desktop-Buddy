"""
tts.py - Text-to-Speech module.

Uses Google Cloud Text-to-Speech to synthesize speech and plays the
resulting audio through the default output device.
"""

import io
import tempfile

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from google.cloud import texttospeech

# ---------------------------------------------------------------------------
# Google Cloud TTS client (initialised once)
# GOOGLE_APPLICATION_CREDENTIALS is set in config.py at import time.
# ---------------------------------------------------------------------------
import src.config  # noqa: F401  – ensures env var is set before client init

_client = texttospeech.TextToSpeechClient()

# Voice configuration
_voice = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
)

# Audio output configuration – LINEAR16 (WAV) for easy playback
_audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=24000,
)


def speak(text: str) -> None:
    """
    Convert text to speech and play it through the speakers.

    Args:
        text: The text to synthesize and speak aloud.
    """
    if not text:
        return

    print("🔊  Synthesizing speech …")

    try:
        synthesis_input = texttospeech.SynthesisInput(text=text)

        response = _client.synthesize_speech(
            input=synthesis_input,
            voice=_voice,
            audio_config=_audio_config,
        )

        # The response audio_content is a LINEAR16 WAV byte string.
        # Write to a temp file so scipy can read it back.
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(response.audio_content)
        tmp.close()

        # Read WAV and play through default output device
        sample_rate, audio_data = wavfile.read(tmp.name)
        sd.play(audio_data, samplerate=sample_rate)
        sd.wait()  # block until playback finishes

        print("🔊  Playback complete.")

    except Exception as e:
        print(f"[ERROR] Text-to-Speech failed: {e}")
