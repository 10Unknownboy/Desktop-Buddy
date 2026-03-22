"""
Desktop Buddy - A real-time desktop AI assistant.

Core modules:
    audio_input            → Continuous listening + silence detection
    stt                    → Speech-to-Text (Groq/Whisper) + retry
    decision_engine        → Brain (OpenRouter/Qwen) + retry + rate-limit
    response_engine        → Writer (OpenRouter/Qwen) + retry + fallback
    tts                    → Text-to-Speech (TTS.ai) + interruption + retry
    reaction_system        → Emotion-aware reactions (no LLM)
    interruption_handler   → Stop/continue/switch on interrupt
    system_monitor         → CPU, RAM, app detection, smart alerts
    engagement_manager     → Conversation quality scoring
    time_awareness         → Time-of-day tone + greetings
    background_mode        → Ambient audio when idle
    personality            → Configurable personality
    memory_manager         → User memory + mood + persistence
    logger                 → Structured file + console logging
"""
