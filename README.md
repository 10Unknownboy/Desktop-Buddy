# 🤖 Desktop Buddy

A real-time desktop AI assistant built in Python with a **dual-model architecture**:

| Stage | Role | Provider |
|-------|------|----------|
| **Decision Model** (Brain) | Classifies input, controls routing | OpenRouter · Qwen 2.5 7B Instruct |
| **Response Model** (Writer) | Generates natural language replies | OpenRouter · Qwen 2.5 7B Instruct |

### Pipeline

```
          ┌───────────┐     ┌────────────┐     ┌─────────────────┐
  Mic ──▶ │   STT     │────▶│  Decision  │────▶│  Response Engine │──▶ TTS ──▶ Speaker
          │(Groq/     │     │  Engine    │     │  (only if       │
          │ Whisper)  │     │  (Brain)   │     │   needed)       │
          └───────────┘     └─────┬──────┘     └─────────────────┘
                                  │
                        ┌─────────▼─────────┐
                        │  Micro-Reaction   │
                        │  (if mode=LISTEN) │
                        └───────────────────┘
```

---

## 📂 Project Structure

```
Desktop-Buddy/
├── .env.example            # API key template
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── src/
    ├── __init__.py          # Package init
    ├── config.py            # Loads & validates .env
    ├── audio_input.py       # Continuous listening + silence detection
    ├── stt.py               # Speech-to-Text  (Groq Whisper) + confidence
    ├── decision_engine.py   # Decision model / Brain  (OpenRouter)
    ├── response_engine.py   # Response model / Writer (OpenRouter)
    ├── tts.py               # Text-to-Speech  (Google Cloud)
    ├── micro_reaction.py    # Lightweight filler reactions
    └── main.py              # Main loop + routing
```

---

## 🧠 Decision Engine

The brain of the system. It classifies every user input and outputs a structured **Instruction Object**:

### Modes

| Mode | Behaviour |
|------|-----------|
| `LISTEN` | No full response – play micro-reaction only |
| `SHORT_REPLY` | Brief conversational reply |
| `ADVICE` | Step-by-step help (quota-limited) |
| `REDIRECT` | Suggest external help, no LLM call |
| `IGNORE` | Do nothing |

### Cost Control

- Casual talk → `LISTEN` (no response LLM call)
- Low STT confidence → canned "can you repeat?" (no LLM calls at all)
- Advice quota (default: 5/session) → automatically downgrades to `SHORT_REPLY`

### Instruction Object

```json
{
  "mode": "SHORT_REPLY",
  "emotion": "neutral",
  "intent": "question",
  "response_needed": true,
  "max_length": "short",
  "tone": "friendly",
  "interrupt_action": "continue",
  "memory_write": false,
  "memory_field": null,
  "micro_reaction": "none",
  "external_redirect": false
}
```

---

## ⚙️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/Desktop-Buddy.git
cd Desktop-Buddy
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
# Copy the template
cp .env.example .env      # Linux/macOS
copy .env.example .env     # Windows
```

Open `.env` and fill in your keys:

| Variable | Where to get it |
|----------|----------------|
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your GCP service-account JSON (see below) |

#### Google Cloud TTS Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Enable the **Cloud Text-to-Speech API**.
4. Go to **IAM & Admin → Service Accounts** → create a service account.
5. Download the JSON key file.
6. Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to the **absolute path** of the JSON file.

---

## 🚀 Usage

```bash
python -m src.main
```

The assistant will:
1. 👂 Listen continuously (always-on mic with silence detection)
2. 🎭 Play a micro-reaction after ~1 s pause ("hmm…")
3. 📝 Transcribe after ~3 s silence using Groq (Whisper)
4. 🧠 Classify input via Decision Engine → Instruction Object
5. 💬 Generate a response (only if needed) via OpenRouter
6. 🔊 Speak the response via Google Cloud TTS

Press **Ctrl+C** to exit.

---

## 🛠️ Current Limitations

- ❌ Personality system
- ❌ Persistent memory / conversation history
- ❌ Interruption handling (flag exists, not yet wired)
- ❌ Threading / async
- ❌ Background music / ambient awareness

---

## 🗺️ Roadmap

- [x] ~~Foundation skeleton~~
- [x] ~~Continuous listening with silence detection~~
- [x] ~~Decision engine (Brain)~~
- [ ] Add personality system
- [ ] Persistent memory storage
- [ ] Wire interruption handling
- [ ] Reaction animations
- [ ] Cost tracking dashboard

---

## 📄 License

See [LICENSE](LICENSE) for details.
