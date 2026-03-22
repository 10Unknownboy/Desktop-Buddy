# 🤖 Desktop Buddy

A real-time desktop AI assistant built in Python with a **dual-model architecture**:

| Stage | Role | Provider |
|-------|------|----------|
| **Decision Model** (Brain) | Decides what to do with user input | *Placeholder – coming soon* |
| **Response Model** (Writer) | Generates natural language replies | OpenRouter · Qwen 2.5 7B Instruct |

### Pipeline

```
Microphone → Speech-to-Text → Decision Engine → Response Engine → Text-to-Speech → Speaker
                (Groq/Whisper)    (placeholder)    (OpenRouter)     (Google Cloud)
```

---

## 📂 Project Structure

```
Desktop-Buddy/
├── .env.example          # API key template
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── src/
    ├── __init__.py       # Package init
    ├── config.py         # Loads & validates .env
    ├── audio_input.py    # Microphone recording
    ├── stt.py            # Speech-to-Text  (Groq Whisper)
    ├── decision_engine.py# Decision model   (placeholder)
    ├── response_engine.py# Response model   (OpenRouter)
    ├── tts.py            # Text-to-Speech   (Google Cloud)
    └── main.py           # Main loop
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
1. 🎙️ Record 5 seconds of audio from your microphone
2. 📝 Transcribe it using Groq (Whisper)
3. 🧠 Pass it through the decision engine (placeholder)
4. 💬 Generate a response via OpenRouter (Qwen 2.5)
5. 🔊 Speak the response via Google Cloud TTS

Press **Ctrl+C** to exit.

---

## 🛠️ Current Limitations

This is the **foundation build only**. The following features are **not** implemented yet:

- ❌ Continuous listening / silence detection
- ❌ Personality system
- ❌ Memory / conversation history
- ❌ Reactions & emotions
- ❌ Interruption handling
- ❌ Cost control logic
- ❌ Threading / async

---

## 🗺️ Roadmap

- [ ] Implement decision model logic
- [ ] Add personality system
- [ ] Conversation memory
- [ ] Continuous listening with VAD (Voice Activity Detection)
- [ ] Interruption handling
- [ ] Reaction animations
- [ ] Cost tracking & rate limiting

---

## 📄 License

See [LICENSE](LICENSE) for details.
