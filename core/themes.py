"""
PRISM - Terminal UI Themes
Color palettes for styling the terminal UI, borders, badges, and accents.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class UITheme:
    id: str
    name: str
    accent: str      # Main brand/highlight color
    secondary: str   # Subtle border/grid color
    muted: str       # Secondary text color
    success: str     # Green / Success
    error: str       # Red / Error
    info: str        # Cyan / Information


THEMES: Dict[str, UITheme] = {
    "peach": UITheme(
        id="peach",
        name="Peach Street (Фирменный тёплый)",
        accent="#EBAF8E",
        secondary="#3F3F46",
        muted="#8C8C8C",
        success="#57F287",
        error="#ED4245",
        info="#00D9FF",
    ),
    "cyan": UITheme(
        id="cyan",
        name="Cyber Neon (Неон / Киберпанк)",
        accent="#00D9FF",
        secondary="#1E3A5F",
        muted="#64748B",
        success="#22C55E",
        error="#EF4444",
        info="#38BDF8",
    ),
    "blurple": UITheme(
        id="blurple",
        name="Discord Blurple (Официальный Дискорд)",
        accent="#5865F2",
        secondary="#35373C",
        muted="#949BA4",
        success="#57F287",
        error="#ED4245",
        info="#00A8FC",
    ),
    "emerald": UITheme(
        id="emerald",
        name="Emerald Matrix (Изумрудный)",
        accent="#57F287",
        secondary="#274934",
        muted="#6B7280",
        success="#4ADE80",
        error="#F87171",
        info="#34D399",
    ),
    "monochrome": UITheme(
        id="monochrome",
        name="Stealth Titanium (Титан / Минимал)",
        accent="#E4E4E7",
        secondary="#52525B",
        muted="#71717A",
        success="#A1A1AA",
        error="#F43F5E",
        info="#D4D4D8",
    ),
}

DEFAULT_THEME = "peach"


def get_theme(theme_id: str) -> UITheme:
    return THEMES.get(theme_id.lower(), THEMES[DEFAULT_THEME])


def list_themes() -> List[UITheme]:
    return list(THEMES.values())
