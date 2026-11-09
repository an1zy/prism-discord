"""
PRISM - Discord Bot Management & Control Suite
Main Application Entry Point and Interactive CLI
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone, timedelta
import json
import sys
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from core.embed import Embed, Button, SelectMenu, SelectOption, COLOR_PRESETS
from core.webhook import DiscordWebhookClient, WebhookError
from core.storage import StorageManager
from core.bot_engines import (
    BotEngineSettings,
    AutoModConfig,
    AIAssistantConfig,
    WelcomerConfig,
    TicketConfig,
)
from rich.markup import escape
from core.bot_runner import (
    send_via_bot,
    delete_bot_message,
    edit_bot_message,
    deploy_ticket_panel,
    run_interactive_dashboard,
    is_listener_running,
    stop_background_listener,
    get_active_listener,
    launch_listener_in_new_window,
    PrismInteractiveListener,
)
from core.themes import UITheme, get_theme, list_themes, DEFAULT_THEME
from core.i18n import t, set_active_language, get_language
from ui.terminal import (
    console,
    clear_screen,
    print_banner,
    render_embed_preview,
    display_fleet_list,
    display_webhook_list,
    display_template_list,
    ask_choice,
    PEACH,
    MUTED,
    GREEN,
    RED,
    CYAN,
)

storage = StorageManager()
client = DiscordWebhookClient()


def get_current_theme() -> UITheme:
    return get_theme(storage.get_theme())


def refresh_locale() -> None:
    set_active_language(get_language(storage.get_language()))


refresh_locale()


# --- Sender Profiles (Multi-Bot & Webhooks Fleet) ---

def action_select_sender(embed: Embed) -> Optional[Tuple[str, str, str]]:
    """
    Selects sender profile for dispatch.
    Returns (sender_type, identifier, extra_info):
      - ("bot", token, alias)
      - ("webhook", url, alias)
      - None (cancelled)
    """
    theme = get_current_theme()
    bots = storage.get_bots()
    webhooks = storage.get_webhooks()
    has_actions = any(b.action_type != "link" and b.style != 5 for b in embed.buttons)

    clear_screen()
    print_banner(theme)
    console.print(f"[bold {theme.accent}]{t('sender_select_title')}[/]\n")

    if has_actions:
        console.print(f"[{theme.accent}]ℹ️ В сообщении есть кнопки со сценариями (Розыгрыш / Роли).[/]")
        console.print(f"[{MUTED}]Для работы кнопок в Discord требуется бот.[/]\n")

    options: List[Tuple[str, str, str]] = []
    opt_idx = 1

    # Bots
    if bots:
        console.print(f"[bold white]🤖 Discord Боты (Поддержка всех кнопок и ролей):[/]")
        for alias, b_data in bots.items():
            name = b_data.get("name", alias)
            console.print(f"  [{theme.accent}]{opt_idx}[/] @{name} [{MUTED}](Бот-профиль: {alias})[/]")
            options.append(("bot", b_data.get("token", ""), alias))
            opt_idx += 1
        console.print("")

    # Webhooks (only if no action buttons or user chooses)
    if webhooks:
        console.print(f"[bold white]🔗 Discord Вебхуки (Только кнопки-ссылки ↗):[/]")
        for alias, url in webhooks.items():
            console.print(f"  [{theme.accent}]{opt_idx}[/] #{alias} [{MUTED}]({url[:35]}...)[/]")
            options.append(("webhook", url, alias))
            opt_idx += 1
        console.print("")

    # Manual additions
    console.print(f"[bold {MUTED}]Ручной ввод:[/]")
    console.print(f"  [{theme.accent}]{opt_idx}[/] Ввести токен нового бота")
    options.append(("new_bot", "", ""))
    opt_idx += 1

    console.print(f"  [{theme.accent}]{opt_idx}[/] Ввести Webhook URL вручную")
    options.append(("new_webhook", "", ""))
    opt_idx += 1

    console.print(f"  [{theme.accent}]0[/] Отмена\n")

    choice = ask_choice("Выберите отправителя >", default="1", theme=theme)
    if choice == "0" or not choice.isdigit():
        return None

    c_num = int(choice)
    if 1 <= c_num <= len(options):
        kind, val, alias = options[c_num - 1]
        if kind == "bot":
            return ("bot", val, alias)
        elif kind == "webhook":
            return ("webhook", val, alias)
        elif kind == "new_bot":
            tok = Prompt.ask(f"[{theme.accent}]Введите Discord Bot Token[/]").strip()
            if not tok:
                return None
            name = Prompt.ask(f"[{theme.accent}]Имя / Алиас для бота (например: EventBot)[/]", default="MyBot").strip()
            storage.save_bot(name, tok, name)
            return ("bot", tok, name)
        elif kind == "new_webhook":
            url = Prompt.ask(f"[{theme.accent}]Введите Discord Webhook URL[/]").strip()
            if not client.is_valid_url(url):
                console.print(f"[{RED}]Неверный формат URL вебхука.[/]")
                Prompt.ask(t("press_enter"))
                return None
            name = Prompt.ask(f"[{theme.accent}]Алиас для вебхука (например: #news)[/]", default="custom").strip()
            storage.save_webhook(name, url)
            return ("webhook", url, name)

    return None


def dispatch_embed(embed: Embed) -> None:
    """Dispatches embed to Discord using selected Bot or Webhook."""
    theme = get_current_theme()
    warnings = embed.validate()
    if warnings:
        console.print(f"\n[{RED}]Внимание:[/]")
        for w in warnings:
            console.print(f"  [{RED}]• {w}[/]")
        if not Confirm.ask("Всё равно попробовать отправить?", default=False):
            return

    sender = action_select_sender(embed)
    if not sender:
        return

    sender_type, identifier, alias = sender

    # Text content / mention
    content = Prompt.ask(f"[{MUTED}]{t('sender_ping_content')}[/]", default="").strip()

    if sender_type == "bot":
        token = identifier
        ch_input = Prompt.ask(f"[{theme.accent}]{t('sender_channel_id')}[/]").strip()
        if not ch_input.isdigit():
            console.print(f"[{RED}]ID канала должен состоять только из цифр.[/]")
            Prompt.ask(t("press_enter"))
            return
        channel_id = int(ch_input)

        # Check for timed giveaways and save schedule
        for b in embed.buttons:
            if b.action_type == "giveaway" and b.duration_minutes > 0:
                end_time = datetime.now(timezone.utc) + timedelta(minutes=b.duration_minutes)
                storage.save_giveaway(
                    b.custom_id,
                    {
                        "custom_id": b.custom_id,
                        "title": embed.title or "Розыгрыш",
                        "prize": b.prize or "Discord Nitro",
                        "winners_count": b.winners_count or 1,
                        "channel_id": channel_id,
                        "end_time": end_time.isoformat(),
                        "duration_minutes": b.duration_minutes,
                        "status": "active",
                        "participants": [],
                    }
                )
                console.print(f"[{GREEN}]✓ Таймер розыгрыша установлен на {b.duration_minutes} мин. (Итоги в {end_time.strftime('%H:%M:%S UTC')})[/]")

        try:
            with console.status(f"[{theme.accent}]Отправка через бота @{alias}...[/]"):
                msg_id, ch_id, bot_name = send_via_bot(token, channel_id, embed, content)
            console.print(f"\n[{GREEN}]✓ Сообщение успешно отправлено ботом @{bot_name} в канал {channel_id}! (ID: {msg_id})[/]\n")
            storage.record_message(str(msg_id), f"bot_@{alias}", embed.title or "Interactive Embed", content, channel_id=channel_id)
            storage.save_components(buttons=embed.buttons, select_menu=embed.select_menu)

            has_actions = any(b.action_type != "link" and b.style != 5 for b in embed.buttons) or bool(embed.select_menu and embed.select_menu.options)
            if has_actions:
                if is_listener_running():
                    console.print(f"[{GREEN}]✓ Слушатель кнопок уже активен в фоне и перехватывает клики![/]")
                    Prompt.ask(f"[{MUTED}]{t('press_enter')}[/]")
                else:
                    console.print(f"\n[bold {theme.accent}]⚡ В сообщении есть интерактивные кнопки / меню:[/]")
                    console.print(f"  [{theme.accent}]1[/] [bold #57F287]Запустить в отдельном окне[/] (Рекомендуется — бот онлайн 24/7, кнопки сразу работают)")
                    console.print(f"  [{theme.accent}]2[/] Запустить прямо здесь (пульт оператора, лог кликов в реальном времени)")
                    console.print(f"  [{theme.accent}]3[/] Оставить оффлайн (кнопки не будут нажиматься, пока не включите в Меню 5)\n")
                    mode = ask_choice("Выберите режим >", choices=["1", "2", "3"], default="1", theme=theme)
                    if mode == "1":
                        launch_listener_in_new_window(alias)
                        console.print(f"[{GREEN}]✓ Слушатель запущен в новом окне! Кнопки и списки в Discord активны.[/]")
                        Prompt.ask(f"[{MUTED}]{t('press_enter')}[/]")
                    elif mode == "2":
                        run_interactive_dashboard(token, embed=embed, channel_id=channel_id, bot_alias=alias)
                    else:
                        console.print(f"[{MUTED}]Кнопки будут показывать 'Приложение не ответило вовремя', пока слушатель оффлайн.[/]")
                        Prompt.ask(f"[{MUTED}]{t('press_enter')}[/]")
        except Exception as e:
            console.print(f"\n[{RED}]✗ Ошибка отправки через бота: {escape(str(e))}[/]\n")
            Prompt.ask(t("press_enter"))

    elif sender_type == "webhook":
        url = identifier
        bot_name = Prompt.ask(f"[{MUTED}]Имя бота (Enter — стандартное)[/]", default="").strip()
        bot_avatar = Prompt.ask(f"[{MUTED}]URL аватарки бота (Enter — стандартная)[/]", default="").strip()

        if Confirm.ask(f"\n[bold {theme.accent}]{t('sender_dispatch_now')}[/]", default=True):
            try:
                with console.status(f"[{theme.accent}]Отправка в Discord через Webhook...[/]"):
                    resp = client.send(
                        url=url,
                        content=content,
                        username=bot_name,
                        avatar_url=bot_avatar,
                        embed=embed,
                    )
                msg_id = resp.get("id", "sent")
                storage.record_message(str(msg_id), f"webhook_#{alias}", embed.title or "Embed", content)
                console.print(f"\n[{GREEN}]✓ Сообщение успешно отправлено в Discord! (ID: {msg_id})[/]\n")
                Prompt.ask(t("press_enter"))
            except WebhookError as e:
                console.print(f"\n[{RED}]✗ Ошибка отправки: {escape(str(e))}[/]\n")
                Prompt.ask(t("press_enter"))


# --- Modular Embed Studio ---

def edit_color_menu(embed: Embed, theme: UITheme) -> None:
    console.print(f"\n[bold {theme.accent}]Выберите цвет полоски эмбеда:[/]")
    console.print(f"  [{theme.accent}]1[/] Peach    [{PEACH}]■ #EBAF8E[/] (Фирменный тёплый)")
    console.print(f"  [{theme.accent}]2[/] Blurple  [#5865F2]■ #5865F2[/] (Классический Discord)")
    console.print(f"  [{theme.accent}]3[/] Green    [#57F287]■ #57F287[/] (Успех / онлайн)")
    console.print(f"  [{theme.accent}]4[/] Red      [#ED4245]■ #ED4245[/] (Внимание / ошибка)")
    console.print(f"  [{theme.accent}]5[/] Gold     [#FEE75C]■ #FEE75C[/] (Премиум / золото)")
    console.print(f"  [{theme.accent}]6[/] Cyan     [#00D9FF]■ #00D9FF[/] (Неон / кибер)")
    console.print(f"  [{theme.accent}]7[/] Ввести свой HEX-код вручную (#XXXXXX)")
    console.print(f"  [{theme.accent}]0[/] Оставить текущий\n")

    c_choice = ask_choice("Цвет >", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1", theme=theme)
    color_map = {
        "1": "peach",
        "2": "blurple",
        "3": "green",
        "4": "red",
        "5": "gold",
        "6": "cyan",
    }
    if c_choice in color_map:
        embed.set_color(color_map[c_choice])
    elif c_choice == "7":
        hex_val = Prompt.ask(f"[{theme.accent}]Введите HEX (например #FF5500)[/]").strip()
        if hex_val:
            embed.set_color(hex_val)


def edit_buttons_menu(embed: Embed, theme: UITheme) -> None:
    """Expanded button configuration: Link buttons, giveaways with timers, and real role assignment."""
    while True:
        clear_screen()
        print_banner(theme)
        render_embed_preview(embed, theme=theme)
        console.print(f"[bold {theme.accent}]{t('buttons_title')}[/]\n")
        if not embed.buttons:
            console.print(f"[{MUTED}]{t('buttons_empty')}[/]\n")
        else:
            for idx, b in enumerate(embed.buttons, start=1):
                emoji_part = f"{b.emoji} " if b.emoji else ""
                if b.action_type == "link" or b.style == 5:
                    console.print(f"  [{theme.accent}]{idx}[/] [bold white]{emoji_part}{b.label} ↗[/] [{MUTED}]Ссылка:[/] [{CYAN}]{b.url}[/]")
                elif b.action_type == "giveaway":
                    timer_info = f" • Таймер: {b.duration_minutes} мин." if b.duration_minutes > 0 else ""
                    console.print(f"  [{theme.accent}]{idx}[/] [bold #5865F2]{emoji_part}{b.label}[/] [{MUTED}]Розыгрыш (Приз: {b.prize or 'Nitro'}{timer_info})[/]")
                elif b.action_type == "verify":
                    role_info = f" • Роль: {b.role_id}" if b.role_id else ""
                    console.print(f"  [{theme.accent}]{idx}[/] [bold #57F287]{emoji_part}{b.label}[/] [{MUTED}]Верификация{role_info}[/]")
                else:
                    console.print(f"  [{theme.accent}]{idx}[/] [bold white]{emoji_part}{b.label}[/] [{MUTED}]Свой сценарий[/]")
            console.print("")

        console.print(f"  [{theme.accent}]1[/] {t('buttons_add')}")
        if embed.buttons:
            console.print(f"  [{theme.accent}]2[/] {t('buttons_remove')}")
            console.print(f"  [{theme.accent}]3[/] {t('buttons_clear')}")
        console.print(f"  [{theme.accent}]0[/] {t('buttons_save_back')}\n")

        valid_choices = ["0", "1"] + (["2", "3"] if embed.buttons else [])
        sub = ask_choice("Выберите действие >", choices=valid_choices, default="0", theme=theme)
        if sub == "0":
            break
        elif sub == "1":
            if len(embed.buttons) >= 5:
                console.print(f"[{RED}]{t('btn_limit_reached')}[/]")
                Prompt.ask(t("press_enter"))
                continue

            console.print(f"\n[bold {theme.accent}]Выберите тип и сценарий кнопки:[/]")
            console.print(f"  [{theme.accent}]1[/] {t('btn_type_link')}")
            console.print(f"      [{MUTED}]{t('btn_type_link_desc')}[/]")
            console.print(f"  [{theme.accent}]2[/] {t('btn_type_giveaway')}")
            console.print(f"      [{MUTED}]{t('btn_type_giveaway_desc')}[/]")
            console.print(f"  [{theme.accent}]3[/] {t('btn_type_verify')}")
            console.print(f"      [{MUTED}]{t('btn_type_verify_desc')}[/]")
            console.print(f"  [{theme.accent}]4[/] {t('btn_type_custom')}")
            console.print(f"      [{MUTED}]{t('btn_type_custom_desc')}[/]")
            console.print(f"  [{theme.accent}]0[/] Отмена\n")

            btn_type = ask_choice("Тип кнопки >", choices=["0", "1", "2", "3", "4"], default="1", theme=theme)
            if btn_type == "0":
                continue

            if btn_type == "1":
                lbl = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_label')}[/]", default="Наш сайт").strip()
                url = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_url')}[/]", default="https://").strip()
                emo = Prompt.ask(f"[{MUTED}]{t('btn_prompt_emoji')}[/]", default="🌐").strip()
                embed.add_button(label=lbl, url=url, emoji=emo, action_type="link", style=5)

            elif btn_type == "2":
                lbl = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_label')}[/]", default="Участвовать в розыгрыше").strip()
                emo = Prompt.ask(f"[{MUTED}]{t('btn_prompt_emoji')}[/]", default="🎉").strip()
                prize = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_prize')}[/]", default="Discord Nitro Full (1 месяц)").strip()
                dur_str = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_minutes')}[/]", default="10").strip()
                duration = int(dur_str) if dur_str.isdigit() else 0
                resp = Prompt.ask(
                    f"[{theme.accent}]{t('btn_prompt_response')}[/]",
                    default="🎉 Вы успешно зарегистрированы в розыгрыше! Желаем удачи!",
                ).strip()
                embed.add_button(
                    label=lbl,
                    emoji=emo,
                    action_type="giveaway",
                    style=1,  # Blurple
                    response_text=resp,
                    prize=prize,
                    duration_minutes=duration,
                )

            elif btn_type == "3":
                lbl = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_label')}[/]", default="Я прочитал правила").strip()
                emo = Prompt.ask(f"[{MUTED}]{t('btn_prompt_emoji')}[/]", default="✅").strip()
                role_id = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_role')}[/]", default="").strip()
                resp = Prompt.ask(
                    f"[{theme.accent}]{t('btn_prompt_response')}[/]",
                    default="✅ Вы успешно подтвердили правила сообщества! Доступ открыт.",
                ).strip()
                embed.add_button(
                    label=lbl,
                    emoji=emo,
                    action_type="verify",
                    style=3,  # Green
                    response_text=resp,
                    role_id=role_id,
                )

            elif btn_type == "4":
                lbl = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_label')}[/]").strip()
                if not lbl:
                    continue
                emo = Prompt.ask(f"[{MUTED}]{t('btn_prompt_emoji')}[/]", default="").strip()
                console.print(f"[bold {theme.accent}]Цвет кнопки:[/] 1. Blurple  2. Green  3. Red  4. Gray")
                c_pick = ask_choice("Цвет >", choices=["1", "2", "3", "4"], default="1", theme=theme)
                style_map = {"1": 1, "2": 3, "3": 4, "4": 2}
                resp = Prompt.ask(f"[{theme.accent}]{t('btn_prompt_response')}[/]", default="Действие выполнено!").strip()
                embed.add_button(
                    label=lbl,
                    emoji=emo,
                    action_type="custom",
                    style=style_map.get(c_pick, 1),
                    response_text=resp,
                )

        elif sub == "2" and embed.buttons:
            num = ask_choice("Номер кнопки для удаления >", default="1", theme=theme)
            if num.isdigit() and 1 <= int(num) <= len(embed.buttons):
                embed.remove_button(int(num) - 1)
        elif sub == "3" and embed.buttons:
            if Confirm.ask("Удалить все кнопки?", default=False):
                embed.clear_buttons()


def edit_select_menu(embed: Embed, theme: UITheme) -> None:
    """Configures interactive Discord Select Menu (Dropdown) with roles, replies, or tickets."""
    if not embed.select_menu:
        embed.select_menu = SelectMenu(
            custom_id="prism_select_menu",
            placeholder="Выберите вариант...",
            options=[],
        )

    sm = embed.select_menu

    while True:
        clear_screen()
        print_banner(theme)
        render_embed_preview(embed, theme=theme)
        console.print(f"[bold {theme.accent}]=== Настройка выпадающего списка (Select Menu) ===[/]\n")
        console.print(f"  [bold white]Плейсхолдер:[/] [{CYAN}]{sm.placeholder}[/]")
        console.print(f"  [bold white]Пунктов в меню:[/] [{theme.accent}]{len(sm.options)} (макс 25)[/]\n")

        if not sm.options:
            console.print(f"[{MUTED}]Список пока пуст. Добавьте пункты для выбора ролей, FAQ или тикетов.[/]\n")
        else:
            for idx, opt in enumerate(sm.options, start=1):
                emo_str = f"{opt.emoji} " if opt.emoji else ""
                desc_str = f" • {opt.description}" if opt.description else ""
                if opt.action_type == "role":
                    action_info = f"[#57F287]Выдача роли: {opt.role_id}[/#57F287]"
                elif opt.action_type == "ticket":
                    action_info = f"[#00D9FF]Создание тикета[/#00D9FF]"
                else:
                    action_info = f"[{MUTED}]Личный ответ: {opt.response_text[:30]}...[/]"

                console.print(f"  [{theme.accent}]{idx}[/] [bold white]{emo_str}{opt.label}[/]{desc_str} -> {action_info}")
            console.print("")

        console.print(f"  [{theme.accent}]1[/] Добавить пункт в меню")
        console.print(f"  [{theme.accent}]2[/] Изменить текст-подсказку (плейсхолдер)")
        if sm.options:
            console.print(f"  [{theme.accent}]3[/] Удалить пункт из меню")
            console.print(f"  [{theme.accent}]4[/] Очистить весь список")
        console.print(f"  [{theme.accent}]0[/] Сохранить и вернуться в конструктор\n")

        valid = ["0", "1", "2"] + (["3", "4"] if sm.options else [])
        sub = ask_choice("Выберите действие >", choices=valid, default="0", theme=theme)

        if sub == "0":
            if not sm.options:
                embed.select_menu = None
            break
        elif sub == "1":
            if len(sm.options) >= 25:
                console.print(f"[{RED}]Лимит Discord: максимум 25 пунктов в одном списке.[/]")
                Prompt.ask(t("press_enter"))
                continue

            console.print(f"\n[bold {theme.accent}]Выберите действие при выборе этого пункта:[/]")
            console.print(f"  [{theme.accent}]1[/] 🎭 Выдать / снять роль на сервере (Reaction Roles)")
            console.print(f"  [{theme.accent}]2[/] 💬 Личный ответ пользователю (FAQ / Секретный бонус / Инфо)")
            console.print(f"  [{theme.accent}]3[/] 🎫 Создать приватный тикет в поддержку")
            console.print(f"  [{theme.accent}]0[/] Отмена\n")

            a_type_c = ask_choice("Действие пункта >", choices=["0", "1", "2", "3"], default="1", theme=theme)
            if a_type_c == "0":
                continue

            lbl = Prompt.ask(f"[{theme.accent}]Название пункта (например: Новости или Игры)[/]").strip()
            if not lbl:
                continue
            emo = Prompt.ask(f"[{MUTED}]Эмодзи перед пунктом (например: 🎮 или пусто)[/]", default="").strip()
            desc = Prompt.ask(f"[{MUTED}]Краткое описание пункта (подпись мелким шрифтом)[/]", default="").strip()
            val = f"opt_{len(sm.options)+1}_{lbl.lower()[:15].replace(' ', '_')}"

            if a_type_c == "1":
                r_id = Prompt.ask(f"[{theme.accent}]ID Discord роли для выдачи (Role ID)[/]").strip()
                sm.options.append(SelectOption(label=lbl, value=val, description=desc, emoji=emo, action_type="role", role_id=r_id))
            elif a_type_c == "2":
                resp = Prompt.ask(f"[{theme.accent}]Личный ответ пользователю при выборе (эфемерное сообщение)[/]", default="Вы успешно выбрали этот пункт!").strip()
                sm.options.append(SelectOption(label=lbl, value=val, description=desc, emoji=emo, action_type="reply", response_text=resp))
            elif a_type_c == "3":
                sm.options.append(SelectOption(label=lbl, value=val, description=desc, emoji=emo, action_type="ticket"))

        elif sub == "2":
            new_ph = Prompt.ask(f"[{theme.accent}]Введите текст-подсказку для списка[/]", default=sm.placeholder).strip()
            if new_ph:
                sm.placeholder = new_ph
        elif sub == "3":
            idx_str = Prompt.ask("Номер пункта для удаления").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(sm.options):
                sm.options.pop(int(idx_str) - 1)
        elif sub == "4":
            if Confirm.ask("Очистить все пункты меню?", default=False):
                sm.options.clear()


def edit_fields_menu(embed: Embed, theme: UITheme) -> None:
    while True:
        clear_screen()
        print_banner(theme)
        render_embed_preview(embed, theme=theme)
        console.print(f"[bold {theme.accent}]=== Настройка информационных полей (Fields) ===[/]\n")
        if not embed.fields:
            console.print(f"[{MUTED}]Полей пока нет.[/]\n")
        else:
            for idx, fld in enumerate(embed.fields, start=1):
                inline_str = " (в один ряд)" if fld.inline else " (отдельная строка)"
                console.print(f"  [{theme.accent}]{idx}[/] [bold white]{fld.name}[/]: [{MUTED}]{fld.value}{inline_str}[/]")
            console.print("")

        console.print(f"  [{theme.accent}]1[/] Добавить новое поле")
        if embed.fields:
            console.print(f"  [{theme.accent}]2[/] Удалить поле")
            console.print(f"  [{theme.accent}]3[/] Очистить все поля")
        console.print(f"  [{theme.accent}]0[/] Назад в конструктор\n")

        valid_choices = ["0", "1"] + (["2", "3"] if embed.fields else [])
        sub = ask_choice("Выберите действие >", choices=valid_choices, default="0", theme=theme)
        if sub == "0":
            break
        elif sub == "1":
            f_name = Prompt.ask(f"[{theme.accent}]Заголовок поля (например: Статус / Приз / Время)[/]").strip()
            if not f_name:
                continue
            f_val = Prompt.ask(f"[{theme.accent}]Значение поля (текст)[/]").strip()
            f_inline = Confirm.ask("Показывать в одну строку с соседними блоками? (inline)", default=True)
            embed.add_field(f_name, f_val, inline=f_inline)
        elif sub == "2" and embed.fields:
            num = ask_choice("Номер поля для удаления >", default="1", theme=theme)
            if num.isdigit() and 1 <= int(num) <= len(embed.fields):
                embed.remove_field(int(num) - 1)
        elif sub == "3" and embed.fields:
            if Confirm.ask("Удалить все поля?", default=False):
                embed.clear_fields()


def action_interactive_builder(embed: Optional[Embed] = None) -> None:
    """Modular Studio: top live preview, bottom modular parts with full button and scenario support."""
    theme = get_current_theme()
    if embed is None:
        embed = Embed(
            title="Заголовок сообщения",
            description="Текст сообщения с поддержкой markdown (**жирный**, *курсив*, `код`).",
            color=COLOR_PRESETS["peach"],
            footer_text="PRISM Studio",
        )

    while True:
        clear_screen()
        print_banner(theme)
        render_embed_preview(embed, theme=theme)

        btn_count = len(embed.buttons)
        fld_count = len(embed.fields)
        sm_count = len(embed.select_menu.options) if embed.select_menu else 0

        title_display = embed.title or f"[{MUTED}не задан{MUTED}]"
        desc_display = (embed.description[:35] + "...") if len(embed.description) > 35 else (embed.description or f"[{MUTED}пусто{MUTED}]")
        footer_display = embed.footer_text or f"[{MUTED}пусто{MUTED}]"

        console.print(f"[bold {theme.accent}]{t('studio_title')}[/]")
        console.print(f"  [{theme.accent}]1[/] {t('part_title')}        : [white]{title_display}[/white]")
        console.print(f"  [{theme.accent}]2[/] {t('part_desc')}    : [white]{desc_display}[/white]")
        console.print(f"  [{theme.accent}]3[/] {t('part_color')}      : [{embed.color_hex}]■ {embed.color_hex}[/]")
        console.print(f"  [{theme.accent}]4[/] {t('part_fields')}     : [white]{fld_count} шт.[/white]")
        console.print(f"  [{theme.accent}]5[/] {t('part_buttons')} : [white]{btn_count} шт. (до 5)[/white]")
        console.print(f"  [{theme.accent}]9[/] Выпадающий список  : [white]{sm_count} пунктов (до 25)[/white]")
        console.print(f"  [{theme.accent}]6[/] {t('part_image')}   : [white]{embed.image_url or f'[{MUTED}нет{MUTED}]'}[/white]")
        console.print(f"  [{theme.accent}]7[/] {t('part_author')}    : [white]{embed.author_name or f'[{MUTED}нет{MUTED}]'}[/white]")
        console.print(f"  [{theme.accent}]8[/] {t('part_footer')} : [white]{footer_display}[/white]")
        console.print(f"[{MUTED}]---------------------------------------------------[/]")
        console.print(f"  [bold {GREEN}]S[/] [bold white]{t('action_dispatch')}[/bold white]")
        console.print(f"  [bold {theme.accent}]W[/] {t('action_save_tpl')}")
        console.print(f"  [{MUTED}]C[/] {t('action_clear')}")
        console.print(f"  [{theme.accent}]0[/] {t('action_back')}\n")

        choice = ask_choice(t("prompt_detail"), default="S", theme=theme)
        choice_upper = choice.upper()

        if choice_upper == "0":
            break
        elif choice_upper == "S":
            dispatch_embed(embed)
            Prompt.ask(f"\n[{MUTED}]{t('press_enter')}[/]")
        elif choice_upper == "W":
            tpl_name = Prompt.ask(f"[{theme.accent}]{t('prompt_tpl_name')}[/]").strip()
            if tpl_name:
                p = storage.save_template(tpl_name, embed)
                console.print(f"[{GREEN}]{t('template_saved_success')} {p.name}[/]")
            Prompt.ask(f"\n[{MUTED}]{t('press_enter')}[/]")
        elif choice_upper == "C":
            if Confirm.ask(t("reset_confirm"), default=False):
                embed = Embed(title="", description="", color=COLOR_PRESETS["peach"])
        elif choice == "1":
            embed.title = Prompt.ask(f"[{theme.accent}]{t('prompt_title')}[/]", default=embed.title).strip()
            embed.url = Prompt.ask(f"[{MUTED}]{t('prompt_url')}[/]", default=embed.url).strip()
        elif choice == "2":
            embed.description = Prompt.ask(f"[{theme.accent}]{t('prompt_desc')}[/]", default=embed.description).strip()
        elif choice == "3":
            edit_color_menu(embed, theme)
        elif choice == "4":
            edit_fields_menu(embed, theme)
        elif choice == "5":
            edit_buttons_menu(embed, theme)
        elif choice == "9":
            edit_select_menu(embed, theme)
        elif choice == "6":
            embed.image_url = Prompt.ask(f"[{theme.accent}]{t('prompt_img')}[/]", default=embed.image_url).strip()
            embed.thumbnail_url = Prompt.ask(f"[{MUTED}]{t('prompt_thumb')}[/]", default=embed.thumbnail_url).strip()
        elif choice == "7":
            embed.author_name = Prompt.ask(f"[{theme.accent}]{t('prompt_author_name')}[/]", default=embed.author_name).strip()
            if embed.author_name:
                embed.author_icon_url = Prompt.ask(f"[{MUTED}]{t('prompt_author_icon')}[/]", default=embed.author_icon_url).strip()
                embed.author_url = Prompt.ask(f"[{MUTED}]{t('prompt_author_url')}[/]", default=embed.author_url).strip()
        elif choice == "8":
            embed.footer_text = Prompt.ask(f"[{theme.accent}]{t('prompt_footer_text')}[/]", default=embed.footer_text).strip()
            embed.timestamp = Confirm.ask(t("prompt_timestamp"), default=embed.timestamp)


# --- Send Flow ---

def action_send_template() -> None:
    theme = get_current_theme()
    templates = storage.list_templates()
    if not templates:
        console.print(f"[{RED}]{t('template_not_found')}[/]\n")
        return

    clear_screen()
    print_banner(theme)
    display_template_list(templates, theme=theme)

    choice = ask_choice("Введите номер или ID шаблона >", default="1", theme=theme)
    selected_name = None
    if choice.isdigit() and 1 <= int(choice) <= len(templates):
        selected_name = templates[int(choice) - 1]
    elif choice in templates:
        selected_name = choice

    if not selected_name:
        console.print(f"[{RED}]{t('template_not_found')}[/]\n")
        return

    embed = storage.load_template(selected_name)
    if not embed:
        console.print(f"[{RED}]Не удалось прочитать шаблон {selected_name}.[/]\n")
        return

    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold green]{t('template_preview_title')} {selected_name}[/bold green]\n")
        render_embed_preview(embed, theme=theme)

        console.print(f"[bold {theme.accent}]{t('template_what_to_do')}[/]")
        console.print(f"  [{theme.accent}]1[/] {t('template_action_send')}")
        console.print(f"  [{theme.accent}]2[/] {t('template_action_edit')}")
        console.print(f"  [{theme.accent}]0[/] Назад\n")

        sub = ask_choice("Выберите действие >", choices=["0", "1", "2"], default="1", theme=theme)
        if sub == "0":
            break
        elif sub == "1":
            dispatch_embed(embed)
            Prompt.ask(f"[{MUTED}]{t('press_enter')}[/]")
            break
        elif sub == "2":
            action_interactive_builder(embed=embed)
            break


def action_send_flow() -> None:
    theme = get_current_theme()
    clear_screen()
    print_banner(theme)
    console.print(f"[bold {theme.accent}]{t('send_flow_title')}[/]\n")
    console.print(f"  [{theme.accent}]1[/] {t('send_opt_template')}")
    console.print(f"  [{theme.accent}]2[/] {t('send_opt_scratch')}")
    console.print(f"  [{theme.accent}]0[/] {t('send_opt_back')}\n")

    c = ask_choice(t("send_prompt"), choices=["0", "1", "2"], default="1", theme=theme)
    if c == "1":
        action_send_template()
    elif c == "2":
        action_interactive_builder()


# --- Sender Fleet Manager (Bots & Webhooks) ---

def action_manage_fleet() -> None:
    """Manage multiple bot tokens and webhooks in a unified Sender Fleet."""
    while True:
        theme = get_current_theme()
        clear_screen()
        print_banner(theme)
        bots = storage.get_bots()
        webhooks = storage.get_webhooks()
        display_fleet_list(bots, webhooks, theme)

        console.print(f"[bold {theme.accent}]Управление профилями отправителей (Fleet):[/]")
        console.print(f"  [{theme.accent}]1[/] Добавить Discord Бота (Токен)")
        console.print(f"  [{theme.accent}]2[/] Добавить Webhook (URL)")
        console.print(f"  [{theme.accent}]3[/] Удалить бота")
        console.print(f"  [{theme.accent}]4[/] Удалить вебхук")
        console.print(f"  [{theme.accent}]0[/] Назад в Главное Меню\n")

        choice = ask_choice("Выберите действие >", choices=["0", "1", "2", "3", "4"], default="0", theme=theme)
        if choice == "0":
            break
        elif choice == "1":
            alias = Prompt.ask(f"[{theme.accent}]Имя / Алиас бота (например: @NewsBot, @GiveawayBot)[/]").strip()
            token = Prompt.ask(f"[{theme.accent}]Discord Bot Token[/]").strip()
            if alias and token:
                storage.save_bot(alias, token)
                console.print(f"[{GREEN}]✓ Бот-профиль '{alias}' сохранён![/]")
            Prompt.ask(f"\n{t('press_enter')}")
        elif choice == "2":
            alias = Prompt.ask(f"[{theme.accent}]Имя / Алиас вебхука (например: #announcements)[/]").strip()
            url = Prompt.ask(f"[{theme.accent}]Discord Webhook URL[/]").strip()
            if client.is_valid_url(url):
                storage.save_webhook(alias or "default", url)
                console.print(f"[{GREEN}]✓ Профиль вебхука '{alias}' сохранён![/]")
            else:
                console.print(f"[{RED}]Неверный URL вебхука Discord.[/]")
            Prompt.ask(f"\n{t('press_enter')}")
        elif choice == "3":
            if not bots:
                console.print(f"[{RED}]Нет сохранённых ботов.[/]")
            else:
                alias = Prompt.ask("Имя бота для удаления", choices=list(bots.keys()))
                storage.remove_bot(alias)
                console.print(f"[{GREEN}]✓ Бот '{alias}' удалён.[/]")
            Prompt.ask(f"\n{t('press_enter')}")
        elif choice == "4":
            if not webhooks:
                console.print(f"[{RED}]Нет сохранённых вебхуков.[/]")
            else:
                alias = Prompt.ask("Имя вебхука для удаления", choices=list(webhooks.keys()))
                storage.remove_webhook(alias)
                console.print(f"[{GREEN}]✓ Вебхук '{alias}' удалён.[/]")
            Prompt.ask(f"\n{t('press_enter')}")


# --- Live Giveaway & Listener Dashboard ---

def action_live_giveaways_menu() -> None:
    theme = get_current_theme()
    clear_screen()
    print_banner(theme)
    console.print(f"[bold {theme.accent}]=== {t('menu_giveaways')} ===[/]\n")

    if is_listener_running():
        console.print(f"[bold #57F287]● Слушатель кнопок сейчас АКТИВЕН в фоне![/]")
        console.print(f"[{MUTED}]Бот обрабатывает нажатия кнопок в Discord в реальном времени.[/]\n")
        console.print(f"  [{theme.accent}]1[/] Открыть пульт управления (Roll Winner / Список участников)")
        console.print(f"  [{theme.accent}]2[/] Остановить фоновый слушатель")
        console.print(f"  [{theme.accent}]0[/] Назад в главное меню\n")

        c = ask_choice("Действие >", default="1", theme=theme)
        if c == "1":
            token = storage.get_bot_token()
            run_interactive_dashboard(token)
            return
        elif c == "2":
            stop_background_listener()
            console.print(f"[{GREEN}]✓ Слушатель бота остановлен.[/]")
            Prompt.ask(f"\n{t('press_enter')}")
            return
        else:
            return

    active_g = storage.list_active_giveaways()
    if active_g:
        console.print(f"[bold white]Активные розыгрыши в базе:[/]")
        for idx, g in enumerate(active_g, start=1):
            parts = len(g.get("participants", []))
            prize = g.get("prize", "Nitro")
            end_t = g.get("end_time", "")
            console.print(f"  [{theme.accent}]{idx}[/] [bold white]{g.get('title', 'Розыгрыш')}[/] • Приз: [cyan]{prize}[/cyan] • Участников: [green]{parts}[/green] • Окончание: [{MUTED}]{end_t[:19].replace('T', ' ')} UTC[/]")
        console.print("")

    bots = storage.get_bots()
    if not bots:
        console.print(f"[{RED}]Для работы слушателя требуется хотя бы один бот в профилях.[/]")
        token = Prompt.ask(f"[{theme.accent}]Введите Discord Bot Token[/]").strip()
        if not token:
            return
        storage.save_bot("DefaultBot", token)
        bots = storage.get_bots()

    # Choose bot
    token = storage.get_bot_token()
    bot_alias = "DefaultBot"
    if len(bots) > 1:
        console.print(f"[bold white]Выберите бота для слушателя:[/]")
        b_keys = list(bots.keys())
        for idx, k in enumerate(b_keys, start=1):
            console.print(f"  [{theme.accent}]{idx}[/] @{k}")
        b_c = ask_choice("Бот >", default="1", theme=theme)
        if b_c.isdigit() and 1 <= int(b_c) <= len(b_keys):
            bot_alias = b_keys[int(b_c) - 1]
            token = bots[bot_alias].get("token", token)
    elif bots:
        bot_alias = list(bots.keys())[0]

    ch_input = Prompt.ask(f"[{MUTED}]ID Discord канала для публикации победителя (Enter — без автопоста)[/]", default="").strip()
    channel_id = int(ch_input) if ch_input.isdigit() else None

    console.print(f"\n[bold {theme.accent}]Режим запуска слушателя:[/]")
    console.print(f"  [{theme.accent}]1[/] [bold #57F287]В отдельном окне[/] (Рекомендуется — бот онлайн 24/7 в фоновом окне)")
    console.print(f"  [{theme.accent}]2[/] [bold #5865F2]Свернуть сразу в системный трей[/] (Окно скрыто, бот у часов Windows)")
    console.print(f"  [{theme.accent}]3[/] Прямо здесь в терминале (Командный центр, модерация)")
    l_mode = ask_choice("Режим >", choices=["1", "2", "3"], default="1", theme=theme)
    if l_mode == "1":
        launch_listener_in_new_window(bot_alias)
        console.print(f"[{GREEN}]✓ Фоновый слушатель запущен в новом окне![/]")
        Prompt.ask(f"\n{t('press_enter')}")
        return
    elif l_mode == "2":
        launch_listener_in_new_window(bot_alias, tray=True)
        console.print(f"[{GREEN}]✓ Слушатель запущен и свёрнут в системный трей! Бот онлайн 24/7.[/]")
        Prompt.ask(f"\n{t('press_enter')}")
        return

    # Load active giveaway or default template
    giveaway_emb = storage.load_template("giveaway")
    run_interactive_dashboard(token, embed=giveaway_emb, channel_id=channel_id, bot_alias=bot_alias)


# --- Bot Engines ---

def edit_automod_menu(cfg: AutoModConfig, theme: UITheme) -> None:
    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Настройка модуля 🛡️ AutoMod ===[/]\n")
        status_str = "[bold #57F287]ВКЛЮЧЁН[/]" if cfg.enabled else f"[{MUTED}]ВЫКЛЮЧЕН[/]"
        console.print(f"  Статус модуля: {status_str}\n")
        console.print(f"  [{theme.accent}]1[/] Переключить статус (Вкл / Выкл)")
        console.print(f"  [{theme.accent}]2[/] Анти-Инвайты (блокировка ссылок discord.gg) : {'[#57F287]ВКЛ[/]' if cfg.anti_invite else '[#ED4245]ВЫКЛ[/]'}")
        console.print(f"  [{theme.accent}]3[/] Анти-Спам (флуд более 4 сообщений в 3 сек)   : {'[#57F287]ВКЛ[/]' if cfg.anti_spam else '[#ED4245]ВЫКЛ[/]'}")
        console.print(f"  [{theme.accent}]4[/] Анти-Капс (удаление сообщений заглавными)    : {'[#57F287]ВКЛ[/]' if cfg.anti_caps else '[#ED4245]ВЫКЛ[/]'}")
        bw_preview = ", ".join(cfg.bad_words) if cfg.bad_words else f"[{MUTED}]нет[/]"
        console.print(f"  [{theme.accent}]5[/] Список запрещённых слов (банворды)          : {bw_preview}")
        log_ch_preview = str(cfg.log_channel_id) if cfg.log_channel_id else f"[{MUTED}]не задан[/]"
        console.print(f"  [{theme.accent}]6[/] ID канала для логов модерации                : {log_ch_preview}")
        console.print(f"  [{theme.accent}]7[/] Команды модератора в чате (!ban, !mute, !clear): {'[#57F287]ВКЛ[/]' if cfg.chat_commands else '[#ED4245]ВЫКЛ[/]'}")
        console.print(f"  [{theme.accent}]0[/] Назад к модулям\n")

        c = ask_choice("Действие >", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="0", theme=theme)
        if c == "0":
            break
        elif c == "1":
            cfg.enabled = not cfg.enabled
        elif c == "2":
            cfg.anti_invite = not cfg.anti_invite
        elif c == "3":
            cfg.anti_spam = not cfg.anti_spam
        elif c == "4":
            cfg.anti_caps = not cfg.anti_caps
        elif c == "5":
            words = Prompt.ask(f"[{theme.accent}]Введите запрещённые слова через запятую[/]", default=",".join(cfg.bad_words)).strip()
            cfg.bad_words = [w.strip() for w in words.split(",") if w.strip()]
        elif c == "6":
            ch = Prompt.ask(f"[{theme.accent}]Введите ID текстового канала для логов (или Enter для сброса)[/]", default=str(cfg.log_channel_id or "")).strip()
            cfg.log_channel_id = int(ch) if ch.isdigit() else None
        elif c == "7":
            cfg.chat_commands = not cfg.chat_commands


def edit_ai_menu(cfg: AIAssistantConfig, theme: UITheme) -> None:
    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Настройка модуля 🧠 AI Чат-Бот ===[/]\n")
        status_str = "[bold #00D9FF]ВКЛЮЧЁН[/]" if cfg.enabled else f"[{MUTED}]ВЫКЛЮЧЕН[/]"
        console.print(f"  Статус модуля: {status_str}\n")
        console.print(f"  [{theme.accent}]1[/] Переключить статус (Вкл / Выкл)")
        console.print(f"  [{theme.accent}]2[/] Провайдер нейросети : [bold white]{cfg.provider.upper()}[/] (Модель: {cfg.model})")
        key_preview = (cfg.api_key[:6] + "..." + cfg.api_key[-4:]) if len(cfg.api_key) > 10 else (f"[{MUTED}]не задан[/]")
        console.print(f"  [{theme.accent}]3[/] API Ключ          : {key_preview}")
        console.print(f"  [{theme.accent}]4[/] Системный промпт : [white]{cfg.system_prompt[:40]}...[/white]")
        console.print(f"  [{theme.accent}]5[/] Режим активации   : [white]{cfg.trigger_mode}[/white] (Канал: {cfg.channel_id or 'любой'})")
        console.print(f"  [{theme.accent}]0[/] Назад к модулям\n")

        c = ask_choice("Действие >", choices=["0", "1", "2", "3", "4", "5"], default="0", theme=theme)
        if c == "0":
            break
        elif c == "1":
            cfg.enabled = not cfg.enabled
        elif c == "2":
            console.print(f"\n[bold {theme.accent}]Выберите провайдера нейросети:[/]")
            console.print(f"  [{theme.accent}]1[/] Google Gemini (Бесплатный ключ на aistudio.google.com)")
            console.print(f"  [{theme.accent}]2[/] OpenAI (ChatGPT / gpt-4o-mini)")
            console.print(f"  [{theme.accent}]3[/] Groq (Сверхбыстрый Llama-3)")
            console.print(f"  [{theme.accent}]4[/] OpenRouter (Универсальный доступ ко всем моделям)")
            p_pick = ask_choice("Провайдер >", choices=["1", "2", "3", "4"], default="1", theme=theme)
            p_map = {
                "1": ("gemini", "gemini-1.5-flash"),
                "2": ("openai", "gpt-4o-mini"),
                "3": ("groq", "llama-3.3-70b-versatile"),
                "4": ("openrouter", "meta-llama/llama-3.3-70b-instruct"),
            }
            cfg.provider, cfg.model = p_map.get(p_pick, ("gemini", "gemini-1.5-flash"))
        elif c == "3":
            key_val = Prompt.ask(f"[{theme.accent}]Введите ваш API ключ[/]", default=cfg.api_key).strip()
            if key_val:
                cfg.api_key = key_val
        elif c == "4":
            prompt_val = Prompt.ask(f"[{theme.accent}]Задайте характер / промпт бота[/]", default=cfg.system_prompt).strip()
            if prompt_val:
                cfg.system_prompt = prompt_val
        elif c == "5":
            console.print(f"\n[bold {theme.accent}]Когда бот должен отвечать в Discord:[/]")
            console.print(f"  [{theme.accent}]1[/] Только при упоминании (@Бот привет...)")
            console.print(f"  [{theme.accent}]2[/] На каждое сообщение в отдельном канале")
            console.print(f"  [{theme.accent}]3[/] И при упоминании, и в отдельном канале")
            m_pick = ask_choice("Режим >", choices=["1", "2", "3"], default="1", theme=theme)
            m_map = {"1": "mention", "2": "channel", "3": "both"}
            cfg.trigger_mode = m_map.get(m_pick, "mention")
            if cfg.trigger_mode in ("channel", "both"):
                ch = Prompt.ask(f"[{theme.accent}]Введите ID текстового канала для AI общения[/]", default=str(cfg.channel_id or "")).strip()
                cfg.channel_id = int(ch) if ch.isdigit() else None


def edit_welcomer_menu(cfg: WelcomerConfig, theme: UITheme) -> None:
    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Настройка модуля 👋 Welcomer & Авто-роли ===[/]\n")
        status_str = "[bold #EBAF8E]ВКЛЮЧЁН[/]" if cfg.enabled else f"[{MUTED}]ВЫКЛЮЧЕН[/]"
        console.print(f"  Статус модуля: {status_str}\n")
        console.print(f"  [{theme.accent}]1[/] Переключить статус (Вкл / Выкл)")
        role_preview = str(cfg.auto_role_id) if cfg.auto_role_id else f"[{MUTED}]не задана[/]"
        console.print(f"  [{theme.accent}]2[/] ID роли для новичков (Auto-Role)   : {role_preview}")
        ch_preview = str(cfg.welcome_channel_id) if cfg.welcome_channel_id else f"[{MUTED}]не задан[/]"
        console.print(f"  [{theme.accent}]3[/] ID канала для приветствий (Welcome) : {ch_preview}")
        console.print(f"  [{theme.accent}]4[/] Текст приветствия                   : [white]{cfg.welcome_title}[/white]")
        console.print(f"  [{theme.accent}]0[/] Назад к модулям\n")

        c = ask_choice("Действие >", choices=["0", "1", "2", "3", "4"], default="0", theme=theme)
        if c == "0":
            break
        elif c == "1":
            cfg.enabled = not cfg.enabled
        elif c == "2":
            r_str = Prompt.ask(f"[{theme.accent}]Введите ID роли Discord для автовыдачи (или Enter для сброса)[/]", default=str(cfg.auto_role_id or "")).strip()
            cfg.auto_role_id = int(r_str) if r_str.isdigit() else None
        elif c == "3":
            c_str = Prompt.ask(f"[{theme.accent}]Введите ID канала для приветственных карточек[/]", default=str(cfg.welcome_channel_id or "")).strip()
            cfg.welcome_channel_id = int(c_str) if c_str.isdigit() else None
        elif c == "4":
            t_str = Prompt.ask(f"[{theme.accent}]Заголовок приветствия (доступны теги: {{user}}, {{guild}})[/]", default=cfg.welcome_title).strip()
            if t_str:
                cfg.welcome_title = t_str


def edit_tickets_menu(cfg: TicketConfig, theme: UITheme, bot_alias: str = "DefaultBot") -> None:
    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Настройка модуля 🎫 Тикет-система ===[/]\n")
        status_str = "[bold #5865F2]ВКЛЮЧЁН[/]" if cfg.enabled else f"[{MUTED}]ВЫКЛЮЧЕН[/]"
        console.print(f"  Статус модуля: {status_str}\n")
        console.print(f"  [{theme.accent}]1[/] Переключить статус (Вкл / Выкл)")
        role_preview = str(cfg.support_role_id) if cfg.support_role_id else f"[{MUTED}]не задана (только админы)[/]"
        console.print(f"  [{theme.accent}]2[/] ID роли модераторов / поддержки : {role_preview}")
        console.print(f"  [{theme.accent}]3[/] 🚀 Развернуть панель тикетов в канале Discord")
        console.print(f"  [{theme.accent}]0[/] Назад к модулям\n")

        c = ask_choice("Действие >", choices=["0", "1", "2", "3"], default="0", theme=theme)
        if c == "0":
            break
        elif c == "1":
            cfg.enabled = not cfg.enabled
        elif c == "2":
            r_str = Prompt.ask(f"[{theme.accent}]Введите ID роли Discord модераторов поддержки[/]", default=str(cfg.support_role_id or "")).strip()
            cfg.support_role_id = int(r_str) if r_str.isdigit() else None
        elif c == "3":
            bots = storage.get_bots()
            token = bots.get(bot_alias, {}).get("token", "") or storage.get_bot_token()
            if not token:
                console.print(f"[{RED}]Ошибка: токен бота не найден. Сначала добавьте бота в профили.[/]")
                Prompt.ask(t("press_enter"))
                continue

            ch_str = Prompt.ask(f"[{theme.accent}]Введите ID Discord канала для панели тикетов (Channel ID)[/]").strip()
            if not ch_str.isdigit():
                console.print(f"[{RED}]ID канала должен состоять только из цифр.[/]")
                Prompt.ask(t("press_enter"))
                continue
            channel_id = int(ch_str)

            title = Prompt.ask(f"[{theme.accent}]Заголовок карточки тикетов[/]", default="📩 Служба поддержки и тикеты").strip()
            desc = Prompt.ask(f"[{theme.accent}]Описание карточки тикетов[/]", default="Возник вопрос или нужна помощь? Создайте приватный тикет с администрацией с помощью меню ниже:").strip()
            console.print(f"\n[bold {theme.accent}]Формат интерфейса тикетов:[/]")
            console.print(f"  [{theme.accent}]1[/] Обычная кнопка: [ 📩 Создать тикет ]")
            console.print(f"  [{theme.accent}]2[/] Выпадающий список категорий (Общий вопрос, Жалоба, Донат, Техпомощь)")
            v_type = ask_choice("Формат >", choices=["1", "2"], default="2", theme=theme)
            use_select = (v_type == "2")

            try:
                with console.status("Развёртывание панели тикетов на сервере..."):
                    ok, msg = deploy_ticket_panel(
                        token=token,
                        channel_id=channel_id,
                        title=title,
                        desc=desc,
                        use_select=use_select,
                        support_role_id=cfg.support_role_id,
                    )
                if ok:
                    cfg.enabled = True
                    console.print(f"\n[{GREEN}]✓ {msg}[/]\n")
                    console.print(f"[bold #EBAF8E]⚠️ ВАЖНО:[/] Кнопка и меню тикетов в Discord работают только когда бот [bold #57F287]ОНЛАЙН[/] (запущен слушатель).")
                    console.print(f"[{MUTED}]Если бот выключен, Discord показывает: «Приложение не ответило вовремя».[/]\n")
                    console.print(f"  [{theme.accent}]1[/] [bold #57F287]Запустить бота в отдельном окне прямо сейчас[/] (24/7 в фоне, можно дальше пользоваться меню)")
                    console.print(f"  [{theme.accent}]2[/] Запустить прямо здесь в терминале (Командный центр PRISM)")
                    console.print(f"  [{theme.accent}]0[/] Вернуться в меню (запустить бота вручную позже)\n")
                    start_c = ask_choice("Действие >", choices=["0", "1", "2"], default="1", theme=theme)
                    if start_c == "1":
                        launch_listener_in_new_window(bot_alias)
                        console.print(f"\n[{GREEN}]✓ Слушатель бота запущен в отдельном окне! Теперь бот онлайн и кнопки в Discord активны.[/]")
                        Prompt.ask(t("press_enter"))
                    elif start_c == "2":
                        storage.save_bot_engines_config(bot_alias, cfg.__dict__)
                        run_interactive_dashboard(token, bot_alias=bot_alias)
                        return
                else:
                    console.print(f"\n[{RED}]✗ Ошибка: {escape(msg)}[/]\n")
                    Prompt.ask(t("press_enter"))
            except Exception as e:
                console.print(f"\n[{RED}]✗ Ошибка: {escape(str(e))}[/]\n")
                Prompt.ask(t("press_enter"))


def action_bot_engines_menu() -> None:
    theme = get_current_theme()
    bots = storage.get_bots()
    if not bots:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Конструктор Ботов ===[/]\n")
        console.print(f"[{RED}]Для настройки модулей сначала добавьте бота в профили.[/]")
        token = Prompt.ask(f"[{theme.accent}]Введите Discord Bot Token[/]").strip()
        if not token:
            return
        alias = Prompt.ask(f"[{theme.accent}]Имя бота (например: MyBot)[/]", default="MyBot").strip()
        storage.save_bot(alias, token, alias)
        bots = storage.get_bots()

    bot_alias = next(iter(bots))
    if len(bots) > 1:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]Выберите бота для настройки модулей:[/]\n")
        b_keys = list(bots.keys())
        for idx, k in enumerate(b_keys, start=1):
            console.print(f"  [{theme.accent}]{idx}[/] @{k}")
        c = ask_choice("Бот >", default="1", theme=theme)
        if c.isdigit() and 1 <= int(c) <= len(b_keys):
            bot_alias = b_keys[int(c) - 1]

    raw_cfg = storage.get_bot_engines_config(bot_alias)
    settings = BotEngineSettings.from_dict(raw_cfg) if raw_cfg else BotEngineSettings(bot_alias=bot_alias)

    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Конструктор Ботов • @{bot_alias} ===[/]\n")

        am_status = "[bold #57F287]ВКЛ[/]" if settings.automod.enabled else f"[{MUTED}]ВЫКЛ[/]"
        ai_status = f"[bold #00D9FF]ВКЛ ({settings.ai.provider})[/]" if settings.ai.enabled else f"[{MUTED}]ВЫКЛ[/]"
        w_status = "[bold #EBAF8E]ВКЛ[/]" if settings.welcomer.enabled else f"[{MUTED}]ВЫКЛ[/]"
        t_status = "[bold #5865F2]ВКЛ[/]" if settings.tickets.enabled else f"[{MUTED}]ВЫКЛ[/]"

        console.print(f"  [{theme.accent}]1[/] 🛡️  AutoMod (Анти-спам, анти-инвайты, банворды, логи) : {am_status}")
        console.print(f"  [{theme.accent}]2[/] 🧠 AI Чат-Бот (Gemini, OpenAI, Groq, память диалога)   : {ai_status}")
        console.print(f"  [{theme.accent}]3[/] 👋 Welcomer & Авто-роли (Выдача роли, карточка входа)  : {w_status}")
        console.print(f"  [{theme.accent}]4[/] 🎫 Тикет-система (Приватные ветки поддержки в чате)   : {t_status}")
        console.print(f"[{MUTED}]---------------------------------------------------------------[/]")
        console.print(f"  [bold {GREEN}]R[/] [bold white]🚀 Запустить бота со всеми активными модулями[/bold white]")
        console.print(f"  [{theme.accent}]0[/] Сохранить и вернуться в главное меню\n")

        ch = ask_choice("Выберите модуль >", choices=["0", "1", "2", "3", "4", "R", "r"], default="0", theme=theme).lower()

        if ch == "0":
            storage.save_bot_engines_config(bot_alias, settings.to_dict())
            break
        elif ch == "r":
            storage.save_bot_engines_config(bot_alias, settings.to_dict())
            token = bots[bot_alias].get("token", "")
            console.print(f"\n[bold {theme.accent}]Запуск бота @{bot_alias} со всеми активными модулями...[/]")
            run_interactive_dashboard(token, bot_alias=bot_alias)
            break
        elif ch == "1":
            edit_automod_menu(settings.automod, theme)
            storage.save_bot_engines_config(bot_alias, settings.to_dict())
        elif ch == "2":
            edit_ai_menu(settings.ai, theme)
            storage.save_bot_engines_config(bot_alias, settings.to_dict())
        elif ch == "3":
            edit_welcomer_menu(settings.welcomer, theme)
            storage.save_bot_engines_config(bot_alias, settings.to_dict())
        elif ch == "4":
            edit_tickets_menu(settings.tickets, theme, bot_alias=bot_alias)
            storage.save_bot_engines_config(bot_alias, settings.to_dict())


# --- Settings: Language & Theme ---

def action_settings_menu() -> None:
    while True:
        theme = get_current_theme()
        current_lang = storage.get_language()
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]{t('settings_title')}[/]\n")
        console.print(f"  {t('settings_current_lang')} [bold white]{current_lang.upper()}[/bold white]")
        console.print(f"  {t('settings_current_theme')} [bold {theme.accent}]{theme.name}[/]\n")

        console.print(f"  [{theme.accent}]1[/] {t('settings_lang')}")
        console.print(f"  [{theme.accent}]2[/] {t('settings_theme')}")
        console.print(f"  [{theme.accent}]0[/] Назад в главное меню\n")

        choice = ask_choice("Выберите настройку >", choices=["0", "1", "2"], default="0", theme=theme)
        if choice == "0":
            break
        elif choice == "1":
            console.print(f"\n[bold {theme.accent}]Выберите язык интерфейса:[/]")
            console.print(f"  [{theme.accent}]1[/] Русский (RU)")
            console.print(f"  [{theme.accent}]2[/] English (EN)")
            console.print(f"  [{theme.accent}]3[/] Авто (По языку системы)")
            lang_c = ask_choice("Язык >", choices=["1", "2", "3"], default="1", theme=theme)
            lang_map = {"1": "ru", "2": "en", "3": "auto"}
            storage.set_language(lang_map[lang_c])
            refresh_locale()
            console.print(f"[{GREEN}]✓ Язык успешно изменён![/]")
            Prompt.ask(f"\n{t('press_enter')}")
        elif choice == "2":
            console.print(f"\n[bold {theme.accent}]Выберите тему оформления:[/]")
            t_list = list_themes()
            for idx, th in enumerate(t_list, start=1):
                console.print(f"  [{th.accent}]{idx}[/] [{th.accent}]■ {th.name}[/]")
            th_c = ask_choice("Тема >", choices=[str(i) for i in range(1, len(t_list) + 1)], default="1", theme=theme)
            if th_c.isdigit() and 1 <= int(th_c) <= len(t_list):
                selected_theme = t_list[int(th_c) - 1]
                storage.set_theme(selected_theme.id)
                console.print(f"[{GREEN}]✓ Тема '{selected_theme.name}' успешно применена![/]")
            Prompt.ask(f"\n{t('press_enter')}")


# --- Sent Messages Management ---

def action_manage_messages() -> None:
    theme = get_current_theme()
    while True:
        clear_screen()
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== {t('menu_messages')} ===[/]\n")
        console.print(f"  [{theme.accent}]1[/] Редактировать отправленное сообщение (по ID)")
        console.print(f"  [{theme.accent}]2[/] Удалить отправленное сообщение (по ID)")
        console.print(f"  [{theme.accent}]0[/] Назад в меню\n")

        c = ask_choice("Выберите действие >", choices=["0", "1", "2"], default="0", theme=theme)
        if c == "0":
            break

        history = storage.get_history(limit=8)
        selected_item = None
        msg_id = ""
        if history:
            console.print(f"\n[{MUTED}]Недавно отправленные сообщения:[/]")
            for idx, item in enumerate(history, start=1):
                sender_badge = f"[#57F287]{item.get('sender', 'unknown')}[/#57F287]"
                console.print(f"  [{theme.accent}]{idx}[/] ID: [cyan]{item['id']}[/cyan] ({sender_badge}) • [white]{item['title']}[/white]")
            choice = Prompt.ask("Номер из списка или введите ID вручную").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(history):
                selected_item = history[int(choice) - 1]
                msg_id = str(selected_item["id"])
            else:
                msg_id = choice
        else:
            msg_id = Prompt.ask(f"[{theme.accent}]Введите Discord Message ID[/]").strip()

        if not msg_id:
            continue

        sender_type = "bot"
        bot_alias = ""
        channel_id = 0
        webhook_url = ""

        if selected_item and selected_item.get("sender", "").startswith("bot_@"):
            sender_type = "bot"
            bot_alias = selected_item["sender"].replace("bot_@", "")
            channel_id = selected_item.get("channel_id") or 0
        elif selected_item and selected_item.get("sender", "").startswith("webhook_#"):
            sender_type = "webhook"
            alias = selected_item["sender"].replace("webhook_#", "")
            webhook_url = storage.get_webhook(alias)
        else:
            console.print(f"\n[bold {theme.accent}]Как было отправлено это сообщение:[/]")
            console.print(f"  [{theme.accent}]1[/] Через Бота (Bot token)")
            console.print(f"  [{theme.accent}]2[/] Через Webhook URL")
            m_pick = ask_choice("Тип >", choices=["1", "2"], default="1", theme=theme)
            sender_type = "bot" if m_pick == "1" else "webhook"

        token = ""
        if sender_type == "bot":
            bots = storage.get_bots()
            if bot_alias and bot_alias in bots:
                token = bots[bot_alias].get("token", "")
            if not token:
                token = storage.get_bot_token()
            if not token:
                token = Prompt.ask(f"[{theme.accent}]Введите Discord Bot Token[/]").strip()
            if not channel_id:
                ch_in = Prompt.ask(f"[{theme.accent}]Введите ID канала, где находится сообщение[/]").strip()
                if ch_in.isdigit():
                    channel_id = int(ch_in)

        elif sender_type == "webhook":
            if not webhook_url:
                webhook_url = Prompt.ask(f"[{theme.accent}]Введите Webhook URL[/]").strip()

        if c == "1":
            templates = storage.list_templates()
            display_template_list(templates, theme=theme)
            tpl = ask_choice("Выберите шаблон для замены >", default="1", theme=theme)
            selected_name = templates[int(tpl) - 1] if tpl.isdigit() and 1 <= int(tpl) <= len(templates) else tpl
            emb = storage.load_template(selected_name)
            if not emb:
                console.print(f"[{RED}]Шаблон не найден.[/]")
                Prompt.ask(t("press_enter"))
                continue

            render_embed_preview(emb, theme=theme)
            if Confirm.ask(f"Обновить сообщение [cyan]{msg_id}[/cyan] в Discord?", default=True):
                try:
                    with console.status("Обновление сообщения на серверах Discord..."):
                        if sender_type == "bot" and channel_id and msg_id.isdigit():
                            ok, res_msg = edit_bot_message(token, channel_id, int(msg_id), emb)
                            if ok:
                                console.print(f"[{GREEN}]✓ {res_msg}[/]")
                            else:
                                console.print(f"[{RED}]✗ Ошибка: {escape(res_msg)}[/]")
                        else:
                            client.edit(url=webhook_url, message_id=msg_id, embed=emb)
                            console.print(f"[{GREEN}]✓ Сообщение {msg_id} успешно обновлено через Webhook![/]")
                except Exception as e:
                    console.print(f"[{RED}]✗ Ошибка обновления: {escape(str(e))}[/]")
            Prompt.ask(f"\n{t('press_enter')}")

        elif c == "2":
            if Confirm.ask(f"Вы уверены, что хотите удалить сообщение [cyan]{msg_id}[/cyan]?", default=False):
                try:
                    with console.status("Удаление сообщения из Discord..."):
                        if sender_type == "bot" and channel_id and msg_id.isdigit():
                            ok, res_msg = delete_bot_message(token, channel_id, int(msg_id))
                            if ok:
                                storage.delete_history_item(msg_id)
                                console.print(f"[{GREEN}]✓ {res_msg}[/]")
                            else:
                                console.print(f"[{RED}]✗ Ошибка удаления: {escape(res_msg)}[/]")
                        else:
                            client.delete(url=webhook_url, message_id=msg_id)
                            storage.delete_history_item(msg_id)
                            console.print(f"[{GREEN}]✓ Сообщение {msg_id} удалено через Webhook.[/]")
                except Exception as e:
                    console.print(f"[{RED}]✗ Ошибка удаления: {escape(str(e))}[/]")
            Prompt.ask(f"\n{t('press_enter')}")


# --- Main Menu ---

def main_menu() -> None:
    while True:
        refresh_locale()
        theme = get_current_theme()
        clear_screen()
        print_banner(theme)

        menu_table = Table.grid(padding=(0, 2))
        menu_table.add_column(style=f"bold {theme.accent}", justify="right")
        menu_table.add_column(style="white")

        menu_table.add_row("1", t("menu_send"))
        menu_table.add_row("2", t("menu_studio"))
        menu_table.add_row("3", t("menu_engines"))
        menu_table.add_row("4", t("menu_fleet"))
        menu_table.add_row("5", t("menu_giveaways"))
        menu_table.add_row("6", t("menu_messages"))
        menu_table.add_row("7", t("menu_settings"))
        menu_table.add_row("0", t("menu_exit"))

        sub_title = (
            f"[{MUTED}]v2.0 • by an1zy • [/][bold #57F287]● Слушатель АКТИВЕН в фоне[/]"
            if is_listener_running()
            else f"[{MUTED}]v2.0 • by an1zy • {t('app_subtitle')}[/]"
        )

        panel = Panel(
            menu_table,
            border_style=theme.accent,
            title=f"[{theme.accent}]{t('menu_title')}[/]",
            subtitle=sub_title,
            padding=(1, 3),
        )
        console.print(panel)
        console.print("")

        choice = ask_choice(t("prompt_action"), choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1", theme=theme)

        if choice == "0":
            stop_background_listener()
            console.print(f"\n[{theme.accent}]{t('exit_farewell')}[/]\n")
            sys.exit(0)
        elif choice == "1":
            action_send_flow()
        elif choice == "2":
            action_interactive_builder()
        elif choice == "3":
            action_bot_engines_menu()
        elif choice == "4":
            action_manage_fleet()
        elif choice == "5":
            action_live_giveaways_menu()
        elif choice == "6":
            action_manage_messages()
        elif choice == "7":
            action_settings_menu()


def parse_cli_args() -> None:
    parser = argparse.ArgumentParser(description="PRISM - Discord Bot Management & Control Suite by an1zy")
    parser.add_argument("--send", type=str, help="Preset name to send headlessly")
    parser.add_argument("--webhook", type=str, help="Discord Webhook URL or saved alias")
    parser.add_argument("--content", type=str, default="", help="Message text or mention ping")
    parser.add_argument("--preview", type=str, help="Preview a template in the console")
    parser.add_argument("--list", action="store_true", help="List all available presets")
    parser.add_argument("--listen", action="store_true", help="Run 24/7 background listener for bot buttons & engines")
    parser.add_argument("--bot", type=str, default="", help="Bot alias to run with --listen")
    parser.add_argument("--tray", action="store_true", help="Run listener minimized directly into Windows system tray")

    args = parser.parse_args()
    theme = get_current_theme()

    if args.listen:
        print_banner(theme)
        console.print(f"[bold {theme.accent}]=== Фоновый процесс PRISM Listener (24/7 Daemon) ===[/]\n")
        bots = storage.get_bots()
        target_alias = args.bot or ""
        token = ""
        if target_alias and target_alias in bots:
            token = bots[target_alias].get("token", "")
        elif bots:
            target_alias = list(bots.keys())[0]
            token = bots[target_alias].get("token", "")
        else:
            token = storage.get_bot_token()
            target_alias = "DefaultBot"

        if not token:
            console.print(f"[{RED}]Ошибка: токен бота не настроен. Добавьте бота в PRISM Studio.[/]")
            sys.exit(1)

        console.print(f"[{GREEN}]✓ Подключение бота @{target_alias} к Discord Gateway...[/]")
        console.print(f"[{MUTED}]Слушатель перехватывает клики по кнопкам, спискам, таймеры, AutoMod и AI.[/]")
        console.print(f"[{MUTED}]Для завершения работы нажмите Ctrl+C[/]\n")

        if args.tray:
            try:
                from core.tray import minimize_to_tray
                minimize_to_tray(bot_alias=target_alias)
            except Exception as te:
                console.print(f"[{RED}]Ошибка трея: {escape(str(te))}[/]")

        try:
            listener = PrismInteractiveListener(token, bot_alias=target_alias)
            import asyncio
            asyncio.run(listener.run())
        except KeyboardInterrupt:
            console.print(f"\n[{MUTED}]Фоновый слушатель остановлен.[/]")
        sys.exit(0)

    if args.list:
        print_banner(theme)
        display_template_list(storage.list_templates(), theme=theme)
        sys.exit(0)

    if args.preview:
        print_banner(theme)
        emb = storage.load_template(args.preview)
        if not emb:
            console.print(f"[{RED}]Шаблон '{args.preview}' не найден.[/]")
            sys.exit(1)
        render_embed_preview(emb, theme=theme)
        sys.exit(0)

    if args.send:
        emb = storage.load_template(args.send)
        if not emb:
            console.print(f"[{RED}]Шаблон '{args.send}' не найден.[/]")
            sys.exit(1)

        url = args.webhook
        if url and not client.is_valid_url(url):
            url = storage.get_webhook(url)

        if not url or not client.is_valid_url(url):
            console.print(f"[{RED}]Укажите корректный URL вебхука через --webhook.[/]")
            sys.exit(1)

        try:
            resp = client.send(url=url, content=args.content, embed=emb)
            console.print(f"[{GREEN}]✓ Шаблон '{args.send}' успешно отправлен (ID: {resp.get('id')})[/]")
            sys.exit(0)
        except WebhookError as e:
            console.print(f"[{RED}]✗ Ошибка: {escape(str(e))}[/]")
            sys.exit(1)

    main_menu()


if __name__ == "__main__":
    try:
        parse_cli_args()
    except KeyboardInterrupt:
        console.print(f"\n[{MUTED}]{t('op_cancelled')}[/]")
        sys.exit(0)
