"""
PRISM - Windows System Tray Manager
Allows running PRISM in the background minimized to the system tray.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import ctypes
import os
import sys
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw

_tray_icon = None


def has_tray_support() -> bool:
    try:
        import pystray
        return True
    except ImportError:
        return False


def get_console_hwnd() -> int:
    try:
        return ctypes.windll.kernel32.GetConsoleWindow()
    except Exception:
        return 0


def hide_console() -> bool:
    hwnd = get_console_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
        return True
    return False


def show_console() -> bool:
    hwnd = get_console_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 5)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return True
    return False


def create_prism_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(35, 37, 43), outline=(235, 175, 142), width=3)
    draw.polygon([(32, 14), (51, 49), (13, 49)], fill=(235, 175, 142))
    draw.polygon([(32, 22), (45, 46), (19, 46)], fill=(255, 255, 255))
    return img


def minimize_to_tray(bot_alias: str = "PRISM Bot", on_restore: Optional[Callable] = None) -> bool:
    global _tray_icon
    if not has_tray_support():
        hide_console()
        return False

    import pystray

    hide_console()

    def on_show(icon, item):
        show_console()
        try:
            icon.stop()
        except Exception:
            pass
        if on_restore:
            try:
                on_restore()
            except Exception:
                pass

    def on_exit(icon, item):
        try:
            icon.stop()
        except Exception:
            pass
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(f"● PRISM: @{bot_alias} (Онлайн)", None, enabled=False),
        pystray.MenuItem("Показать окно PRISM", on_show, default=True),
        pystray.MenuItem("Выход из PRISM", on_exit),
    )

    _tray_icon = pystray.Icon("PRISM", create_prism_icon(), f"PRISM Studio • @{bot_alias} Онлайн", menu)
    tray_thread = threading.Thread(target=_tray_icon.run, daemon=True)
    tray_thread.start()
    return True
