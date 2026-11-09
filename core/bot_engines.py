"""
PRISM - Bot Engines & Autonomous Modules
Autonomous modules for Discord bots:
1. AutoMod & Moderation Suite (Ban, Kick, Timeout, Purge, Warns, Anti-invite, Anti-spam/flood, Anti-caps, Bad words)
2. AI Assistant (Gemini / OpenAI / OpenRouter / Groq with context memory)
3. Welcomer & AutoRole (Auto-assign role on join, customizable welcome card)
4. Ticket Support Engine (Private threads, category select, close button, staff ping)
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
import html
import io
import json
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

import discord
from rich.console import Console
from rich.markup import escape

console = Console()


# --- 1. Engine Configuration Dataclass ---

@dataclass
class AutoModConfig:
    enabled: bool = False
    anti_invite: bool = True
    anti_spam: bool = True
    anti_caps: bool = False
    bad_words: List[str] = field(default_factory=list)
    log_channel_id: Optional[int] = None
    warn_in_chat: bool = True
    chat_commands: bool = True


@dataclass
class AIAssistantConfig:
    enabled: bool = False
    provider: str = "gemini"  # "gemini", "openai", "openrouter", "groq"
    api_key: str = ""
    model: str = "gemini-1.5-flash"  # or gpt-4o-mini, llama-3.3-70b-versatile
    system_prompt: str = "You are a friendly and helpful Discord server assistant."
    trigger_mode: str = "mention"  # "mention", "channel", "both"
    channel_id: Optional[int] = None


@dataclass
class WelcomerConfig:
    enabled: bool = False
    auto_role_id: Optional[int] = None
    welcome_channel_id: Optional[int] = None
    welcome_title: str = "👋 Добро пожаловать на сервер, {user}!"
    welcome_desc: str = "Рады видеть тебя в нашем сообществе! Приятного общения."
    welcome_color: int = 0xEBAF8E


@dataclass
class TicketConfig:
    enabled: bool = False
    support_role_id: Optional[int] = None
    category_channel_id: Optional[int] = None
    panel_channel_id: Optional[int] = None
    log_channel_id: Optional[int] = None
    prefix: str = "ticket-"


@dataclass
class BotEngineSettings:
    bot_alias: str = "DefaultBot"
    automod: AutoModConfig = field(default_factory=AutoModConfig)
    ai: AIAssistantConfig = field(default_factory=AIAssistantConfig)
    welcomer: WelcomerConfig = field(default_factory=WelcomerConfig)
    tickets: TicketConfig = field(default_factory=TicketConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_alias": self.bot_alias,
            "automod": asdict(self.automod),
            "ai": asdict(self.ai),
            "welcomer": asdict(self.welcomer),
            "tickets": asdict(self.tickets),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BotEngineSettings:
        alias = data.get("bot_alias", "DefaultBot")
        am_data = data.get("automod", {})
        ai_data = data.get("ai", {})
        w_data = data.get("welcomer", {})
        t_data = data.get("tickets", {})

        return cls(
            bot_alias=alias,
            automod=AutoModConfig(**am_data) if isinstance(am_data, dict) else AutoModConfig(),
            ai=AIAssistantConfig(**ai_data) if isinstance(ai_data, dict) else AIAssistantConfig(),
            welcomer=WelcomerConfig(**w_data) if isinstance(w_data, dict) else WelcomerConfig(),
            tickets=TicketConfig(**t_data) if isinstance(t_data, dict) else TicketConfig(),
        )


# --- 2. AutoMod Engine ---

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?(discord\.(gg|io|me|li)|discordapp\.com\/invite|discord\.com\/invite)\/[a-zA-Z0-9]+",
    re.IGNORECASE,
)


class AutoModEngine:
    def __init__(self, config: AutoModConfig):
        self.config = config
        self._user_msg_times: Dict[int, deque] = defaultdict(lambda: deque(maxlen=6))

    def should_moderate(self, message: discord.Message) -> Tuple[bool, str]:
        if not self.config.enabled:
            return False, ""
        if message.author.bot or not message.guild:
            return False, ""

        content = message.content or ""

        # 1. Anti-Invite
        if self.config.anti_invite and INVITE_REGEX.search(content):
            return True, "Публикация сторонних ссылок-приглашений Discord (Anti-Invite)"

        # 2. Anti-Spam / Flood (More than 4 messages within 3 seconds)
        if self.config.anti_spam:
            now = datetime.now(timezone.utc).timestamp()
            q = self._user_msg_times[message.author.id]
            q.append(now)
            if len(q) >= 4 and (now - q[0]) < 3.0:
                q.clear()
                return True, "Слишком частая отправка сообщений (Anti-Spam / Flood)"

        # 3. Anti-Caps (Length > 10 and uppercase ratio > 70%)
        if self.config.anti_caps and len(content) > 10:
            letters = [c for c in content if c.isalpha()]
            if letters:
                caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if caps_ratio > 0.70:
                    return True, "Злоупотребление CAPS LOCK (Anti-Caps)"

        # 4. Bad Words Filter
        if self.config.bad_words:
            lower_content = content.lower()
            for bw in self.config.bad_words:
                clean_bw = bw.strip().lower()
                if clean_bw and clean_bw in lower_content:
                    return True, f"Запрещённое слово в сообщении: `{clean_bw}`"

        return False, ""

    async def execute_moderation(self, message: discord.Message, reason: str, client: discord.Client):
        try:
            await message.delete()
        except Exception:
            pass

        # Warn user
        if self.config.warn_in_chat:
            try:
                warn_msg = await message.channel.send(
                    f"⚠️ {message.author.mention}, ваше сообщение удалено: **{reason}**."
                )
                await asyncio.sleep(6)
                await warn_msg.delete()
            except Exception:
                pass

        # Send audit log embed
        if self.config.log_channel_id:
            try:
                log_ch = client.get_channel(self.config.log_channel_id) or await client.fetch_channel(self.config.log_channel_id)
                if log_ch and isinstance(log_ch, discord.TextChannel):
                    log_embed = discord.Embed(
                        title="🛡️ PRISM AutoMod • Нарушение правил",
                        color=0xED4245,
                        timestamp=datetime.now(timezone.utc),
                    )
                    log_embed.add_field(name="Пользователь", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
                    log_embed.add_field(name="Канал", value=message.channel.mention, inline=True)
                    log_embed.add_field(name="Причина", value=f"`{reason}`", inline=False)
                    if message.content:
                        log_embed.add_field(name="Текст сообщения", value=f"```{message.content[:800]}```", inline=False)
                    await log_ch.send(embed=log_embed)
            except Exception as le:
                console.print(f"[#ED4245]Ошибка отправки лога модерации: {le}[/]")


# --- 3. AI Assistant Engine ---

class AIAssistantEngine:
    def __init__(self, config: AIAssistantConfig):
        self.config = config
        self._history: Dict[int, List[Dict[str, str]]] = defaultdict(list)

    def should_reply(self, message: discord.Message, client: discord.Client) -> bool:
        if not self.config.enabled or not self.config.api_key:
            return False
        if message.author.bot:
            return False

        mode = self.config.trigger_mode
        channel_match = (self.config.channel_id and message.channel.id == self.config.channel_id)
        mention_match = client.user in message.mentions if client.user else False

        if mode == "channel":
            return channel_match
        elif mode == "mention":
            return mention_match
        elif mode == "both":
            return channel_match or mention_match
        return False

    async def generate_response(self, user_id: int, user_prompt: str) -> str:
        """Asynchronously calls AI API based on configured provider."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_generate, user_id, user_prompt)

    def _sync_generate(self, user_id: int, prompt: str) -> str:
        provider = self.config.provider.lower()
        api_key = self.config.api_key.strip()
        model = self.config.model.strip() or "gemini-1.5-flash"
        sys_prompt = self.config.system_prompt or "You are a helpful Discord assistant."

        # Keep last 6 exchanges
        user_hist = self._history[user_id][-6:]

        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            contents = []
            for h in user_hist:
                contents.append({"role": h["role"], "parts": [{"text": h["text"]}]})
            contents.append({"role": "user", "parts": [{"text": f"System context: {sys_prompt}\nUser: {prompt}"}]})

            payload = {"contents": contents}
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    cand = res_json.get("candidates", [])
                    if cand:
                        reply = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        self._history[user_id].append({"role": "user", "text": prompt})
                        self._history[user_id].append({"role": "model", "text": reply})
                        return reply.strip()
            except Exception as e:
                return f"⚠️ Ошибка Gemini AI: {e}"

        else:
            # OpenAI / OpenRouter / Groq compatible endpoint
            if provider == "openrouter":
                url = "https://openrouter.ai/api/v1/chat/completions"
            elif provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
            else:
                url = "https://api.openai.com/v1/chat/completions"

            messages = [{"role": "system", "content": sys_prompt}]
            for h in user_hist:
                r = "assistant" if h["role"] in ("assistant", "model") else "user"
                messages.append({"role": r, "content": h["text"]})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 800,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    choices = res_json.get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "")
                        self._history[user_id].append({"role": "user", "text": prompt})
                        self._history[user_id].append({"role": "assistant", "text": reply})
                        return reply.strip()
            except Exception as e:
                return f"⚠️ Ошибка AI API ({provider}): {e}"

        return "Не удалось получить ответ от нейросети."


