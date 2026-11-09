"""
PRISM - Discord Webhook Client
Handles sending, editing, deleting messages, and fetching webhook info.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import json
import re
import time
from typing import Any, Dict, Optional, Tuple
import requests

from core.embed import Embed

DISCORD_WEBHOOK_REGEX = re.compile(
    r"^https:\/\/(?:ptb\.|canary\.)?discord(?:app)?\.com\/api\/webhooks\/(\d+)\/([a-zA-Z0-9_\-]+)\/?$"
)


class WebhookError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DiscordWebhookClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Prism-Discord-Embed-Studio/1.0 (+https://github.com/an1zy/prism-discord)",
        })

    @staticmethod
    def is_valid_url(url: str) -> bool:
        if not url:
            return False
        return bool(DISCORD_WEBHOOK_REGEX.match(url.strip()))

    @staticmethod
    def parse_webhook_ids(url: str) -> Optional[Tuple[str, str]]:
        m = DISCORD_WEBHOOK_REGEX.match(url.strip())
        if m:
            return m.group(1), m.group(2)
        return None

    def get_info(self, url: str) -> Dict[str, Any]:
        """Fetch details about the webhook (target channel, guild, name, avatar)."""
        if not self.is_valid_url(url):
            raise WebhookError("Invalid Discord Webhook URL format.")
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                raise WebhookError("Webhook not found or deleted by Discord server administrators.", 404)
            elif resp.status_code == 401:
                raise WebhookError("Invalid webhook token / unauthorized.", 401)
            else:
                raise WebhookError(f"Discord returned error {resp.status_code}: {resp.text}", resp.status_code)
        except requests.RequestException as e:
            raise WebhookError(f"Network error while connecting to Discord: {e}")

    def send(
        self,
        url: str,
        content: str = "",
        username: str = "",
        avatar_url: str = "",
        embed: Optional[Embed] = None,
        tts: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a message through the webhook.
        Appends ?wait=true to retrieve message ID from Discord API.
        """
        if not self.is_valid_url(url):
            raise WebhookError("Invalid Discord Webhook URL.")

        payload: Dict[str, Any] = {}
        if content:
            payload["content"] = content
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        if tts:
            payload["tts"] = True
        if embed is not None:
            payload["embeds"] = [embed.to_dict()]
            if getattr(embed, "buttons", None):
                payload["components"] = [
                    {
                        "type": 1,  # Action Row
                        "components": [b.to_dict() for b in embed.buttons],
                    }
                ]

        if not payload.get("content") and not payload.get("embeds"):
            raise WebhookError("Cannot send an empty message. Provide text content or an embed.")

        target_url = url if "?wait=true" in url else f"{url.rstrip('/')}?wait=true"

        for attempt in range(3):
            try:
                resp = self.session.post(target_url, json=payload, timeout=self.timeout)
                if resp.status_code in (200, 204):
                    return resp.json() if resp.text else {"id": "unknown"}
                elif resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 2.0)
                    time.sleep(float(retry_after) + 0.2)
                    continue
                elif resp.status_code == 400:
                    err_msg = resp.json().get("message", resp.text)
                    raise WebhookError(f"Discord rejected message payload (400): {err_msg}", 400)
                else:
                    raise WebhookError(f"Discord API returned status {resp.status_code}: {resp.text}", resp.status_code)
            except requests.RequestException as e:
                raise WebhookError(f"Connection failed: {e}")

        raise WebhookError("Exceeded retry limit due to rate-limiting.")

    def edit(
        self,
        url: str,
        message_id: str,
        content: Optional[str] = None,
        embed: Optional[Embed] = None,
    ) -> Dict[str, Any]:
        """Edit an already sent message by ID."""
        ids = self.parse_webhook_ids(url)
        if not ids:
            raise WebhookError("Invalid webhook URL.")
        webhook_id, webhook_token = ids
        edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id.strip()}"

        payload: Dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if embed is not None:
            payload["embeds"] = [embed.to_dict()]
            if getattr(embed, "buttons", None):
                payload["components"] = [
                    {
                        "type": 1,
                        "components": [b.to_dict() for b in embed.buttons],
                    }
                ]
            else:
                payload["components"] = []

        try:
            resp = self.session.patch(edit_url, json=payload, timeout=self.timeout)
            if resp.status_code in (200, 204):
                return resp.json() if resp.text else {}
            elif resp.status_code == 404:
                raise WebhookError("Message not found or message was not sent by this webhook.", 404)
            else:
                raise WebhookError(f"Discord returned error {resp.status_code}: {resp.text}", resp.status_code)
        except requests.RequestException as e:
            raise WebhookError(f"Failed to edit message: {e}")

    def delete(self, url: str, message_id: str) -> bool:
        """Delete an existing message by ID."""
        ids = self.parse_webhook_ids(url)
        if not ids:
            raise WebhookError("Invalid webhook URL.")
        webhook_id, webhook_token = ids
        del_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id.strip()}"

        try:
            resp = self.session.delete(del_url, timeout=self.timeout)
            if resp.status_code in (204, 200):
                return True
            elif resp.status_code == 404:
                raise WebhookError("Message not found.", 404)
            else:
                raise WebhookError(f"Discord returned error {resp.status_code}: {resp.text}", resp.status_code)
        except requests.RequestException as e:
            raise WebhookError(f"Failed to delete message: {e}")
