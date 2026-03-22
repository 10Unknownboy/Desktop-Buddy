"""
config.py - Configuration & environment variable loader.

Loads API keys from a .env file at the project root and validates
that all required variables are present.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from the project root (one level up from src/)
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"

if not _env_path.exists():
    print(
        "[ERROR] .env file not found at:", _env_path,
        "\n        Copy .env.example → .env and fill in your API keys.",
    )
    sys.exit(1)

load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Required API keys
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# ---------------------------------------------------------------------------
# Validate at import time
# ---------------------------------------------------------------------------
_missing: list[str] = []

if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
    _missing.append("GROQ_API_KEY")
if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
    _missing.append("OPENROUTER_API_KEY")
if not GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS == "path/to/your/service-account.json":
    _missing.append("GOOGLE_APPLICATION_CREDENTIALS")

if _missing:
    print(
        "[ERROR] Missing or placeholder API keys in .env:",
        ", ".join(_missing),
        "\n        Please fill in your real keys before running.",
    )
    sys.exit(1)

# Set the GCP credentials env var so the google-cloud SDK picks it up
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
