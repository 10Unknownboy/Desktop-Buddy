"""
Desktop Buddy - A real-time desktop AI assistant.

This package contains the core modules for the assistant pipeline:
    audio_input            → Continuous microphone listening + silence detection
    stt                    → Speech-to-Text (Groq / Whisper)
    decision_engine        → Decision model / Brain (OpenRouter / Qwen)
    response_engine        → Response model / Writer (OpenRouter / Qwen)
    tts                    → Text-to-Speech (TTS.ai) + interruption support
    reaction_system        → Advanced emotion-aware reactions (no LLM)
    interruption_handler   → Stop/continue/switch on user interrupt
    system_monitor         → CPU, RAM, app detection, smart alerts
    engagement_manager     → Conversation quality scoring (7–10 min eval)
    time_awareness         → Time-of-day tone + greetings + rest reminders
    background_mode        → Ambient audio when idle (auto-stop on speech)
    personality            → Configurable personality system
    memory_manager         → User digital memory + mood + engagement
"""
