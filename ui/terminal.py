"""
PRISM - Terminal UI & Live Discord Embed Renderer
Renders high-fidelity Discord-like embeds and menus in the console using Rich.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

if sys.platform == "win32":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box

from core.embed import Embed, COLOR_PRESETS
from core.themes import UITheme, get_theme, DEFAULT_THEME
from core.i18n import t

# Default Base Colors
PEACH = "#EBAF8E"
MUTED = "#8C8C8C"
DARK_BG = "#18181B"
DISCORD_PANEL = "#2B2D31"
BORDER_GRAY = "#3F3F46"
GREEN = "#57F287"
RED = "#ED4245"
CYAN = "#00D9FF"

console = Console(force_terminal=True)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner(theme: Optional[UITheme] = None) -> None:
    accent = theme.accent if theme else PEACH
    from core.i18n import t
    banner = f"""[{accent}]
    ____  ____  _________  __  ___
   / __ \\/ __ \\/  _/ ___/ /  |/  /
  / /_/ / /_/ // / \\__ \\ / /|_/ / 
 / ____/ _, _// / ___/ // /  / /  
/_/   /_/ |_/___//____//_/  /_/   [/{accent}]
   [{MUTED}]{t('app_title')}[/]
"""
    console.print(banner)


def render_embed_preview(embed: Embed, username: str = "", avatar_url: str = "", theme: Optional[UITheme] = None) -> None:
    """
    Renders an ASCII/Rich preview of the Discord message with left colored border,
    author, title, description, fields and footer.
    """
    accent = theme.accent if theme else PEACH
    embed_color_hex = embed.color_hex
    elements: List[Any] = []

    # Webhook Bot User Header
    if username or avatar_url:
        bot_text = Text()
        bot_text.append("[BOT] ", style=f"bold {accent}")
        bot_text.append(username or "Prism Webhook", style="bold white")
        bot_text.append("  APP", style="bold white on #5865F2")
        bot_text.append(f"  • Today at {datetime.now().strftime('%H:%M')}", style=MUTED)
        elements.append(bot_text)
        elements.append(Text(""))

    # Author
    if embed.author_name:
        author_text = Text()
        author_text.append(f"• {embed.author_name}", style="bold white")
        if embed.author_url:
            author_text.append(f" ({embed.author_url})", style=f"{MUTED} underline")
        elements.append(author_text)

    # Title
    if embed.title:
        title_text = Text(embed.title, style=f"bold {accent}")
        if embed.url:
            title_text.stylize(f"underline {accent}")
        elements.append(title_text)

    # Description
    if embed.description:
        clean_desc = embed.description.replace("\\n", "\n")
        desc_text = Text(clean_desc, style="white")
        elements.append(desc_text)

    # Fields
    if embed.fields:
        inline_row: List[Panel] = []

        for fld in embed.fields:
            field_content = Text()
            field_content.append(f"{fld.name}\n", style="bold #D4D4D8")
            clean_val = fld.value.replace("\\n", "\n")
            field_content.append(clean_val, style="white")

            if fld.inline:
                inline_row.append(Panel(field_content, border_style=BORDER_GRAY, padding=(0, 1), box=box.ROUNDED))
                if len(inline_row) == 3:
                    elements.append(Columns(inline_row, equal=True))
                    inline_row = []
            else:
                if inline_row:
                    elements.append(Columns(inline_row, equal=True))
                    inline_row = []
                elements.append(Panel(field_content, border_style=BORDER_GRAY, padding=(0, 1), box=box.ROUNDED))

        if inline_row:
            elements.append(Columns(inline_row, equal=True))

    # Images info
    if embed.thumbnail_url:
        elements.append(Text(f"[Thumbnail: {embed.thumbnail_url}]", style=f"{MUTED} italic"))
    if embed.image_url:
        elements.append(Text(f"[Image: {embed.image_url}]", style=f"{MUTED} italic"))

    # Footer
    footer_elements = []
    if embed.footer_text:
        footer_elements.append(embed.footer_text)
    if embed.timestamp:
        footer_elements.append(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    if footer_elements:
        elements.append(Text(" • ".join(footer_elements), style=f"{MUTED}"))

    # Embed Panel with left accent border
    embed_body = Table.grid()
    for el in elements:
        embed_body.add_row(el)

    preview_panel = Panel(
        embed_body,
        border_style=embed_color_hex,
        box=box.HORIZONTALS,
        title=f"[{embed_color_hex}]Discord Embed Preview[/{embed_color_hex}]",
        title_align="left",
        padding=(1, 2),
    )

    console.print(preview_panel)

    # Discord Interactive Buttons Row (Action Row)
    if getattr(embed, "buttons", None):
        btn_text = Text()
        btn_text.append("  ")
        style_bg = {
            1: "#5865F2",  # Blurple (Primary)
            2: "#4E5058",  # Gray (Secondary)
            3: "#248046",  # Green (Success)
            4: "#DA373C",  # Red (Danger)
            5: "#2B2D31",  # Dark (Link)
        }
        for i, b in enumerate(embed.buttons):
            b_style = getattr(b, "style", 5)
            bg = style_bg.get(b_style, "#5865F2")
            emoji_str = f"{b.emoji} " if b.emoji else ("🔗 " if b_style == 5 else "")
            arrow_str = " ↗" if b_style == 5 else ""
            btn_text.append(f" {emoji_str}{b.label}{arrow_str} ", style=f"bold white on {bg}")
            if i < len(embed.buttons) - 1:
                btn_text.append("   ")
        console.print(btn_text)
        console.print("")

    # Discord Select Menu Row (Action Row 2)
    if getattr(embed, "select_menu", None) and embed.select_menu.options:
        sm = embed.select_menu
        opts_preview = " • ".join(f"{o.emoji + ' ' if o.emoji else ''}{o.label}" for o in sm.options[:4])
        if len(sm.options) > 4:
            opts_preview += f" (+{len(sm.options)-4})"
        console.print(f"   [bold white on #2B2D31]  ▼ {sm.placeholder}  [/] [{MUTED}]({opts_preview})[/]")
        console.print("")


def display_fleet_list(bots: Dict[str, Dict[str, Any]], webhooks: Dict[str, str], theme: UITheme) -> None:
    """Displays saved Bot profiles and Webhooks in a unified Sender Fleet table."""
    table = Table(
        title="Отряд отправителей PRISM (Bots & Webhooks)",
        border_style=theme.secondary,
        header_style=f"bold {theme.accent}",
    )
    table.add_column("#", justify="right", style=f"bold {theme.accent}", width=4)
    table.add_column("Тип", style="bold white", width=14)
    table.add_column("Имя / Алиас", style="bold white", width=22)
    table.add_column("Статус / Endpoint", style=MUTED)

    row_idx = 1
    for alias, b_data in bots.items():
        name = b_data.get("name", alias)
        token_preview = "Токен сохранён (Bot API)"
        table.add_row(str(row_idx), "🤖 Discord Bot", f"@{name}", f"[{GREEN}]{token_preview}[/{GREEN}]")
        row_idx += 1

    for alias, url in webhooks.items():
        masked_url = url[:40] + "..." if len(url) > 40 else url
        table.add_row(str(row_idx), "🔗 Webhook", alias, masked_url)
        row_idx += 1

    if row_idx == 1:
        console.print(f"[{MUTED}]Профили не найдены. Добавьте бота или вебхук, чтобы начать![/{MUTED}]\n")
    else:
        console.print(table)
        console.print("")


def display_webhook_list(webhooks: Dict[str, str], theme: Optional[UITheme] = None) -> None:
    accent = theme.accent if theme else PEACH
    border = theme.secondary if theme else BORDER_GRAY

    if not webhooks:
        console.print(f"[{MUTED}]Сохранённые вебхуки не найдены.[/{MUTED}]\n")
        return

    table = Table(title="Сохранённые профили вебхуков", border_style=border, header_style=f"bold {accent}")
    table.add_column("#", justify="right", style=f"bold {accent}", width=4)
    table.add_column("Алиас", style="bold white", width=22)
    table.add_column("Тип", style="white", width=18)
    table.add_column("Discord Webhook URL", style=MUTED)

    for idx, (alias, url) in enumerate(webhooks.items(), start=1):
        masked_url = url[:45] + "..." if len(url) > 45 else url
        table.add_row(str(idx), alias, "Discord Webhook", masked_url)

    console.print(table)
    console.print("")


def display_template_list(templates: List[str], theme: Optional[UITheme] = None) -> None:
    accent = theme.accent if theme else PEACH
    border = theme.secondary if theme else BORDER_GRAY

    table = Table(title="Доступные шаблоны сообщений", border_style=border, header_style=f"bold {accent}")
    table.add_column("#", justify="right", style=f"bold {accent}", width=4)
    table.add_column("Шаблон (ID)", style="bold white", width=22)
    table.add_column("Назначение / Описание", style=MUTED)

    purposes = {
        "announcement": "Официальные новости, анонсы и важные события",
        "server_status": "Мониторинг серверов, аптайм и статус работы",
        "rules": "Правила сообщества, регламент модерации",
        "giveaway": "Розыгрыши Discord Nitro с таймером и кнопкой",
        "changelog": "Список изменений патча, добавленные и исправленные фичи",
        "test_lab": "Полный тестовый стенд для проверки всех кнопок, полей и ролей",
    }

    for idx, name in enumerate(templates, start=1):
        table.add_row(str(idx), name, purposes.get(name, "Пользовательский шаблон"))

    console.print(table)
    console.print("")


def ask_choice(prompt_text: str = "Выберите действие >", choices: Optional[List[str]] = None, default: str = "1", theme: Optional[UITheme] = None) -> str:
    """Clean input prompt styled with active theme accent and no choices clutter."""
    accent = theme.accent if theme else PEACH
    return Prompt.ask(
        f"[{accent}]{prompt_text}[/]",
        choices=choices,
        default=default,
        show_choices=False,
        show_default=False,
    ).strip()
