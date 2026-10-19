import os
import sys
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

GRAY: Final[str] = "90"
GREEN: Final[str] = "32"
PLUM: Final[str] = "38;2;166;72;105"
TEAL: Final[str] = "36"
AMBER: Final[str] = "38;2;210;120;44"
PINK: Final[str] = "38;2;255;82;153"


def timestamp() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %I:%M %p")


def colorize(text: str, color: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return text
    return f"\033[{color}m{text}\033[0m"


def log_line(*segments: tuple[str, str]) -> None:
    parts: list[str] = [colorize(f"[{timestamp()}]", GRAY)]
    for text, color in segments:
        parts.append(colorize(text, color))
    print(" ".join(parts), flush=True)
