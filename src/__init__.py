"""
Desktop Buddy - A real-time desktop AI assistant.

This package contains the core modules for the assistant pipeline:
    audio_input       → Continuous microphone listening + silence detection
    stt               → Speech-to-Text (Groq / Whisper)
    decision_engine   → Decision model (placeholder)
    response_engine   → Response model (OpenRouter / Qwen)
    tts               → Text-to-Speech (Google Cloud TTS)
    micro_reaction    → Lightweight filler reactions (no LLM)
"""
