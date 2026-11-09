"""
PRISM - Interactive Discord Bot & Scenario Engine
Handles multi-bot dispatching, real role assignment on verify buttons,
automated timed giveaways, and live operator dashboard.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone, timedelta
import os
import random
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

import discord
from rich.console import Console
from rich.markup import escape

from core.embed import Embed, Button, SelectMenu, SelectOption
from core.storage import StorageManager
from core.i18n import t
from core.bot_engines import (
    AutoModEngine,
    AIAssistantEngine,
    WelcomerEngine,
    TicketEngine,
    ModerationEngine,
    BotEngineSettings,
)

console = Console()
storage = StorageManager()


def create_discord_embed(embed: Embed) -> discord.Embed:
    """Converts PRISM internal Embed dataclass into a discord.py Embed object."""
    desc = embed.description.replace("\\n", "\n") if embed.description else None
    title = embed.title.replace("\\n", "\n") if embed.title else None
    d_embed = discord.Embed(
        title=title,
        description=desc,
        color=embed.color,
        url=embed.url or None,
    )
    if embed.author_name:
        d_embed.set_author(
            name=embed.author_name.replace("\\n", "\n"),
            url=embed.author_url or None,
            icon_url=embed.author_icon_url or None,
        )
    if embed.thumbnail_url:
        d_embed.set_thumbnail(url=embed.thumbnail_url)
    if embed.image_url:
        d_embed.set_image(url=embed.image_url)
    if embed.footer_text or embed.footer_icon_url:
        d_embed.set_footer(
            text=(embed.footer_text or "PRISM Interactive Studio").replace("\\n", "\n"),
            icon_url=embed.footer_icon_url or None,
        )
    if embed.timestamp:
        d_embed.timestamp = datetime.now(timezone.utc)

    for fld in embed.fields:
        clean_name = fld.name.replace("\\n", "\n")
        clean_val = fld.value.replace("\\n", "\n")
        d_embed.add_field(name=clean_name, value=clean_val, inline=fld.inline)

    return d_embed


def create_discord_view(buttons: List[Button], select_menu: Optional[SelectMenu] = None) -> discord.ui.View:
    """Converts PRISM buttons and Select Menus into a discord.ui.View."""
    view = discord.ui.View(timeout=None)
    for b in buttons[:5]:
        style_enum = discord.ButtonStyle(b.style)
        if b.style == 5 or b.action_type == "link":
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=b.label,
                    url=b.url or "https://discord.com",
                    emoji=b.emoji or None,
                    row=0,
                )
            )
        else:
            view.add_item(
                discord.ui.Button(
                    style=style_enum,
                    label=b.label,
                    custom_id=b.custom_id,
                    emoji=b.emoji or None,
                    row=0,
                )
            )

    if select_menu and select_menu.options:
        discord_options = []
        for opt in select_menu.options[:25]:
            discord_options.append(
                discord.SelectOption(
                    label=opt.label[:100],
                    value=opt.value[:100],
                    description=opt.description[:100] if opt.description else None,
                    emoji=opt.emoji or None,
                )
            )
        view.add_item(
            discord.ui.Select(
                custom_id=select_menu.custom_id,
                placeholder=select_menu.placeholder[:150] or "Выберите вариант...",
                min_values=select_menu.min_values,
                max_values=min(select_menu.max_values, len(discord_options)),
                options=discord_options,
                row=1 if buttons else 0,
            )
        )
    return view


async def async_send_via_bot(
    token: str,
    channel_id: int,
    embed: Embed,
    content: str = "",
) -> Tuple[int, int, str]:
    """
    Connects with Bot token, dispatches embed, buttons and select menus to channel.
    Returns (message_id, channel_id, bot_name).
    """
    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    result_queue: asyncio.Queue = asyncio.Queue()

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                await result_queue.put(("error", f"Канал с ID {channel_id} не найден или это не текстовый канал."))
                await client.close()
                return

            d_embed = create_discord_embed(embed)
            has_components = bool(embed.buttons or (embed.select_menu and embed.select_menu.options))
            view = create_discord_view(embed.buttons, embed.select_menu) if has_components else None

            msg = await channel.send(
                content=content or None,
                embed=d_embed,
                view=view,
            )
            await result_queue.put(("success", (msg.id, channel.id, client.user.name if client.user else "Bot")))
        except Exception as e:
            await result_queue.put(("error", str(e)))
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=25.0)
    except asyncio.TimeoutError:
        return 0, 0, "Timeout: не удалось подключиться к Discord за 25 секунд."
    except Exception as e:
        return 0, 0, str(e)

    status, payload = await result_queue.get()
    if status == "success":
        return payload[0], payload[1], payload[2]
    else:
        raise RuntimeError(str(payload))


def send_via_bot(token: str, channel_id: int, embed: Embed, content: str = "") -> Tuple[int, int, str]:
    """Synchronous wrapper for sending interactive embed via bot token."""
    return asyncio.run(async_send_via_bot(token, channel_id, embed, content))


async def async_delete_bot_message(token: str, channel_id: int, message_id: int) -> Tuple[bool, str]:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    result_queue: asyncio.Queue = asyncio.Queue()

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                await result_queue.put((False, f"Канал с ID {channel_id} не найден."))
                await client.close()
                return
            msg = await channel.fetch_message(message_id)
            await msg.delete()
            await result_queue.put((True, f"Сообщение {message_id} успешно удалено ботом."))
        except Exception as e:
            await result_queue.put((False, str(e)))
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=20.0)
    except Exception as e:
        return False, str(e)

    return await result_queue.get()


def delete_bot_message(token: str, channel_id: int, message_id: int) -> Tuple[bool, str]:
    """Synchronous deletion of a Discord message sent by a bot."""
    return asyncio.run(async_delete_bot_message(token, channel_id, message_id))


async def async_edit_bot_message(token: str, channel_id: int, message_id: int, embed: Embed, content: str = "") -> Tuple[bool, str]:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    result_queue: asyncio.Queue = asyncio.Queue()

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                await result_queue.put((False, f"Канал с ID {channel_id} не найден."))
                await client.close()
                return
            msg = await channel.fetch_message(message_id)
            d_embed = create_discord_embed(embed)
            has_components = bool(embed.buttons or (embed.select_menu and embed.select_menu.options))
            view = create_discord_view(embed.buttons, embed.select_menu) if has_components else None
            await msg.edit(content=content or None, embed=d_embed, view=view)
            await result_queue.put((True, f"Сообщение {message_id} успешно обновлено."))
        except Exception as e:
            await result_queue.put((False, str(e)))
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=20.0)
    except Exception as e:
        return False, str(e)

    return await result_queue.get()


def edit_bot_message(token: str, channel_id: int, message_id: int, embed: Embed, content: str = "") -> Tuple[bool, str]:
    """Synchronous update of a Discord message sent by a bot."""
    return asyncio.run(async_edit_bot_message(token, channel_id, message_id, embed, content))


async def async_deploy_ticket_panel(
    token: str,
    channel_id: int,
    title: str = "",
    desc: str = "",
    use_select: bool = False,
    support_role_id: Optional[int] = None,
) -> Tuple[bool, str]:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    result_queue: asyncio.Queue = asyncio.Queue()

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                await result_queue.put((False, f"Канал с ID {channel_id} не найден или это не текстовый канал."))
                await client.close()
                return

            from core.bot_engines import TicketConfig, TicketEngine
            t_cfg = TicketConfig(enabled=True, support_role_id=support_role_id)
            t_engine = TicketEngine(t_cfg)
            d_embed = t_engine.build_ticket_panel_embed(title, desc)
            view = t_engine.build_ticket_panel_view(use_select)

            msg = await channel.send(embed=d_embed, view=view)
            await result_queue.put((True, f"Панель тикетов успешно развёрнута в #{channel.name} (ID: {msg.id})!"))
        except Exception as e:
            await result_queue.put((False, str(e)))
        finally:
            await client.close()

    try:
        await asyncio.wait_for(client.start(token), timeout=25.0)
    except Exception as e:
        return False, str(e)

    return await result_queue.get()


def deploy_ticket_panel(
    token: str,
    channel_id: int,
    title: str = "",
    desc: str = "",
    use_select: bool = False,
    support_role_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """Synchronous helper to deploy a ticket panel into a Discord channel."""
    return asyncio.run(async_deploy_ticket_panel(token, channel_id, title, desc, use_select, support_role_id))


class PrismInteractiveListener:
    """
    Full-featured interactive listener:
    - Real role assignment for verify buttons and select menus
    - Participant tracking and automated timer ending for giveaways
    - Autonomous engines: AutoMod, AI Chat Assistant, Welcomer, Tickets
    - Real-time in-chat and terminal moderation suite
    """

    def __init__(self, token: str, embed: Optional[Embed] = None, channel_id: Optional[int] = None, bot_alias: str = "DefaultBot"):
        self.token = token.strip()
        self.embed = embed
        self.channel_id = channel_id
        self.bot_alias = bot_alias
        self.client: Optional[discord.Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.target_buttons: Dict[str, Button] = {}
        self.select_menu: Optional[SelectMenu] = embed.select_menu if embed else None

        if embed and embed.buttons:
            for b in embed.buttons:
                if b.custom_id:
                    self.target_buttons[b.custom_id] = b

        # Load Bot Engines configuration
        raw_cfg = storage.get_bot_engines_config(self.bot_alias)
        self.engine_settings = BotEngineSettings.from_dict(raw_cfg) if raw_cfg else BotEngineSettings(bot_alias=self.bot_alias)
        self.automod = AutoModEngine(self.engine_settings.automod)
        self.ai = AIAssistantEngine(self.engine_settings.ai)
        self.welcomer = WelcomerEngine(self.engine_settings.welcomer)
        self.tickets = TicketEngine(self.engine_settings.tickets)
        self.mod = ModerationEngine()

    async def _timer_worker(self):
        """Background task checking if any active timed giveaway should finish."""
        while self.is_running:
            try:
                active_g = storage.list_active_giveaways()
                now_iso = datetime.now(timezone.utc).isoformat()
                for g in active_g:
                    end_time = g.get("end_time")
                    cid = g.get("custom_id")
                    if end_time and end_time <= now_iso and cid:
                        participants = g.get("participants", [])
                        prize = g.get("prize", "Discord Nitro")
                        w_count = int(g.get("winners_count", 1))

                        if participants:
                            winners = random.sample(participants, min(len(participants), w_count))
                        else:
                            winners = []

                        # Mark ended so it won't roll again
                        storage.mark_giveaway_ended(cid, winners)

                        # Announce in Discord channel if bot connected
                        ch_id = g.get("channel_id") or self.channel_id
                        if ch_id and self.client and not self.client.is_closed():
                            try:
                                ch = self.client.get_channel(ch_id) or await self.client.fetch_channel(ch_id)
                                if ch and winners:
                                    mentions = ", ".join(f"<@{w['user_id']}>" for w in winners)
                                    announcement = t("bot_giveaway_ended_title", prize=prize, mentions=mentions)
                                    await ch.send(announcement)
                                elif ch and not winners:
                                    await ch.send(t("bot_giveaway_ended_empty"))
                            except Exception as ann_err:
                                console.print(f"[#ED4245]Ошибка отправки объявления победителя: {escape(str(ann_err))}[/]")

                        # Console announcement
                        console.print(f"\n[bold #57F287]🏆 ТАЙМЕР РОЗЫГРЫША ИСТЁК![/]")
                        for w in winners:
                            console.print(f"  [bold white]Победитель:[/] @{w['username']} (ID: {w['user_id']}) • Приз: {prize}")
            except Exception:
                pass
            await asyncio.sleep(5.0)

    def _setup_events(self, client: discord.Client):
        @client.event
        async def on_ready():
            console.print(f"\n[bold #57F287]✓ PRISM Слушатель активен![/] Бот: [bold white]@{client.user}[/bold white]")

            engines_status = []
            if self.automod.config.enabled:
                engines_status.append("[#57F287]AutoMod: ON[/]")
            if self.ai.config.enabled:
                engines_status.append(f"[#00D9FF]AI ({self.ai.config.provider}): ON[/]")
            if self.welcomer.config.enabled:
                engines_status.append("[#EBAF8E]Welcomer: ON[/]")
            if self.tickets.config.enabled:
                engines_status.append("[#5865F2]Tickets: ON[/]")

            if engines_status:
                console.print(f"  [bold white]Активные модули:[/] {' • '.join(engines_status)}")
            console.print("[#8C8C8C]Ожидание взаимодействий, тикетов и команд в Discord...[/#8C8C8C]\n")
            asyncio.create_task(self._timer_worker())

        @client.event
        async def on_message(message: discord.Message):
            if not client or message.author.id == client.user.id:
                return

            # 1. Moderation in-chat commands (!ban, !kick, !mute, !clear, etc.)
            if message.content.startswith("!") and message.guild and isinstance(message.author, discord.Member):
                perms = message.author.guild_permissions
                if perms.administrator or perms.manage_messages or perms.ban_members or perms.kick_members:
                    raw = message.content[1:].strip()
                    parts = raw.split()
                    if parts:
                        cmd = parts[0].lower()
                        args = parts[1:]

                        async def send_mod_reply(txt: str):
                            try:
                                await message.reply(txt, mention_author=True)
                            except Exception:
                                pass

                        def parse_user_id(val: str) -> Optional[int]:
                            clean = val.replace("<@", "").replace(">", "").replace("!", "")
                            return int(clean) if clean.isdigit() else None

                        if cmd in ("ban", "бан"):
                            if not args:
                                await send_mod_reply("Использование: `!ban @user [причина]`")
                                return
                            uid = parse_user_id(args[0])
                            reason = " ".join(args[1:]) if len(args) > 1 else "Бан через команду !ban"
                            if uid:
                                ok, msg = await ModerationEngine.ban_user(message.guild, uid, reason)
                                await send_mod_reply(f"🛡️ {msg}")
                            return

                        elif cmd in ("unban", "разбан"):
                            if not args:
                                await send_mod_reply("Использование: `!unban <user_id>`")
                                return
                            uid = parse_user_id(args[0])
                            if uid:
                                ok, msg = await ModerationEngine.unban_user(message.guild, uid)
                                await send_mod_reply(f"🛡️ {msg}")
                            return

                        elif cmd in ("kick", "кик"):
                            if not args:
                                await send_mod_reply("Использование: `!kick @user [причина]`")
                                return
                            uid = parse_user_id(args[0])
                            reason = " ".join(args[1:]) if len(args) > 1 else "Кик через команду !kick"
                            if uid:
                                ok, msg = await ModerationEngine.kick_user(message.guild, uid, reason)
                                await send_mod_reply(f"🛡️ {msg}")
                            return

                        elif cmd in ("mute", "мут", "timeout"):
                            if not args:
                                await send_mod_reply("Использование: `!mute @user [минуты] [причина]`")
                                return
                            uid = parse_user_id(args[0])
                            mins = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
                            reason = " ".join(args[2:]) if len(args) > 2 else "Таймаут через !mute"
                            if uid:
                                ok, msg = await ModerationEngine.timeout_user(message.guild, uid, mins, reason)
                                await send_mod_reply(f"🛡️ {msg}")
                            return

                        elif cmd in ("unmute", "размут"):
                            if not args:
                                await send_mod_reply("Использование: `!unmute @user`")
                                return
                            uid = parse_user_id(args[0])
                            if uid:
                                ok, msg = await ModerationEngine.untimeout_user(message.guild, uid)
                                await send_mod_reply(f"🛡️ {msg}")
                            return

                        elif cmd in ("clear", "purge", "очистить"):
                            count = int(args[0]) if args and args[0].isdigit() else 10
                            if isinstance(message.channel, discord.TextChannel):
                                try:
                                    await message.delete()
                                except Exception:
                                    pass
                                ok, deleted_count, msg = await ModerationEngine.purge_channel(message.channel, count)
                                cfm = await message.channel.send(f"🧹 Очищено {deleted_count} сообщений.")
                                await asyncio.sleep(4)
                                try:
                                    await cfm.delete()
                                except Exception:
                                    pass
                            return

                        elif cmd in ("warn", "варн"):
                            if not args:
                                await send_mod_reply("Использование: `!warn @user [причина]`")
                                return
                            uid = parse_user_id(args[0])
                            reason = " ".join(args[1:]) if len(args) > 1 else "Нарушение правил"
                            if uid:
                                total = storage.add_warn(uid, reason, moderator=message.author.name)
                                await send_mod_reply(f"⚠️ Пользователю <@{uid}> выдано предупреждение #{total}! Причина: {reason}")
                            return

                        elif cmd in ("slowmode", "медленный"):
                            sec = int(args[0]) if args and args[0].isdigit() else 0
                            if isinstance(message.channel, discord.TextChannel):
                                ok, msg = await ModerationEngine.set_slowmode(message.channel, sec)
                                await send_mod_reply(f"⏱️ {msg}")
                            return

                        elif cmd in ("modhelp", "help"):
                            help_text = (
                                "**🛡️ Команды модерации PRISM:**\n"
                                "`!ban @user [причина]` — Забанить пользователя\n"
                                "`!unban <id>` — Разбанить пользователя\n"
                                "`!kick @user [причина]` — Выгнать с сервера\n"
                                "`!mute @user [мин] [причина]` — Таймаут (мут)\n"
                                "`!unmute @user` — Снять таймаут\n"
                                "`!clear [кол-во]` — Очистить сообщения\n"
                                "`!warn @user [причина]` — Выдать предупреждение\n"
                                "`!slowmode [сек]` — Установить задержку чата"
                            )
                            await send_mod_reply(help_text)
                            return

            # 2. AutoMod
            mod_hit, reason = self.automod.should_moderate(message)
            if mod_hit:
                time_str = datetime.now().strftime("%H:%M:%S")
                console.print(f"  [#EBAF8E][{time_str}][/#EBAF8E] [#ED4245]🛡️ AutoMod:[/#ED4245] @{message.author.name} -> {reason}")
                await self.automod.execute_moderation(message, reason, client)
                return

            # 3. AI Assistant
            if self.ai.should_reply(message, client):
                try:
                    async with message.channel.typing():
                        raw_prompt = message.content or ""
                        if client.user:
                            raw_prompt = raw_prompt.replace(f"<@{client.user.id}>", "").replace(f"<@!{client.user.id}>", "").strip()
                        if not raw_prompt:
                            raw_prompt = "Привет!"
                        reply = await self.ai.generate_response(message.author.id, raw_prompt)
                        time_str = datetime.now().strftime("%H:%M:%S")
                        console.print(f"  [#EBAF8E][{time_str}][/#EBAF8E] [#00D9FF]🧠 AI Ответ:[/#00D9FF] @{message.author.name}")
                        await message.reply(reply[:2000], mention_author=True)
                except Exception as aie:
                    console.print(f"[#ED4245]Ошибка ИИ: {escape(str(aie))}[/]")

        @client.event
        async def on_member_join(member: discord.Member):
            if self.welcomer.config.enabled:
                await self.welcomer.handle_member_join(member)

        @client.event
        async def on_interaction(interaction: discord.Interaction):
            if interaction.type != discord.InteractionType.component:
                return

            custom_id = interaction.data.get("custom_id", "")
            user = interaction.user
            username = f"{user.name}"
            user_id = user.id

            # --- 1. Ticket Open via Discord Modal (Native Popup Form) ---
            if custom_id in ("prism_open_ticket", "prism_create_ticket") or "ticket_btn" in custom_id:
                from core.bot_engines import TicketModal
                try:
                    await interaction.response.send_modal(TicketModal(self.tickets, category="Общий вопрос"))
                    return
                except Exception as modal_err:
                    console.print(f"[#ED4245]Ошибка показа модального окна: {escape(str(modal_err))}[/]")
                    # If modal fails, fall back to defer and direct creation

            # Immediately acknowledge other interactions to eliminate "Приложение не ответило вовремя"
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception:
                pass

            async def reply_ephemeral(text: str) -> None:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(text, ephemeral=True)
                    else:
                        await interaction.response.send_message(text, ephemeral=True)
                except Exception as send_err:
                    console.print(f"[#ED4245]Ошибка ответа: {escape(str(send_err))}[/]")

            # --- 2. Ticket Close with HTML Transcript & Log Forwarding ---
            if custom_id == "prism_close_ticket":
                if isinstance(interaction.channel, (discord.Thread, discord.TextChannel)):
                    await reply_ephemeral("🔒 Тикет сохраняется и архивируется... Формирую стенограмму.")
                    if isinstance(interaction.channel, discord.Thread):
                        try:
                            fname, buf = await TicketEngine.generate_ticket_transcript(interaction.channel)
                            file_thread = discord.File(buf, filename=fname)
                            await interaction.channel.send("📄 **Стенограмма диалога сохранена:**", file=file_thread)

                            log_id = self.tickets.config.log_channel_id or self.automod.config.log_channel_id
                            if log_id and client:
                                try:
                                    log_ch = client.get_channel(log_id) or await client.fetch_channel(log_id)
                                    if isinstance(log_ch, discord.TextChannel):
                                        buf.seek(0)
                                        log_file = discord.File(buf, filename=fname)
                                        await log_ch.send(
                                            f"📁 **Архив тикета:** `#{interaction.channel.name}` (Закрыл: @{interaction.user.name})",
                                            file=log_file,
                                        )
                                except Exception:
                                    pass

                            await interaction.channel.edit(archived=True, locked=True)
                        except Exception as e:
                            console.print(f"[#ED4245]Ошибка архивации тикета: {escape(str(e))}[/]")
                    return

            # --- 3. Select Menu Handling ---
            comp_type = interaction.data.get("component_type")
            if comp_type == 3 or (self.select_menu and custom_id == self.select_menu.custom_id) or "select" in custom_id:
                selected_vals = interaction.data.get("values", [])
                for val in selected_vals:
                    # Ticket category selection via modal or direct
                    if val.startswith("ticket_"):
                        category_map = {
                            "ticket_question": "❓ Общий вопрос",
                            "ticket_report": "⚠️ Жалоба на игрока",
                            "ticket_donate": "💎 Донат и покупки",
                            "ticket_tech": "🛠️ Техническая поддержка",
                        }
                        cat_name = category_map.get(val, val.replace("ticket_", "").replace("_", " ").title())
                        try:
                            thread = await self.tickets.create_ticket(interaction, cat_name)
                            if thread:
                                await reply_ephemeral(f"🎫 Тикет создан: {thread.mention}")
                            else:
                                await reply_ephemeral("⚠️ Не удалось создать тикет (проверьте права бота на создание веток).")
                        except Exception as err:
                            await reply_ephemeral(f"⚠️ Ошибка создания тикета: {escape(str(err))}")
                        return

                    # Role or action selection
                    matched_opt = None
                    if self.select_menu:
                        for opt in self.select_menu.options:
                            if opt.value == val:
                                matched_opt = opt
                                break

                    # Persistent component fallback
                    if not matched_opt:
                        opt_data = storage.get_component_option(val)
                        if opt_data:
                            class DummyOpt:
                                pass
                            matched_opt = DummyOpt()
                            matched_opt.action_type = opt_data.get("action_type")
                            matched_opt.role_id = opt_data.get("role_id")
                            matched_opt.response_text = opt_data.get("response_text")
                            matched_opt.label = opt_data.get("label", val)

                    # Dynamic role ID extraction fallback
                    if not matched_opt and ("role_" in val or "prism_role_" in val):
                        clean_id = re.sub(r'[^0-9]', '', val)
                        if clean_id:
                            class DummyOpt:
                                pass
                            matched_opt = DummyOpt()
                            matched_opt.action_type = "role"
                            matched_opt.role_id = clean_id
                            matched_opt.label = "Роль"

                    if matched_opt and matched_opt.action_type == "role":
                        role_id = matched_opt.role_id
                        if role_id and str(role_id).isdigit() and interaction.guild:
                            role = interaction.guild.get_role(int(role_id))
                            if role and isinstance(interaction.user, discord.Member):
                                if role in interaction.user.roles:
                                    await interaction.user.remove_roles(role, reason="PRISM Role Toggle")
                                    await reply_ephemeral(f"🗑️ С вас снята роль: **{role.name}**")
                                else:
                                    await interaction.user.add_roles(role, reason="PRISM Role Select")
                                    await reply_ephemeral(f"✅ Вам выдана роль: **{role.name}**")
                                return
                    elif matched_opt and matched_opt.action_type == "ticket":
                        thread = await self.tickets.create_ticket(interaction, matched_opt.label)
                        if thread:
                            await reply_ephemeral(f"🎫 Тикет создан: {thread.mention}")
                        return
                    elif matched_opt and matched_opt.response_text:
                        await reply_ephemeral(matched_opt.response_text)
                        return

                await reply_ephemeral(f"Вы выбрали вариант: {', '.join(selected_vals)}")
                return

            # --- 4. Button Actions ---
            btn_obj = self.target_buttons.get(custom_id)
            if not btn_obj:
                b_data = storage.get_component_button(custom_id)
                if b_data:
                    class DummyBtn:
                        pass
                    btn_obj = DummyBtn()
                    btn_obj.action_type = b_data.get("action_type")
                    btn_obj.role_id = b_data.get("role_id")
                    btn_obj.response_text = b_data.get("response_text")
                    btn_obj.prize = b_data.get("prize")
                    btn_obj.duration_minutes = b_data.get("duration_minutes", 0)

            action_type = btn_obj.action_type if btn_obj else ("giveaway" if "giveaway" in custom_id else ("verify" if "verify" in custom_id else "custom"))

            try:
                # Giveaway Scenario
                if "giveaway" in custom_id or action_type == "giveaway":
                    is_new, total_count = storage.add_giveaway_participant(custom_id, user_id, username)
                    if not is_new:
                        await reply_ephemeral(t("bot_giveaway_already", count=total_count))
                    else:
                        resp = (btn_obj.response_text if btn_obj and btn_obj.response_text else t("bot_giveaway_success"))
                        part_line = t("bot_giveaway_part_num", count=total_count)
                        await reply_ephemeral(f"{resp}{part_line}")
                        time_str = datetime.now().strftime("%H:%M:%S")
                        console.print(f"  [#EBAF8E][{time_str}][/#EBAF8E] [#57F287]+ Новый участник розыгрыша:[/#57F287] [bold white]@{username}[/bold white] (Всего: {total_count})")

                # Verification & Role Assignment
                elif "verify" in custom_id or action_type == "verify":
                    role_id = btn_obj.role_id if btn_obj else ""
                    role_assigned = False
                    role_name = ""

                    if role_id and role_id.isdigit() and interaction.guild:
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            role_name = role.name
                            try:
                                member = interaction.user
                                if isinstance(member, discord.Member):
                                    if role in member.roles:
                                        await reply_ephemeral(t("bot_verify_already", role=role.name))
                                        return
                                    await member.add_roles(role, reason="PRISM Verification")
                                    role_assigned = True
                            except discord.Forbidden:
                                await reply_ephemeral(t("bot_verify_forbidden", role=role.name))
                                return
                            except Exception as re:
                                console.print(f"[#ED4245]Ошибка выдачи роли: {escape(str(re))}[/]")

                    resp = (btn_obj.response_text if btn_obj and btn_obj.response_text else t("bot_verify_success"))
                    if role_assigned:
                        resp += t("bot_verify_role_granted", role=role_name)

                    await reply_ephemeral(resp)
                    time_str = datetime.now().strftime("%H:%M:%S")
                    extra = f" (Роль: {role_name})" if role_assigned else ""
                    console.print(f"  [#EBAF8E][{time_str}][/#EBAF8E] [#57F287]✓ Верификация:[/#57F287] [bold white]@{username}[/bold white]{extra}")

                # Custom Action
                else:
                    resp = (btn_obj.response_text if btn_obj and btn_obj.response_text else t("bot_action_success"))
                    await reply_ephemeral(resp)
                    time_str = datetime.now().strftime("%H:%M:%S")
                    console.print(f"  [#EBAF8E][{time_str}][/#EBAF8E] [#00D9FF]• Нажата кнопка:[/#00D9FF] [bold white]@{username}[/bold white] -> {custom_id}")

            except Exception as err:
                console.print(f"[bold #ED4245]Ошибка при обработке кнопки: {escape(str(err))}[/]")
                await reply_ephemeral(t("bot_action_processed"))

    async def run(self):
        use_privileged = True
        while True:
            intents = discord.Intents.default()
            intents.guilds = True
            intents.messages = True
            if use_privileged:
                try:
                    intents.message_content = True
                except Exception:
                    pass
                if self.welcomer.config.enabled:
                    try:
                        intents.members = True
                    except Exception:
                        pass

            self.client = discord.Client(intents=intents)
            self._setup_events(self.client)
            self.is_running = True

            try:
                await self.client.start(self.token)
                break
            except discord.errors.PrivilegedIntentsRequired:
                if use_privileged:
                    console.print("\n[bold #EBAF8E]⚠️ У бота не включены Privileged Intents в Discord Developer Portal.[/]")
                    console.print("[#57F287]✓ Автоматический переход в базовый безопасный режим (кнопки, списки, тикеты продолжают работать!)...[/#57F287]\n")
                    use_privileged = False
                    continue
                else:
                    break
            except Exception as e:
                console.print(f"[bold #ED4245]Ошибка подключения бота: {escape(str(e))}[/]")
                break
            finally:
                self.is_running = False

    def roll_winner(self, custom_id: str = "") -> Optional[Dict[str, Any]]:
        """Selects a random winner from participants and marks giveaway completed."""
        if not custom_id and self.target_buttons:
            for cid in self.target_buttons:
                if "giveaway" in cid:
                    custom_id = cid
                    break

        if not custom_id:
            active_g = storage.list_active_giveaways()
            if active_g:
                custom_id = active_g[0].get("custom_id", "")

        g_data = storage.get_giveaway(custom_id) if custom_id else None
        participants = g_data.get("participants", []) if g_data else []
        if not participants:
            return None
        winner = random.choice(participants)
        if custom_id:
            storage.mark_giveaway_ended(custom_id, [winner])
        return winner


_active_listener: Optional[PrismInteractiveListener] = None
_active_loop: Optional[asyncio.AbstractEventLoop] = None
_active_thread: Optional[threading.Thread] = None


def get_active_listener() -> Optional[PrismInteractiveListener]:
    global _active_listener
    if _active_listener and _active_listener.is_running:
        return _active_listener
    return None


def is_listener_running() -> bool:
    return get_active_listener() is not None


def stop_background_listener() -> None:
    global _active_listener, _active_loop
    if _active_listener:
        _active_listener.is_running = False
        if _active_listener.client and not _active_listener.client.is_closed():
            try:
                if _active_loop and _active_loop.is_running():
                    asyncio.run_coroutine_threadsafe(_active_listener.client.close(), _active_loop)
            except Exception:
                pass
    _active_listener = None


def launch_listener_in_new_window(bot_alias: str = "", tray: bool = False) -> bool:
    """
    Spawns an independent background console window running PRISM listener.
    Keeps the bot online 24/7 so buttons, select menus, tickets and timers never timeout.
    """
    try:
        import subprocess
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            cmd = [sys.executable, "--listen"]
            if bot_alias:
                cmd.extend(["--bot", bot_alias])
            if tray:
                cmd.append("--tray")
        else:
            main_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prism.py")
            cmd = [sys.executable, main_script, "--listen"]
            if bot_alias:
                cmd.extend(["--bot", bot_alias])
            if tray:
                cmd.append("--tray")

        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        from core.storage import BASE_DIR
        subprocess.Popen(cmd, creationflags=flags, cwd=str(BASE_DIR))
        return True
    except Exception as e:
        console.print(f"[#ED4245]Ошибка запуска фонового окна: {escape(str(e))}[/]")
        return False


def run_interactive_dashboard(
    token: str,
    embed: Optional[Embed] = None,
    channel_id: Optional[int] = None,
    bot_alias: str = "DefaultBot",
) -> None:
    """Runs a live console operator dashboard with full moderation commands."""
    global _active_listener, _active_loop, _active_thread

    if _active_listener and _active_listener.is_running:
        listener = _active_listener
        loop = _active_loop
        if embed and embed.buttons:
            for b in embed.buttons:
                if b.custom_id:
                    listener.target_buttons[b.custom_id] = b
        if embed and embed.select_menu:
            listener.select_menu = embed.select_menu
        if channel_id:
            listener.channel_id = channel_id
    else:
        stop_background_listener()
        listener = PrismInteractiveListener(token, embed, channel_id, bot_alias=bot_alias)
        loop = asyncio.new_event_loop()
        _active_listener = listener
        _active_loop = loop

        def thread_target():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(listener.run())

        _active_thread = threading.Thread(target=thread_target, daemon=True)
        _active_thread.start()

        import time
        time.sleep(1.5)

    from rich.prompt import Prompt
    from rich.table import Table
    from rich.panel import Panel

    while listener.is_running:
        active_g = storage.list_active_giveaways()
        has_giveaways = bool(active_g or (embed and any(b.action_type == "giveaway" for b in embed.buttons)))

        console.print(f"\n[bold #EBAF8E]=== ⚡ PRISM Bot Command Center • @{bot_alias} ===[/]")
        engines_str = []
        if listener.automod.config.enabled:
            engines_str.append("[#57F287]AutoMod: ON[/]")
        if listener.ai.config.enabled:
            engines_str.append(f"[#00D9FF]AI: ON[/]")
        if listener.welcomer.config.enabled:
            engines_str.append("[#EBAF8E]Welcomer: ON[/]")
        if listener.tickets.config.enabled:
            engines_str.append("[#5865F2]Tickets: ON[/]")
        if engines_str:
            console.print(f"  [bold white]Модули:[/] {' • '.join(engines_str)}")

        if channel_id:
            console.print(f"  [bold white]Канал управления:[/] [cyan]ID: {channel_id}[/cyan]")

        if has_giveaways:
            console.print(f"  [bold #57F287]R[/] [white]Выбрать победителя розыгрыша (Roll Winner) 🏆[/white]")
            console.print(f"  [bold #00D9FF]L[/] [white]Список участников розыгрыша 👥[/white]")

        console.print(f"  [bold white]Команды модератора (вводите прямо в консоль):[/]")
        console.print(f"    [bold #ED4245]ban[/] <id> [причина]       [bold #ED4245]kick[/] <id> [причина]")
        console.print(f"    [bold #FEE75C]mute[/] <id> <мин> [причина] [bold #57F287]unmute[/] <id>")
        console.print(f"    [bold #00D9FF]purge[/] <кол-во>            [bold #5865F2]tickets[/] [channel_id]")
        console.print(f"    [bold white]say[/] <текст>               [bold #EBAF8E]slowmode[/] <сек>")
        console.print(f"  [bold #5865F2]T[/] [white]Свернуть в системный трей (к часам Windows) 📌[/white]")
        console.print(f"  [bold #EBAF8E]B[/] [white]Свернуть в фон (бот онлайн 24/7) ⚡[/white]")
        console.print(f"  [bold #ED4245]0[/] [white]Полностью остановить бота[/white]\n")

        raw_cmd = Prompt.ask("[#EBAF8E]PRISM Operator >[/#EBAF8E]", default="b").strip()
        parts = raw_cmd.split()
        if not parts:
            continue
        cmd = parts[0].lower()

        if cmd in ("t", "tray", "трей"):
            from core.tray import minimize_to_tray
            console.print("\n[#57F287]✓ Окно PRISM свёрнуто в системный трей (к часам Windows).[/]")
            console.print("[#8C8C8C]Бот продолжает работать 24/7. Кликните по иконке в трее, чтобы восстановить окно.[/]\n")
            minimize_to_tray(bot_alias=bot_alias)
            return

        elif cmd in ("b", "back", "fon"):
            console.print("[#57F287]✓ Слушатель свёрнут в фон. Бот продолжает обрабатывать кнопки, тикеты и модерацию![/#57F287]")
            break

        elif cmd == "0":
            console.print("[#8C8C8C]Остановка слушателя бота...[/#8C8C8C]")
            stop_background_listener()
            break

        elif cmd == "r":
            winner = listener.roll_winner()
            if not winner:
                console.print("[bold #ED4245]Участников в активных розыгрышах пока нет.[/]")
            else:
                w_text = f"[bold green]🏆 ПОБЕДИТЕЛЬ РОЗЫГРЫША![/bold green]\n\n"
                w_text += f"Пользователь: [bold white]@{winner['username']}[/bold white]\n"
                w_text += f"Discord User ID: [cyan]{winner['user_id']}[/cyan]"
                console.print(Panel(w_text, border_style="#EBAF8E", title="[bold #EBAF8E]РЕЗУЛЬТАТ РОЗЫГРЫША[/]"))

                target_ch = channel_id
                if target_ch and listener.client and not listener.client.is_closed():
                    if Prompt.ask("[#EBAF8E]Опубликовать поздравление в Discord канал? (y/n)[/#EBAF8E]", default="y").lower() == "y":
                        async def post_win():
                            ch = listener.client.get_channel(target_ch) or await listener.client.fetch_channel(target_ch)
                            if ch:
                                msg = t("bot_roll_winner_public", user_id=winner['user_id'], username=winner['username'])
                                await ch.send(msg)
                        asyncio.run_coroutine_threadsafe(post_win(), loop)
                        console.print("[#57F287]✓ Поздравление успешно отправлено в Discord канал![/#57F287]")

        elif cmd == "l":
            g_list = storage.list_active_giveaways()
            all_parts = []
            for g in g_list:
                all_parts.extend(g.get("participants", []))

            if not all_parts:
                console.print("[#8C8C8C]Список пуст. Участников пока нет.[/#8C8C8C]")
            else:
                table = Table(title="Участники розыгрыша", border_style="#3F3F46", header_style="bold #EBAF8E")
                table.add_column("#", style="#EBAF8E", width=4)
                table.add_column("Username", style="bold white", width=24)
                table.add_column("User ID", style="cyan", width=20)
                table.add_column("Время входа", style="#8C8C8C")
                for i, p in enumerate(all_parts, start=1):
                    table.add_row(str(i), p["username"], str(p["user_id"]), p.get("joined_at", "")[:19])
                console.print(table)

        elif cmd == "ban":
            if len(parts) < 2 or not parts[1].isdigit():
                console.print("[#ED4245]Использование: ban <user_id> [причина][/]")
                continue
            uid = int(parts[1])
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Бан через консоль PRISM"
            async def do_ban():
                for guild in listener.client.guilds:
                    ok, msg = await ModerationEngine.ban_user(guild, uid, reason)
                    if ok:
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                        return
                console.print(f"[#ED4245]Не удалось забанить {uid} (проверьте права бота на сервере).[/#ED4245]")
            asyncio.run_coroutine_threadsafe(do_ban(), loop)

        elif cmd == "kick":
            if len(parts) < 2 or not parts[1].isdigit():
                console.print("[#ED4245]Использование: kick <user_id> [причина][/]")
                continue
            uid = int(parts[1])
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Кик через консоль PRISM"
            async def do_kick():
                for guild in listener.client.guilds:
                    ok, msg = await ModerationEngine.kick_user(guild, uid, reason)
                    if ok:
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                        return
                console.print(f"[#ED4245]Пользователь {uid} не найден на серверах бота.[/#ED4245]")
            asyncio.run_coroutine_threadsafe(do_kick(), loop)

        elif cmd == "mute":
            if len(parts) < 2 or not parts[1].isdigit():
                console.print("[#ED4245]Использование: mute <user_id> <минуты> [причина][/]")
                continue
            uid = int(parts[1])
            mins = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
            reason = " ".join(parts[3:]) if len(parts) > 3 else "Таймаут через консоль PRISM"
            async def do_mute():
                for guild in listener.client.guilds:
                    ok, msg = await ModerationEngine.timeout_user(guild, uid, mins, reason)
                    if ok:
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                        return
                console.print(f"[#ED4245]Пользователь {uid} не найден.[/#ED4245]")
            asyncio.run_coroutine_threadsafe(do_mute(), loop)

        elif cmd == "unmute":
            if len(parts) < 2 or not parts[1].isdigit():
                console.print("[#ED4245]Использование: unmute <user_id>[/]")
                continue
            uid = int(parts[1])
            async def do_unmute():
                for guild in listener.client.guilds:
                    ok, msg = await ModerationEngine.untimeout_user(guild, uid)
                    if ok:
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                        return
                console.print(f"[#ED4245]Пользователь {uid} не найден.[/#ED4245]")
            asyncio.run_coroutine_threadsafe(do_unmute(), loop)

        elif cmd == "purge":
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            target_ch = channel_id
            if not target_ch:
                ch_in = Prompt.ask("[#EBAF8E]ID канала для очистки[/#EBAF8E]").strip()
                if ch_in.isdigit():
                    target_ch = int(ch_in)
            if target_ch:
                async def do_purge():
                    ch = listener.client.get_channel(target_ch) or await listener.client.fetch_channel(target_ch)
                    if isinstance(ch, discord.TextChannel):
                        ok, d_count, msg = await ModerationEngine.purge_channel(ch, count)
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                    else:
                        console.print("[#ED4245]Канал не найден или это не текстовый канал.[/#ED4245]")
                asyncio.run_coroutine_threadsafe(do_purge(), loop)

        elif cmd == "say":
            if len(parts) < 2:
                console.print("[#ED4245]Использование: say <текст>[/]")
                continue
            text = " ".join(parts[1:])
            target_ch = channel_id
            if not target_ch:
                ch_in = Prompt.ask("[#EBAF8E]ID канала для отправки[/#EBAF8E]").strip()
                if ch_in.isdigit():
                    target_ch = int(ch_in)
            if target_ch:
                async def do_say():
                    ch = listener.client.get_channel(target_ch) or await listener.client.fetch_channel(target_ch)
                    if ch:
                        await ch.send(text)
                        console.print(f"[#57F287]✓ Сообщение отправлено в #{ch.name}![/#57F287]")
                asyncio.run_coroutine_threadsafe(do_say(), loop)

        elif cmd == "tickets":
            target_ch = channel_id
            if len(parts) > 1 and parts[1].isdigit():
                target_ch = int(parts[1])
            if not target_ch:
                ch_in = Prompt.ask("[#EBAF8E]ID канала для панели тикетов[/#EBAF8E]").strip()
                if ch_in.isdigit():
                    target_ch = int(ch_in)
            if target_ch:
                async def do_tickets():
                    ok, msg = await listener.tickets.deploy_panel(listener.client, target_ch, use_select=True)
                    if ok:
                        console.print(f"[#57F287]✓ {msg}[/#57F287]")
                    else:
                        console.print(f"[#ED4245]✗ {msg}[/#ED4245]")
                asyncio.run_coroutine_threadsafe(do_tickets(), loop)
