"""
tts.py - Clean Edge TTS implementation using edge-tts.
"""

import asyncio
import os
import tempfile
import pygame
import edge_tts

TTS_VOICE = "en-IN-PrabhatNeural"
is_speaking = False

pygame.mixer.init()

def speak(text: str) -> bool:
    """Generates audio via edge_tts and plays it."""
    global is_speaking
    if not text:
        return True

    is_speaking = True
    temp_file = ""
    try:
        fd, temp_file = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        asyncio.run(edge_tts.Communicate(text, TTS_VOICE).save(temp_file))
        
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy() and is_speaking:
            pygame.time.Clock().tick(10)
            
        return True
    except Exception as e:
        print(f"[TTS Error] {e}")
        return True
    finally:
        is_speaking = False
        pygame.mixer.music.unload()
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
    return True

def stop_speaking() -> None:
    """Stops playback instantly."""
    global is_speaking
    is_speaking = False
    pygame.mixer.music.stop()
