# 🤖 Desktop Buddy

A real-time desktop AI assistant built in Python with a **dual-model architecture**:

| Stage | Role | Provider |
|-------|------|----------|
| **Decision Model** (Brain) | Classifies input, controls routing | OpenRouter · Qwen 2.5 7B |
| **Response Model** (Writer) | Generates natural language replies | OpenRouter · Qwen 2.5 7B |

### Pipeline

```
          ┌───────────┐     ┌────────────┐     ┌─────────────────┐
  Mic ──▶ │   STT     │────▶│  Decision  │────▶│  Response Engine │──▶ TTS ──▶ Speaker
          │(Groq/     │     │  Engine    │     │  (personality-  │   (TTS.ai)
          │ Whisper)  │     │  (Brain)   │     │   aware)        │
          └───────────┘     └─────┬──────┘     └─────────────────┘
                                  │
                    ┌─────────────┼──────────────┐
                    ▼             ▼               ▼
              Micro-React    Memory Update    Mood Tracking
```

---

## 📂 Project Structure

```
Desktop-Buddy/
├── .env.example             # API key template
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
├── data/
│   ├── personality.json     # Personality config (editable)
│   └── memory.json          # User digital memory (auto-managed)
└── src/
    ├── __init__.py
    ├── config.py            # Loads & validates .env
    ├── audio_input.py       # Continuous listening + silence detection
    ├── stt.py               # Speech-to-Text (Groq Whisper) + confidence
    ├── decision_engine.py   # Brain – classifier + cost control
    ├── response_engine.py   # Writer – personality-aware responses
    ├── tts.py                  # Text-to-Speech (TTS.ai) + interrupt support
    ├── reaction_system.py      # Advanced emotion-aware reactions (no LLM)
    ├── interruption_handler.py # Stop/continue/switch interrupt logic
    ├── system_monitor.py       # CPU, RAM, app detection, smart alerts
    ├── micro_reaction.py       # Legacy reactions (kept for reference)
    ├── personality.py          # Personality system
    ├── memory_manager.py       # Memory, mood, engagement, presence
    └── main.py                 # Main loop + routing
```

---

## 🧠 Decision Engine

Classifies input → outputs **Instruction Object** controlling all downstream modules.

| Mode | Behaviour |
|------|-----------|
| `LISTEN` | Micro-reaction only, no LLM response |
| `SHORT_REPLY` | Brief conversational reply |
| `ADVICE` | Step-by-step help (quota-limited) |
| `REDIRECT` | Suggest external help, no LLM call |
| `IGNORE` | Do nothing |

---

## 🎭 Reaction System

Advanced micro-reactions — **zero LLM calls**, pure local logic.

- **Emotion pools:** happy → "haha"/"nice!", sad → "aww...", frustrated → "hmm..."
- **Intent awareness:** greetings get "hey!", rants get "I see..."
- **Variation:** last 5 reactions tracked, no immediate repeats
- **Natural timing:** 0.3–0.8 s random delay before speaking
- **Personality gating:** energy score + reaction_style filter reactions

---

### Cost Control
- Casual talk → `LISTEN` (1 LLM call)
- Low STT confidence → canned response (0 LLM calls)
- Advice quota reached → auto-downgrade to `SHORT_REPLY`

---

## 🎭 Personality System

Edit `data/personality.json`:
```json
{
  "name": "Buddy",
  "tone": "friendly",
  "style": "short",
  "energy_level": "dynamic",
  "reaction_style": "expressive"
}
```

- **Tone:** calm / friendly / playful
- **Style:** short / expressive / minimal
- **Energy:** random 1–10 at each startup — affects expressiveness
- **Reactions:** controlled by energy + reaction_style

---

## 📦 Memory System

Auto-managed `data/memory.json`:
- **User Profile** — name, preferences, interests
- **Mood Tracking** — score (−10 to +10), type (happy/sad/neutral)
- **Engagement Meter** — 0–10, recalculated from interaction frequency
- **Presence Simulation** — idle prompts when engagement is low
- **Advice Counter** — persisted across turns

Only relevant memory sections are loaded per response.

---

## ⚙️ Setup

### 1. Clone & install

```bash
git clone https://github.com/<your-username>/Desktop-Buddy.git
cd Desktop-Buddy
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
copy .env.example .env         # Windows
```

| Variable | Where to get it |
|----------|----------------|
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `TTS_AI_API_KEY` | [tts.ai](https://tts.ai) |

---

## 🚀 Usage

```bash
python -m src.main
```

1. 👂 Listens continuously (silence-detection)
2. 🎭 Micro-reaction at ~1 s pause
3. 📝 Transcribes after ~3 s silence (Groq/Whisper)
4. 🧠 Decision Engine classifies → Instruction Object
5. 💬 Response Engine generates reply (if needed)
6. 🔊 Speaks via TTS.ai (interruptible)
7. ⚡ If interrupted → capture new speech → decide stop/continue/switch
8. 📦 Updates mood + memory

Press **Ctrl+C** to exit.

---

## ⚡ Interruption System

User speech **always takes priority** over assistant speech.

| Action | Behaviour |
|--------|----------|
| `stop` | Discard previous response |
| `continue` | Resume from where it stopped |
| `switch` | Drop previous, start new response |

- Mic is polled every 50 ms during TTS playback
- `sd.stop()` halts audio instantly on detection
- Resume tracks exact sample position

---

## 🖥️ System Awareness

Monitors system health in the background (every ~8s, no blocking).

| Alert | Trigger | Cooldown |
|-------|---------|----------|
| High CPU | > 80% | 5 min |
| High RAM | > 80% | 5 min |
| High temp | > 85°C | 5 min |
| Heavy process | Single app > 50% CPU | 5 min (per app) |

- Active window tracked via `ctypes` (Windows, zero deps)
- Friendly app names (`chrome.exe` → "Chrome")
- Alerts spoken as short natural phrases

---

## 🛠️ Current Limitations

- ❌ Persistent conversation memory across sessions
- ❌ Background music / ambient

---

## 🗺️ Roadmap

- [x] ~~Foundation skeleton~~
- [x] ~~Continuous listening + silence detection~~
- [x] ~~Decision engine (Brain)~~
- [x] ~~Personality system~~
- [x] ~~User digital memory~~
- [x] ~~Mood tracking~~
- [x] ~~Advanced reaction system~~
- [x] ~~Engagement meter + presence~~
- [x] ~~System awareness~~
- [x] ~~Interruption handling~~
- [ ] Background music
- [ ] Advanced memory persistence

---

## 📄 License

See [LICENSE](LICENSE) for details.
