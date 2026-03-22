"""
system_monitor.py - System Awareness Module.

Lightweight system monitoring that tracks CPU, RAM, active window,
and top resource-consuming processes.  Fires alerts intelligently
with cooldown logic to avoid spamming the user.

Design principles:
    * psutil for CPU/RAM (low overhead)
    * ctypes for active window on Windows (no extra dependency)
    * Cooldown timers per alert type (5–10 min)
    * Only alerts when system is genuinely stressed
    * Integrates with decision engine via system_event dicts
"""

import ctypes
import time
from collections import defaultdict

import psutil

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
CPU_THRESHOLD: float = 80.0       # percent
RAM_THRESHOLD: float = 80.0       # percent
PROCESS_CPU_THRESHOLD: float = 50.0   # single process CPU %

# ---------------------------------------------------------------------------
# Cooldown (seconds) — per alert type
# ---------------------------------------------------------------------------
ALERT_COOLDOWN: int = 5 * 60      # 5 minutes between same alert type
CHECK_INTERVAL: float = 8.0       # seconds between background checks

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_last_alert_times: dict[str, float] = defaultdict(float)
_last_check_time: float = 0.0


# ---------------------------------------------------------------------------
# Core stats
# ---------------------------------------------------------------------------

def get_system_stats() -> dict:
    """
    Return current system stats (CPU, RAM, optional temp).

    Returns:
        Dict with keys: cpu_percent, ram_percent, ram_used_gb,
        ram_total_gb, temperature (if available).
    """
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()

    stats: dict = {
        "cpu_percent": cpu,
        "ram_percent": mem.percent,
        "ram_used_gb": round(mem.used / (1024 ** 3), 1),
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
    }

    # Temperature (optional — not all systems support this)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Get the first available sensor's current temp
            for name, entries in temps.items():
                if entries:
                    stats["temperature"] = entries[0].current
                    break
    except (AttributeError, Exception):
        pass  # sensors_temperatures not available on all platforms

    return stats


def get_active_window() -> str:
    """
    Return the title of the currently active window (Windows only).

    Returns empty string on failure or non-Windows platforms.
    """
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def get_top_processes(n: int = 5) -> list[dict]:
    """
    Return the top N processes by CPU usage.

    Each entry has: name, pid, cpu_percent, memory_mb.
    """
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            procs.append({
                "name": info["name"] or "unknown",
                "pid": info["pid"],
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_mb": round(
                    (info["memory_info"].rss if info["memory_info"] else 0)
                    / (1024 ** 2), 1
                ),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return procs[:n]


# ---------------------------------------------------------------------------
# High usage detection
# ---------------------------------------------------------------------------

def detect_high_usage() -> list[dict]:
    """
    Check for high resource usage and return a list of events.

    Each event is a dict suitable for feeding into the decision engine:
        {
            "intent": "system_event",
            "event_type": "high_cpu" | "high_ram" | "high_process_cpu",
            "app": "...",
            "value": float,
            "message": "..."
        }
    """
    events: list[dict] = []
    stats = get_system_stats()

    # --- CPU alert -------------------------------------------------------
    if stats["cpu_percent"] > CPU_THRESHOLD:
        events.append({
            "intent": "system_event",
            "event_type": "high_cpu",
            "app": "system",
            "value": stats["cpu_percent"],
            "message": f"CPU usage is at {stats['cpu_percent']:.0f}%",
        })

    # --- RAM alert -------------------------------------------------------
    if stats["ram_percent"] > RAM_THRESHOLD:
        events.append({
            "intent": "system_event",
            "event_type": "high_ram",
            "app": "system",
            "value": stats["ram_percent"],
            "message": (
                f"RAM usage is at {stats['ram_percent']:.0f}% "
                f"({stats['ram_used_gb']}GB / {stats['ram_total_gb']}GB)"
            ),
        })

    # --- Temperature alert (if available) --------------------------------
    temp = stats.get("temperature")
    if temp and temp > 85:
        events.append({
            "intent": "system_event",
            "event_type": "high_temperature",
            "app": "system",
            "value": temp,
            "message": f"System temperature is at {temp:.0f}°C",
        })

    # --- Per-process alerts ----------------------------------------------
    top = get_top_processes(3)
    for proc in top:
        if proc["cpu_percent"] > PROCESS_CPU_THRESHOLD:
            app_name = _friendly_name(proc["name"])
            events.append({
                "intent": "system_event",
                "event_type": "high_process_cpu",
                "app": app_name,
                "value": proc["cpu_percent"],
                "message": f"{app_name} is using {proc['cpu_percent']:.0f}% CPU",
            })

    return events


# ---------------------------------------------------------------------------
# Smart alert logic (cooldown)
# ---------------------------------------------------------------------------

def filter_alerts(events: list[dict]) -> list[dict]:
    """
    Filter events through cooldown logic.

    Only returns events whose alert type + app combo hasn't fired
    within ALERT_COOLDOWN seconds.
    """
    now = time.time()
    filtered: list[dict] = []

    for event in events:
        key = f"{event['event_type']}:{event.get('app', 'system')}"
        last = _last_alert_times.get(key, 0)

        if now - last >= ALERT_COOLDOWN:
            filtered.append(event)
            _last_alert_times[key] = now

    return filtered


# ---------------------------------------------------------------------------
# Main check function (called from main loop)
# ---------------------------------------------------------------------------

def check_system() -> list[dict]:
    """
    Perform a system check if enough time has elapsed.

    Returns a (possibly empty) list of cooldown-filtered events.
    Call this frequently — it self-throttles via CHECK_INTERVAL.
    """
    global _last_check_time
    now = time.time()

    if now - _last_check_time < CHECK_INTERVAL:
        return []

    _last_check_time = now

    events = detect_high_usage()
    return filter_alerts(events)


def get_system_context() -> str:
    """
    Return a 1-line system context string for prompt injection.

    Lightweight — just CPU%, RAM%, and active window.
    """
    try:
        cpu = psutil.cpu_percent(interval=0)
        ram = psutil.virtual_memory().percent
        window = get_active_window()
        app = _extract_app_from_title(window) if window else "unknown"
        return f"System: CPU {cpu:.0f}%, RAM {ram:.0f}%, active app: {app}"
    except Exception:
        return "System: stats unavailable"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_APP_NAME_MAP: dict[str, str] = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "code.exe": "VS Code",
    "explorer.exe": "File Explorer",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "notepad.exe": "Notepad",
    "powershell.exe": "PowerShell",
    "cmd.exe": "Command Prompt",
    "python.exe": "Python",
    "pythonw.exe": "Python",
}


def _friendly_name(process_name: str) -> str:
    """Convert a process filename to a user-friendly name."""
    lower = process_name.lower()
    return _APP_NAME_MAP.get(lower, process_name.replace(".exe", "").title())


def _extract_app_from_title(title: str) -> str:
    """Extract app name from window title (best-effort)."""
    if not title:
        return "unknown"
    # Many apps put their name at the end after " - "
    parts = title.split(" - ")
    if len(parts) > 1:
        return parts[-1].strip()
    return title[:30]
