"""
tts.py - Text-to-Speech module.

Uses the TTS.ai REST API (model: kokoro) to synthesize speech and
plays the resulting audio through the default output device.
"""

import tempfile

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
            TTS_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        # Write binary audio to a temp WAV file
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(response.content)
        tmp.close()

        # Read WAV and play through default output device
        sample_rate, audio_data = wavfile.read(tmp.name)
        sd.play(audio_data, samplerate=sample_rate)
        sd.wait()  # block until playback finishes

        print("🔊  Playback complete.")

    except requests.RequestException as e:
        print(f"[ERROR] TTS.ai request failed: {e}")
    except Exception as e:
        print(f"[ERROR] Text-to-Speech playback failed: {e}")
