"""
PRISM - Storage & Configuration Manager
Handles saved webhook profiles, multi-bot fleet, template persistence,
timed giveaways, language and theme preferences.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from core.embed import Embed


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
        if (exe_dir / "config.json").exists() or (exe_dir / "templates").exists():
            return exe_dir
        if (exe_dir.parent / "config.json").exists() or (exe_dir.parent / "templates").exists():
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_FILE = BASE_DIR / "config.json"
WEBHOOKS_FILE = BASE_DIR / "webhooks.json"
HISTORY_FILE = BASE_DIR / "history.json"
GIVEAWAYS_FILE = BASE_DIR / "giveaways.json"
BOT_CONFIGS_FILE = BASE_DIR / "bot_configs.json"
WARNS_FILE = BASE_DIR / "warns.json"
COMPONENTS_FILE = BASE_DIR / "components.json"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
TEMPLATES_DIR = BASE_DIR / "templates"


class StorageManager:
    def __init__(self) -> None:
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self) -> None:
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text("{}", encoding="utf-8")
        if not WEBHOOKS_FILE.exists():
            WEBHOOKS_FILE.write_text("{}", encoding="utf-8")
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("[]", encoding="utf-8")
        if not GIVEAWAYS_FILE.exists():
            GIVEAWAYS_FILE.write_text("{}", encoding="utf-8")
        if not COMPONENTS_FILE.exists():
            COMPONENTS_FILE.write_text(json.dumps({"buttons": {}, "options": {}}), encoding="utf-8")

    # --- Config: Language & Theme ---

    def get_config(self) -> Dict[str, Any]:
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _update_config(self, key: str, value: Any) -> None:
        cfg = self.get_config()
        cfg[key] = value
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_language(self) -> str:
        return str(self.get_config().get("language", "auto")).lower()

    def set_language(self, lang: str) -> None:
        self._update_config("language", lang.lower())

    def get_theme(self) -> str:
        return str(self.get_config().get("theme", "peach")).lower()

    def set_theme(self, theme: str) -> None:
        self._update_config("theme", theme.lower())

    # --- Multi-Bot Fleet Management ---

    def get_bots(self) -> Dict[str, Dict[str, Any]]:
        cfg = self.get_config()
        bots = cfg.get("bots")
        if isinstance(bots, dict):
            return bots
        # Backwards compatibility with single bot_token
        legacy_token = cfg.get("bot_token")
        if legacy_token:
            return {"DefaultBot": {"token": legacy_token, "name": "DefaultBot"}}
        return {}

    def get_bot(self, alias: str) -> Optional[Dict[str, Any]]:
        return self.get_bots().get(alias)

    def save_bot(self, alias: str, token: str, name: str = "") -> None:
        cfg = self.get_config()
        if "bots" not in cfg or not isinstance(cfg["bots"], dict):
            cfg["bots"] = {}
        cfg["bots"][alias.strip()] = {
            "token": token.strip(),
            "name": name.strip() or alias.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Also set as active / fallback bot_token
        cfg["bot_token"] = token.strip()
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def remove_bot(self, alias: str) -> bool:
        cfg = self.get_config()
        if "bots" in cfg and isinstance(cfg["bots"], dict):
            if alias in cfg["bots"]:
                del cfg["bots"][alias]
                CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                return True
        return False

    def get_bot_token(self, alias: Optional[str] = None) -> str:
        bots = self.get_bots()
        if alias and alias in bots:
            return str(bots[alias].get("token", "")).strip()
        if bots:
            # Return first available bot
            first_key = next(iter(bots))
            return str(bots[first_key].get("token", "")).strip()
        return str(self.get_config().get("bot_token", "")).strip()

    def save_bot_token(self, token: str) -> None:
        self.save_bot("DefaultBot", token)

    # --- Bot Engines Config ---

    def get_bot_engines_config(self, alias: str) -> Dict[str, Any]:
        try:
            configs = json.loads(BOT_CONFIGS_FILE.read_text(encoding="utf-8"))
            return configs.get(alias, {})
        except Exception:
            return {}

    def save_bot_engines_config(self, alias: str, data: Dict[str, Any]) -> None:
        try:
            configs = json.loads(BOT_CONFIGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            configs = {}
        configs[alias] = data
        BOT_CONFIGS_FILE.write_text(json.dumps(configs, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Webhooks Management ---

    def get_webhooks(self) -> Dict[str, str]:
        try:
            return json.loads(WEBHOOKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_webhook(self, alias: str, url: str) -> None:
        webhooks = self.get_webhooks()
        webhooks[alias.strip()] = url.strip()
        WEBHOOKS_FILE.write_text(json.dumps(webhooks, indent=2, ensure_ascii=False), encoding="utf-8")

    def remove_webhook(self, alias: str) -> bool:
        webhooks = self.get_webhooks()
        if alias in webhooks:
            del webhooks[alias]
            WEBHOOKS_FILE.write_text(json.dumps(webhooks, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        return False

    def get_webhook(self, alias: str) -> Optional[str]:
        return self.get_webhooks().get(alias)

    # --- Templates Management ---

    def list_templates(self) -> List[str]:
        items = [f.stem for f in TEMPLATES_DIR.glob("*.json") if not f.stem.endswith("_en")]
        return sorted(items)

    def load_template(self, name: str) -> Optional[Embed]:
        clean_name = name.removesuffix("_en")
        lang = self.get_language()
        if lang == "en":
            en_file = TEMPLATES_DIR / f"{clean_name}_en.json"
            if en_file.exists():
                try:
                    data = json.loads(en_file.read_text(encoding="utf-8"))
                    return Embed.from_dict(data)
                except Exception:
                    pass

        file_path = TEMPLATES_DIR / f"{clean_name}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return Embed.from_dict(data)
        except Exception:
            return None

    def save_template(self, name: str, embed: Embed) -> Path:
        file_path = TEMPLATES_DIR / f"{name.strip().lower().replace(' ', '_')}.json"
        payload = embed.to_template_dict() if hasattr(embed, "to_template_dict") else embed.to_dict()
        file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return file_path

    def delete_template(self, name: str) -> bool:
        file_path = TEMPLATES_DIR / f"{name}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    # --- Giveaways Persistence ---

    def get_giveaways(self) -> Dict[str, Any]:
        try:
            return json.loads(GIVEAWAYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_giveaway(self, custom_id: str) -> Optional[Dict[str, Any]]:
        return self.get_giveaways().get(custom_id)

    def save_giveaway(self, custom_id: str, data: Dict[str, Any]) -> None:
        g = self.get_giveaways()
        g[custom_id] = data
        GIVEAWAYS_FILE.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_giveaway_participant(self, custom_id: str, user_id: int, username: str) -> Tuple[bool, int]:
        """Adds participant to giveaway. Returns (is_new, total_count)."""
        g = self.get_giveaways()
        if custom_id not in g:
            g[custom_id] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "participants": [],
                "status": "active",
            }
        participants = g[custom_id].get("participants", [])
        if any(p.get("user_id") == user_id for p in participants):
            return False, len(participants)

        participants.append({
            "user_id": user_id,
            "username": username,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        })
        g[custom_id]["participants"] = participants
        GIVEAWAYS_FILE.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, len(participants)

    def list_active_giveaways(self) -> List[Dict[str, Any]]:
        g = self.get_giveaways()
        return [v for v in g.values() if v.get("status") == "active"]

    def mark_giveaway_ended(self, custom_id: str, winners: List[Dict[str, Any]]) -> None:
        g = self.get_giveaways()
        if custom_id in g:
            g[custom_id]["status"] = "ended"
            g[custom_id]["winners"] = winners
            g[custom_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
            GIVEAWAYS_FILE.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Message History Management ---

    def get_history(self, limit: int = 15) -> List[Dict[str, Any]]:
        try:
            items: List[Dict[str, Any]] = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return items[-limit:]
        except Exception:
            return []

    def record_message(self, message_id: str, sender_alias: str, title: str, content: str = "", channel_id: Optional[int] = None) -> None:
        try:
            items: List[Dict[str, Any]] = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            items = []
        items.append({
            "id": str(message_id),
            "sender": sender_alias,
            "channel_id": channel_id,
            "title": title or (content[:40] if content else "Untitled Message"),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        items = items[-50:]
        HISTORY_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def delete_history_item(self, message_id: str) -> None:
        try:
            items: List[Dict[str, Any]] = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            items = [it for it in items if str(it.get("id")) != str(message_id)]
            HISTORY_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # --- Moderation & Warnings ---

    def add_warn(self, user_id: int, reason: str = "", moderator: str = "Admin") -> int:
        warns = self.get_all_warns()
        uid_str = str(user_id)
        if uid_str not in warns:
            warns[uid_str] = []
        warns[uid_str].append({
            "reason": reason or "Нарушение правил сервера",
            "moderator": moderator,
            "date": datetime.now(timezone.utc).isoformat(),
        })
        WARNS_FILE.write_text(json.dumps(warns, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(warns[uid_str])

    def get_user_warns(self, user_id: int) -> List[Dict[str, Any]]:
        warns = self.get_all_warns()
        return warns.get(str(user_id), [])

    def get_all_warns(self) -> Dict[str, List[Dict[str, Any]]]:
        if not WARNS_FILE.exists():
            return {}
        try:
            return json.loads(WARNS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    # --- Persistent Components (Buttons & Select Options) ---

    def get_components(self) -> Dict[str, Any]:
        if not COMPONENTS_FILE.exists():
            return {"buttons": {}, "options": {}}
        try:
            return json.loads(COMPONENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"buttons": {}, "options": {}}

    def save_components(self, buttons: Optional[List[Any]] = None, select_menu: Optional[Any] = None) -> None:
        data = self.get_components()
        btns = data.get("buttons", {})
        opts = data.get("options", {})

        if buttons:
            for b in buttons:
                cid = getattr(b, "custom_id", "")
                if cid:
                    btns[cid] = {
                        "custom_id": cid,
                        "label": getattr(b, "label", ""),
                        "action_type": getattr(b, "action_type", "custom"),
                        "role_id": getattr(b, "role_id", ""),
                        "prize": getattr(b, "prize", ""),
                        "response_text": getattr(b, "response_text", ""),
                        "duration_minutes": getattr(b, "duration_minutes", 0),
                        "winners_count": getattr(b, "winners_count", 1),
                    }

        if select_menu and getattr(select_menu, "options", None):
            for opt in select_menu.options:
                val = getattr(opt, "value", "")
                if val:
                    opts[val] = {
                        "value": val,
                        "label": getattr(opt, "label", ""),
                        "action_type": getattr(opt, "action_type", "custom"),
                        "role_id": getattr(opt, "role_id", ""),
                        "response_text": getattr(opt, "response_text", ""),
                    }

        data["buttons"] = btns
        data["options"] = opts
        try:
            COMPONENTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def get_component_button(self, custom_id: str) -> Optional[Dict[str, Any]]:
        return self.get_components().get("buttons", {}).get(custom_id)

    def get_component_option(self, value: str) -> Optional[Dict[str, Any]]:
        return self.get_components().get("options", {}).get(value)
