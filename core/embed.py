"""
PRISM - Discord Bot Management & Control Suite
Core Embed and Component Models (Embed, Fields, Buttons)
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

COLOR_PRESETS: Dict[str, int] = {
    "peach": 0xEBAF8E,
    "blurple": 0x5865F2,
    "green": 0x57F287,
    "yellow": 0xFEE75C,
    "fuchsia": 0xEB459E,
    "red": 0xED4245,
    "white": 0xFFFFFF,
    "dark": 0x2B2D31,
    "charcoal": 0x1E1F22,
    "gold": 0xF1C40F,
    "cyan": 0x00D9FF,
    "purple": 0x9B59B6,
}


def parse_color(value: str | int) -> int:
    if isinstance(value, int):
        return max(0, min(0xFFFFFF, value))
    val = str(value).strip().lower()
    if val in COLOR_PRESETS:
        return COLOR_PRESETS[val]
    val = val.lstrip("#").replace("0x", "")
    if re.fullmatch(r"[0-9a-f]{6}", val):
        return int(val, 16)
    if re.fullmatch(r"[0-9a-f]{3}", val):
        return int("".join(c * 2 for c in val), 16)
    return COLOR_PRESETS["peach"]


BUTTON_STYLES = {
    "link": 5,
    "primary": 1,    # Blurple
    "secondary": 2,  # Gray
    "success": 3,    # Green
    "danger": 4,     # Red
}

STYLE_NAMES = {
    1: "Blurple (Синий)",
    2: "Gray (Серый)",
    3: "Green (Зеленый)",
    4: "Danger (Красный)",
    5: "Link (Ссылка ↗)",
}


@dataclass
class Button:
    label: str
    url: str = ""
    emoji: str = ""
    action_type: str = "link"  # "link" | "giveaway" | "verify" | "custom"
    style: int = 5  # 5 = Link, 1 = Blurple, 2 = Gray, 3 = Green, 4 = Danger
    custom_id: str = ""
    response_text: str = ""  # Текст ответа при нажатии (эфемерное сообщение)
    role_id: str = ""        # ID роли в Discord для выдачи (при verify)
    prize: str = ""          # Название приза (при giveaway)
    duration_minutes: int = 0  # Таймер розыгрыша в минутах (0 = ручной)
    winners_count: int = 1   # Количество победителей

    def __post_init__(self) -> None:
        if self.action_type != "link" and not self.custom_id:
            import uuid
            self.custom_id = f"prism_{self.action_type}_{uuid.uuid4().hex[:8]}"
        if self.action_type != "link" and self.style == 5:
            self.style = 3 if self.action_type == "verify" else 1

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "type": 2,
            "style": self.style,
            "label": (self.label or "Button")[:80],
        }
        if self.emoji:
            data["emoji"] = {"name": self.emoji.strip()}

        if self.style == 5 or self.action_type == "link":
            data["style"] = 5
            data["url"] = self.url.strip() or "https://discord.com"
        else:
            data["custom_id"] = self.custom_id or f"prism_btn_{id(self)}"

        return data

    def to_template_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["action_type"] = self.action_type
        d["response_text"] = self.response_text
        d["role_id"] = self.role_id
        d["prize"] = self.prize
        d["duration_minutes"] = self.duration_minutes
        d["winners_count"] = self.winners_count
        if self.url:
            d["url"] = self.url
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Button:
        emoji_val = ""
        raw_emoji = data.get("emoji")
        if isinstance(raw_emoji, dict):
            emoji_val = str(raw_emoji.get("name", ""))
        elif isinstance(raw_emoji, str):
            emoji_val = raw_emoji

        action_type = data.get("action_type")
        style = int(data.get("style", 5))
        if not action_type:
            action_type = "link" if (style == 5 or "url" in data) else "custom"

        return cls(
            label=str(data.get("label", "Button")),
            url=str(data.get("url", "")),
            emoji=emoji_val,
            action_type=action_type,
            style=style,
            custom_id=str(data.get("custom_id", "")),
            response_text=str(data.get("response_text", "")),
            role_id=str(data.get("role_id", "")),
            prize=str(data.get("prize", "")),
            duration_minutes=int(data.get("duration_minutes", 0)),
            winners_count=int(data.get("winners_count", 1)),
        )


@dataclass
class SelectOption:
    label: str
    value: str
    description: str = ""
    emoji: str = ""
    action_type: str = "reply"  # "reply", "role", "ticket"
    response_text: str = ""
    role_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "label": self.label[:100],
            "value": self.value[:100],
        }
        if self.description:
            d["description"] = self.description[:100]
        if self.emoji:
            d["emoji"] = {"name": self.emoji} if isinstance(self.emoji, str) else self.emoji
        return d

    def to_template_dict(self) -> Dict[str, Any]:
        d = self.to_dict()
        d["action_type"] = self.action_type
        d["response_text"] = self.response_text
        d["role_id"] = self.role_id
        if self.emoji:
            d["emoji"] = self.emoji
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelectOption:
        emo = data.get("emoji", "")
        if isinstance(emo, dict):
            emo = emo.get("name", "")
        return cls(
            label=str(data.get("label", "Option")),
            value=str(data.get("value", "opt")),
            description=str(data.get("description", "")),
            emoji=str(emo),
            action_type=str(data.get("action_type", "reply")),
            response_text=str(data.get("response_text", "")),
            role_id=str(data.get("role_id", "")),
        )


@dataclass
class SelectMenu:
    custom_id: str = "prism_select_menu"
    placeholder: str = "Выберите действие..."
    min_values: int = 1
    max_values: int = 1
    options: List[SelectOption] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": 3,
            "custom_id": self.custom_id,
            "placeholder": self.placeholder[:150],
            "min_values": self.min_values,
            "max_values": self.max_values,
            "options": [opt.to_dict() for opt in self.options[:25]],
        }

    def to_template_dict(self) -> Dict[str, Any]:
        return {
            "custom_id": self.custom_id,
            "placeholder": self.placeholder,
            "min_values": self.min_values,
            "max_values": self.max_values,
            "options": [opt.to_template_dict() for opt in self.options[:25]],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelectMenu:
        opts = [SelectOption.from_dict(o) for o in data.get("options", []) if isinstance(o, dict)]
        return cls(
            custom_id=str(data.get("custom_id", "prism_select_menu")),
            placeholder=str(data.get("placeholder", "Выберите действие...")),
            min_values=int(data.get("min_values", 1)),
            max_values=int(data.get("max_values", 1)),
            options=opts,
        )


@dataclass
class EmbedField:
    name: str
    value: str
    inline: bool = False

    def __post_init__(self):
        self.name = str(self.name).replace("\\n", "\n")
        self.value = str(self.value).replace("\\n", "\n")

    def to_dict(self) -> Dict[str, Any]:
        clean_name = str(self.name).replace("\\n", "\n")[:256] or "\u200b"
        clean_val = str(self.value).replace("\\n", "\n")[:1024] or "\u200b"
        return {
            "name": clean_name,
            "value": clean_val,
            "inline": self.inline,
        }


@dataclass
class Embed:
    title: str = ""
    description: str = ""
    url: str = ""
    color: int = COLOR_PRESETS["peach"]
    author_name: str = ""
    author_url: str = ""
    author_icon_url: str = ""
    thumbnail_url: str = ""
    image_url: str = ""
    footer_text: str = ""
    footer_icon_url: str = ""
    timestamp: bool = True
    fields: List[EmbedField] = field(default_factory=list)
    buttons: List[Button] = field(default_factory=list)
    select_menu: Optional[SelectMenu] = None

    @property
    def color_hex(self) -> str:
        return f"#{self.color:06X}"

    def set_color(self, value: str | int) -> None:
        self.color = parse_color(value)

    def add_field(self, name: str, value: str, inline: bool = False) -> None:
        if len(self.fields) < 25:
            # Automatically convert literal \n to real newlines for multi-line fields
            clean_val = value.replace("\\n", "\n")
            self.fields.append(EmbedField(name=name, value=clean_val, inline=inline))

    def remove_field(self, index: int) -> bool:
        if 0 <= index < len(self.fields):
            self.fields.pop(index)
            return True
        return False

    def clear_fields(self) -> None:
        self.fields.clear()

    def add_button(
        self,
        label: str,
        url: str = "",
        emoji: str = "",
        action_type: str = "link",
        style: int = 5,
        custom_id: str = "",
        response_text: str = "",
        role_id: str = "",
        prize: str = "",
        duration_minutes: int = 0,
        winners_count: int = 1,
    ) -> bool:
        if len(self.buttons) < 5:  # Discord allows up to 5 buttons in 1 action row
            self.buttons.append(
                Button(
                    label=label,
                    url=url,
                    emoji=emoji,
                    action_type=action_type,
                    style=style,
                    custom_id=custom_id,
                    response_text=response_text,
                    role_id=role_id,
                    prize=prize,
                    duration_minutes=duration_minutes,
                    winners_count=winners_count,
                )
            )
            return True
        return False

    def remove_button(self, index: int) -> bool:
        if 0 <= index < len(self.buttons):
            self.buttons.pop(index)
            return True
        return False

    def clear_buttons(self) -> None:
        self.buttons.clear()

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"color": self.color}
        if self.title:
            data["title"] = self.title[:256]
        if self.description:
            data["description"] = self.description.replace("\\n", "\n")[:4096]
        if self.url:
            data["url"] = self.url
        if self.author_name:
            author: Dict[str, str] = {"name": self.author_name[:256]}
            if self.author_url:
                author["url"] = self.author_url
            if self.author_icon_url:
                author["icon_url"] = self.author_icon_url
            data["author"] = author
        if self.thumbnail_url:
            data["thumbnail"] = {"url": self.thumbnail_url}
        if self.image_url:
            data["image"] = {"url": self.image_url}
        if self.footer_text or self.footer_icon_url:
            footer: Dict[str, str] = {"text": str(self.footer_text or "PRISM").replace("\\n", "\n")[:2048]}
            if self.footer_icon_url:
                footer["icon_url"] = self.footer_icon_url
            data["footer"] = footer
        if self.timestamp:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        if self.fields:
            data["fields"] = [f.to_dict() for f in self.fields[:25]]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Embed:
        embed = cls()
        embed.title = str(data.get("title", ""))
        embed.description = str(data.get("description", ""))
        embed.url = str(data.get("url", ""))
        if "color" in data:
            embed.color = parse_color(data["color"])
        author = data.get("author") or {}
        if isinstance(author, dict):
            embed.author_name = str(author.get("name", ""))
            embed.author_url = str(author.get("url", ""))
            embed.author_icon_url = str(author.get("icon_url", ""))
        thumb = data.get("thumbnail") or {}
        if isinstance(thumb, dict):
            embed.thumbnail_url = str(thumb.get("url", ""))
        img = data.get("image") or {}
        if isinstance(img, dict):
            embed.image_url = str(img.get("url", ""))
        footer = data.get("footer") or {}
        if isinstance(footer, dict):
            embed.footer_text = str(footer.get("text", ""))
            embed.footer_icon_url = str(footer.get("icon_url", ""))
        embed.timestamp = bool(data.get("timestamp", True))
        embed.fields = []
        raw_fields = data.get("fields") or []
        if isinstance(raw_fields, list):
            for f in raw_fields:
                if isinstance(f, dict):
                    embed.fields.append(
                        EmbedField(
                            name=str(f.get("name", "")),
                            value=str(f.get("value", "")),
                            inline=bool(f.get("inline", False)),
                        )
                    )
        embed.buttons = []
        raw_buttons = data.get("buttons") or []
        if isinstance(raw_buttons, list):
            for b in raw_buttons:
                if isinstance(b, dict):
                    embed.buttons.append(Button.from_dict(b))
        if "select_menu" in data and isinstance(data["select_menu"], dict):
            embed.select_menu = SelectMenu.from_dict(data["select_menu"])
        return embed

    def to_template_dict(self) -> Dict[str, Any]:
        """Full payload including buttons and select menus for saving to templates"""
        d = self.to_dict()
        if self.buttons:
            d["buttons"] = [b.to_template_dict() for b in self.buttons]
        if self.select_menu:
            d["select_menu"] = self.select_menu.to_template_dict()
        return d

    def validate(self) -> List[str]:
        warnings: List[str] = []
        if not self.title and not self.description and not self.fields and not self.image_url:
            warnings.append("Эмбед пустой: добавьте заголовок, описание или картинку.")
        if len(self.title) > 256:
            warnings.append(f"Длина заголовка {len(self.title)} симв. (максимум 256).")
        if len(self.description) > 4096:
            warnings.append(f"Длина описания {len(self.description)} симв. (максимум 4096).")
        if len(self.fields) > 25:
            warnings.append(f"Количество полей: {len(self.fields)} (максимум 25).")
        if len(self.buttons) > 5:
            warnings.append(f"Кнопок: {len(self.buttons)} (максимум 5 в одном ряду Discord).")
        total_len = len(self.title) + len(self.description) + len(self.author_name) + len(self.footer_text)
        for f in self.fields:
            total_len += len(f.name) + len(f.value)
        if total_len > 6000:
            warnings.append(f"Всего символов: {total_len} (лимит Discord 6000).")
        return warnings