# --- 4. Welcomer Engine ---

class WelcomerEngine:
    def __init__(self, config: WelcomerConfig):
        self.config = config

    async def handle_member_join(self, member: discord.Member):
        if not self.config.enabled:
            return

        # 1. Auto-Role
        if self.config.auto_role_id and member.guild:
            role = member.guild.get_role(self.config.auto_role_id)
            if role:
                try:
                    await member.add_roles(role, reason="PRISM Welcomer Auto-Role")
                except Exception as e:
                    console.print(f"[#ED4245]Ошибка выдачи авто-роли: {escape(str(e))}[/]")

        # 2. Welcome Message
        if self.config.welcome_channel_id and member.guild:
            ch = member.guild.get_channel(self.config.welcome_channel_id)
            if ch and isinstance(ch, discord.TextChannel):
                title = self.config.welcome_title.replace("{user}", member.display_name).replace("{guild}", member.guild.name)
                desc = self.config.welcome_desc.replace("{user}", member.mention).replace("{guild}", member.guild.name)
                emb = discord.Embed(
                    title=title,
                    description=desc,
                    color=self.config.welcome_color,
                    timestamp=datetime.now(timezone.utc),
                )
                if member.display_avatar:
                    emb.set_thumbnail(url=member.display_avatar.url)
                emb.set_footer(text=f"Участник #{member.guild.member_count}")
                try:
                    await ch.send(content=member.mention, embed=emb)
                except Exception as e:
                    console.print(f"[#ED4245]Ошибка отправки приветствия: {escape(str(e))}[/]")


# --- 5. Moderation Suite Engine ---

class ModerationEngine:
    """
    Full Discord moderation engine.
    Supports actions from the PRISM operator console and Discord chat commands (!ban, !mute, etc.)
    """
    @staticmethod
    async def ban_user(guild: discord.Guild, user_id: int, reason: str = "Бан через PRISM", delete_days: int = 0) -> Tuple[bool, str]:
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if member:
                await guild.ban(member, reason=reason, delete_message_days=delete_days)
                return True, f"@{member.name} (ID: {user_id}) забанен на сервере. Причина: {reason}"
            else:
                user_obj = discord.Object(id=user_id)
                await guild.ban(user_obj, reason=reason, delete_message_days=delete_days)
                return True, f"Пользователь с ID {user_id} забанен (Hackban). Причина: {reason}"
        except discord.Forbidden:
            return False, "Недостаточно прав (роль бота ниже цели или нет права Ban Members)."
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def unban_user(guild: discord.Guild, user_id: int, reason: str = "Разбан через PRISM") -> Tuple[bool, str]:
        try:
            user_obj = discord.Object(id=user_id)
            await guild.unban(user_obj, reason=reason)
            return True, f"Пользователь ID {user_id} успешно разбанен."
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def kick_user(guild: discord.Guild, user_id: int, reason: str = "Кик через PRISM") -> Tuple[bool, str]:
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if not member:
                return False, f"Пользователь {user_id} не найден на сервере."
            await member.kick(reason=reason)
            return True, f"@{member.name} (ID: {user_id}) успешно выгнан с сервера."
        except discord.Forbidden:
            return False, "Недостаточно прав для кика этого пользователя."
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def timeout_user(guild: discord.Guild, user_id: int, minutes: int = 10, reason: str = "Таймаут через PRISM") -> Tuple[bool, str]:
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if not member:
                return False, f"Пользователь {user_id} не найден на сервере."
            until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            await member.timeout(until, reason=reason)
            return True, f"@{member.name} отправлен в таймаут на {minutes} мин. (до {until.strftime('%H:%M:%S UTC')})."
        except discord.Forbidden:
            return False, "Недостаточно прав для таймаута этого пользователя."
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def untimeout_user(guild: discord.Guild, user_id: int) -> Tuple[bool, str]:
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if not member:
                return False, f"Пользователь {user_id} не найден на сервере."
            await member.timeout(None, reason="Досрочное снятие таймаута")
            return True, f"Таймаут с @{member.name} успешно снят."
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def purge_channel(channel: discord.TextChannel, amount: int = 10) -> Tuple[bool, int, str]:
        try:
            deleted = await channel.purge(limit=amount)
            return True, len(deleted), f"Очищено {len(deleted)} сообщений в канале #{channel.name}."
        except discord.Forbidden:
            return False, 0, "Недостаточно прав (Manage Messages) для очистки."
        except Exception as e:
            return False, 0, str(e)

    @staticmethod
    async def set_slowmode(channel: discord.TextChannel, seconds: int = 0) -> Tuple[bool, str]:
        try:
            await channel.edit(slowmode_delay=seconds)
            if seconds > 0:
                return True, f"Медленный режим в #{channel.name} установлен: {seconds} сек."
            return True, f"Медленный режим в #{channel.name} отключён."
        except Exception as e:
            return False, str(e)


# --- 6. Ticket Support Engine ---

class TicketEngine:
    def __init__(self, config: TicketConfig):
        self.config = config

    @staticmethod
    def build_ticket_panel_embed(title: str = "", desc: str = "") -> discord.Embed:
        emb = discord.Embed(
            title=title or "📩 Служба поддержки и тикеты",
            description=desc or "Возник вопрос или нужна помощь? Создайте приватное обращение с помощью меню ниже:",
            color=0xEBAF8E,
        )
        emb.set_footer(text="PRISM Ticket System • Нажмите на кнопку или выберите тему")
        return emb

    @staticmethod
    def build_ticket_panel_view(use_select: bool = False) -> discord.ui.View:
        view = discord.ui.View(timeout=None)
        if use_select:
            opts = [
                discord.SelectOption(label="Общий вопрос", value="ticket_question", description="Вопрос по серверу или правилам", emoji="❓"),
                discord.SelectOption(label="Жалоба на игрока", value="ticket_report", description="Нарушение правил другим участником", emoji="⚠️"),
                discord.SelectOption(label="Донат и покупки", value="ticket_donate", description="Вопросы по оплате или бонусам", emoji="💎"),
                discord.SelectOption(label="Техническая поддержка", value="ticket_tech", description="Баги, технические проблемы", emoji="🛠️"),
            ]
            view.add_item(discord.ui.Select(
                custom_id="prism_ticket_select",
                placeholder="Выберите категорию тикета...",
                options=opts,
                row=0,
            ))
        else:
            view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Создать тикет",
                emoji="📩",
                custom_id="prism_open_ticket",
                row=0,
            ))
        return view

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        category: str = "Общий вопрос",
        topic: str = "",
        details: str = "",
    ) -> Optional[discord.Thread]:
        ch = interaction.channel
        if not isinstance(ch, (discord.TextChannel, discord.ForumChannel)):
            return None
        user = interaction.user
        thread_name = f"тикет-{user.name[:14]}"
        try:
            is_private = ch.guild.premium_tier >= 2
            try:
                thread = await ch.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.private_thread if is_private else discord.ChannelType.public_thread,
                    auto_archive_duration=1440,
                )
            except Exception:
                thread = await ch.create_thread(name=thread_name, auto_archive_duration=1440)

            try:
                await thread.add_user(user)
            except Exception:
                pass

            staff_mention = f"<@&{self.config.support_role_id}> " if self.config.support_role_id else ""

            close_view = discord.ui.View(timeout=None)
            close_view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="🔒 Закрыть тикет",
                custom_id="prism_close_ticket",
            ))

            t_embed = discord.Embed(
                title=f"📩 Обращение в поддержку: {category}",
                description=f"Здравствуйте, {user.mention}!\nАдминистрация сервера скоро ответит вам в этом чате.",
                color=0x57F287,
                timestamp=datetime.now(timezone.utc),
            )
            if topic:
                t_embed.add_field(name="📋 Тема обращения", value=topic, inline=False)
            if details:
                t_embed.add_field(name="📝 Описание проблемы", value=details, inline=False)
            t_embed.set_footer(text="Чтобы завершить диалог и сохранить стенограмму, нажмите кнопку закрытия ниже")
            await thread.send(content=f"{user.mention} {staff_mention}", embed=t_embed, view=close_view)
            return thread
        except Exception as e:
            console.print(f"[#ED4245]Ошибка создания тикета: {escape(str(e))}[/]")
            return None

    @staticmethod
    async def generate_ticket_transcript(thread: discord.Thread) -> Tuple[str, io.BytesIO]:
        """Generates an HTML transcript file of all messages in the thread."""
        messages = []
        try:
            async for m in thread.history(limit=500, oldest_first=True):
                messages.append(m)
        except Exception:
            pass

        def esc(s: str) -> str:
            return html.escape(s or "")

        lines = [
            "<!DOCTYPE html>",
            "<html lang='ru'>",
            "<head>",
            "<meta charset='utf-8'>",
            f"<title>Транскрипт тикета {esc(thread.name)}</title>",
            "<style>",
            "body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background: #313338; color: #dbdee1; margin: 0; padding: 24px; }",
            ".header { border-bottom: 2px solid #3f4147; padding-bottom: 16px; margin-bottom: 24px; }",
            ".header h1 { margin: 0; color: #ffffff; font-size: 24px; }",
            ".header p { margin: 6px 0 0; color: #949ba4; font-size: 14px; }",
            ".msg { display: flex; margin-bottom: 18px; padding: 6px 10px; border-radius: 6px; }",
            ".msg:hover { background: #2b2d31; }",
            ".avatar { width: 42px; height: 42px; border-radius: 50%; margin-right: 14px; background: #5865F2; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; flex-shrink: 0; }",
            ".content { flex: 1; }",
            ".meta { display: flex; align-items: baseline; margin-bottom: 4px; }",
            ".author { font-weight: 600; color: #f2f3f5; font-size: 15px; margin-right: 10px; }",
            ".time { font-size: 12px; color: #949ba4; }",
            ".text { font-size: 14px; line-height: 1.45; color: #dbdee1; white-space: pre-wrap; word-break: break-word; }",
            ".embed { background: #2b2d31; border-left: 4px solid #57F287; padding: 12px 16px; border-radius: 6px; margin-top: 8px; max-width: 550px; }",
            ".embed-title { font-weight: 600; color: #ffffff; margin-bottom: 6px; }",
            ".embed-desc { font-size: 13px; color: #dbdee1; white-space: pre-wrap; }",
            ".field { margin-top: 8px; }",
            ".field-name { font-weight: 600; font-size: 13px; color: #ffffff; }",
            ".field-val { font-size: 13px; color: #dbdee1; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='header'>",
            f"<h1>📑 Стенограмма тикета: #{esc(thread.name)}</h1>",
            f"<p>Сервер: {esc(thread.guild.name)} • Сообщений: {len(messages)} • Дата экспорта: {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M:%S UTC')}</p>",
            "</div>",
            "<div class='chat'>",
        ]

        for m in messages:
            author_name = esc(m.author.name)
            initials = esc(author_name[:2].upper())
            time_str = m.created_at.strftime("%d.%m.%Y %H:%M")
            txt = esc(m.content or "")

            lines.append("<div class='msg'>")
            if m.author.display_avatar:
                lines.append(f"<img class='avatar' src='{m.author.display_avatar.url}' alt='{initials}'>")
            else:
                lines.append(f"<div class='avatar'>{initials}</div>")

            lines.append("<div class='content'>")
            lines.append(f"<div class='meta'><span class='author'>{author_name}</span><span class='time'>{time_str}</span></div>")
            if txt:
                lines.append(f"<div class='text'>{txt}</div>")

            for emb in m.embeds:
                color_hex = f"#{emb.color.value:06x}" if emb.color else "#57F287"
                lines.append(f"<div class='embed' style='border-left-color: {color_hex};'>")
                if emb.title:
                    lines.append(f"<div class='embed-title'>{esc(emb.title)}</div>")
                if emb.description:
                    lines.append(f"<div class='embed-desc'>{esc(emb.description)}</div>")
                for fld in emb.fields:
                    lines.append(f"<div class='field'><div class='field-name'>{esc(fld.name)}</div><div class='field-val'>{esc(fld.value)}</div></div>")
                lines.append("</div>")

            lines.append("</div></div>")

        lines.append("</div></body></html>")
        full_html = "\n".join(lines)

        from core.storage import TRANSCRIPTS_DIR
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\u0400-\u04FF]', '_', thread.name)
        filename = f"transcript-{clean_name}-{int(datetime.now().timestamp())}.html"
        file_path = TRANSCRIPTS_DIR / filename
        try:
            file_path.write_text(full_html, encoding="utf-8")
        except Exception:
            pass

        buf = io.BytesIO(full_html.encode("utf-8"))
        buf.seek(0)
        return filename, buf


class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_engine: TicketEngine, category: str = "Общий вопрос"):
        super().__init__(title=f"Тикет: {category[:35]}")
        self.ticket_engine = ticket_engine
        self.category = category

        self.topic_input = discord.ui.TextInput(
            label="Тема обращения",
            placeholder="Кратко суть вопроса (например: Вопрос по серверу)...",
            max_length=100,
            required=True,
        )
        self.details_input = discord.ui.TextInput(
            label="Подробное описание проблемы",
            style=discord.TextStyle.paragraph,
            placeholder="Опишите подробно вашу проблему, чтобы администрация могла сразу помочь...",
            max_length=1500,
            required=False,
        )
        self.add_item(self.topic_input)
        self.add_item(self.details_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        topic = str(self.topic_input.value).strip()
        details = str(self.details_input.value).strip()
        thread = await self.ticket_engine.create_ticket(
            interaction,
            category=self.category,
            topic=topic,
            details=details,
        )
        if thread:
            await interaction.followup.send(f"🎫 Тикет успешно создан: {thread.mention}", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Не удалось создать тикет (проверьте права бота на создание веток).", ephemeral=True)
