"""
PRISM - Internationalization (i18n)
Provides bilingual UI (Russian / English) with auto-detection from system locale.
Author: an1zy (https://github.com/an1zy)
"""

from __future__ import annotations
import locale
import os
import sys
from typing import Dict, Any

_CURRENT_LANGUAGE = "auto"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ru": {
        # App Info
        "app_title": "Управление ботами & Командный центр PRISM",
        "app_subtitle": "Управление ботами • Модули • Командный центр",
        
        # Main Menu
        "menu_title": "Панель управления PRISM",
        "menu_send": "Отправить сообщение (Готовые шаблоны или своё)",
        "menu_studio": "Конструктор сообщений (Собрать эмбед и кнопки по деталям)",
        "menu_engines": "Конструктор ботов (AutoMod, AI Ассистент, Роли, Тикеты)",
        "menu_fleet": "Профили отправителей (Управление ботами и вебхуками)",
        "menu_giveaways": "Слушатель интерактива и Розыгрыши (Live Dashboard)",
        "menu_messages": "Управление отправленными (Редактировать / Удалить)",
        "menu_settings": "Настройки (Язык: RU/EN, Темы оформления)",
        "menu_exit": "Выход из PRISM",
        "prompt_action": "Выберите действие >",
        "press_enter": "Нажмите Enter для возврата в меню...",
        "exit_farewell": "Спасибо за использование PRISM. До встречи!",
        "op_cancelled": "Операция отменена пользователем.",

        # Send Flow
        "send_flow_title": "Отправка сообщения в Discord:",
        "send_opt_template": "Готовые шаблоны (Анонс, статус, правила, розыгрыш, патчноут, тест)",
        "send_opt_scratch": "Собрать новое сообщение с нуля (Конструктор)",
        "send_opt_back": "Назад в меню",
        "send_prompt": "Выберите вариант >",
        "template_preview_title": "Предпросмотр шаблона:",
        "template_what_to_do": "Что сделать с этим шаблоном?",
        "template_action_send": "Отправить в Discord",
        "template_action_edit": "Изменить текст, детали или кнопки под себя (в конструктор)",
        "template_not_found": "Шаблон не найден.",
        "template_saved_success": "Шаблон успешно сохранён:",

        # Modular Studio
        "studio_title": "=== Конструктор сообщения (Детали и компоненты) ===",
        "part_title": "Заголовок",
        "part_desc": "Текст/описание",
        "part_color": "Цвет полоски",
        "part_fields": "Поля (Fields)",
        "part_buttons": "Кнопки (Ссылки / Сценарии)",
        "part_image": "Картинка/баннер",
        "part_author": "Автор / Иконка",
        "part_footer": "Нижний текст (Футер)",
        "action_dispatch": "Отправить в Discord",
        "action_save_tpl": "Сохранить как шаблон",
        "action_clear": "Очистить всё",
        "action_back": "Назад в главное меню",
        "prompt_detail": "Выберите деталь для изменения >",
        "prompt_title": "Заголовок",
        "prompt_url": "Ссылка при клике (или пусто)",
        "prompt_desc": "Текст / Описание",
        "prompt_img": "URL большой картинки/баннера (или пусто)",
        "prompt_thumb": "URL миниатюры справа сверху (или пусто)",
        "prompt_author_name": "Имя автора (или пусто)",
        "prompt_author_icon": "URL аватарки автора",
        "prompt_author_url": "Ссылка на автора",
        "prompt_footer_text": "Текст внизу (Футер)",
        "prompt_timestamp": "Показывать текущее время (timestamp)?",
        "prompt_tpl_name": "Введите название для нового шаблона (например: my_event)",
        "reset_confirm": "Сбросить сообщение до чистого листа?",

        # Sender Selection (Fleet)
        "sender_select_title": "Выберите отправителя сообщения:",
        "sender_via_bot": "Отправить через Discord Бот (поддерживает живые кнопки и роли)",
        "sender_via_webhook": "Отправить через Webhook (быстро, только ссылки)",
        "sender_choose_bot": "Выберите бота из сохранённых профилей:",
        "sender_add_new_bot": "Добавить нового бота (токен)",
        "sender_choose_webhook": "Выберите вебхук из профилей:",
        "sender_add_new_webhook": "Ввести другой Webhook URL вручную",
        "sender_channel_id": "Введите ID текстового канала Discord (Channel ID)",
        "sender_ping_content": "Текст над сообщением / пинг (например @everyone или пусто)",
        "sender_dispatch_now": "Отправить сообщение в Discord прямо сейчас?",
        "sender_success_bot": "✓ Сообщение успешно отправлено ботом @{bot} в канал {channel}! (ID: {id})",
        "sender_success_webhook": "✓ Сообщение успешно отправлено в Discord! (ID: {id})",

        # Buttons Menu
        "buttons_title": "=== Настройка кнопок Discord (ActionRow) ===",
        "buttons_empty": "Кнопок пока нет. Вы можете прикрепить до 5 кнопок со ссылками или сценариями.",
        "buttons_add": "Добавить кнопку",
        "buttons_remove": "Удалить кнопку",
        "buttons_clear": "Очистить все кнопки",
        "buttons_save_back": "Сохранить и вернуться в конструктор",
        "btn_type_link": "Кнопка-ссылка (Link Button) ↗",
        "btn_type_link_desc": "Открывает сайт, Telegram, Discord инвайт. Работает через любой вебхук сразу.",
        "btn_type_giveaway": "Сценарий: Розыгрыш (Giveaway 🎉)",
        "btn_type_giveaway_desc": "Кнопка «Участвовать», авто-сбор участников, таймер и случайный выбор победителя.",
        "btn_type_verify": "Сценарий: Верификация / Выдача роли (Verify ✅)",
        "btn_type_verify_desc": "Кнопка подтверждения правил и РЕАЛЬНАЯ выдача роли на сервере.",
        "btn_type_custom": "Свой сценарий (Custom Pop-up 💬)",
        "btn_type_custom_desc": "Кастомная кнопка и персональный ответ-невидимка для нажавшего.",
        "btn_prompt_label": "Текст на кнопке",
        "btn_prompt_url": "URL ссылки (куда ведёт клик)",
        "btn_prompt_emoji": "Эмодзи перед текстом (или пусто)",
        "btn_prompt_role": "ID роли для выдачи (Role ID, или Enter — только подтверждение)",
        "btn_prompt_response": "Ответ пользователю при клике (эфемерное сообщение)",
        "btn_prompt_prize": "Название приза для розыгрыша (например: Discord Nitro Full)",
        "btn_prompt_minutes": "Длительность розыгрыша в минутах (0 — ручное подведение итогов)",
        "btn_limit_reached": "Лимит: в одном ряду Discord максимум 5 кнопок.",

        # Live Giveaway & Listener Dashboard
        "listener_active": "✓ PRISM Слушатель активен!",
        "listener_waiting": "Ожидание нажатий интерактивных кнопок в Discord...",
        "listener_cmd_roll": "Выбрать случайного победителя розыгрыша (Roll Winner) 🏆",
        "listener_cmd_list": "Показать список всех участников ({count}) 👥",
        "listener_cmd_stop": "Остановить слушатель и вернуться в меню",
        "listener_new_participant": "+ Новый участник розыгрыша:",
        "listener_verified": "✓ Роль выдана участнику:",
        "listener_winner_box_title": "РЕЗУЛЬТАТ РОЗЫГРЫША",
        "listener_winner_congrats": "🏆 ПОБЕДИТЕЛЬ РОЗЫГРЫША!",
        "listener_winner_user": "Пользователь:",
        "listener_winner_total": "Всего участников было:",
        "listener_post_channel_confirm": "Опубликовать поздравление в Discord канал? (y/n)",
        "listener_post_channel_done": "✓ Поздравление успешно отправлено в Discord канал!",

        # Discord Bot Messages (Sent to Discord)
        "bot_giveaway_already": "ℹ️ Вы уже участвуете в этом розыгрыше!\n👥 Всего участников: **{count}**",
        "bot_giveaway_success": "🎉 Вы успешно зарегистрированы в розыгрыше! Желаем удачи!",
        "bot_giveaway_part_num": "\n👥 Вы стали **#{count}** участником.",
        "bot_verify_already": "ℹ️ У вас уже есть роль **{role}**!",
        "bot_verify_forbidden": "⚠️ Ошибка: у бота недостаточно прав выдать роль **{role}**.\n(Переместите роль бота выше роли **{role}** в настройках сервера Discord).",
        "bot_verify_success": "✅ Верификация успешно пройдена! Доступ открыт.",
        "bot_verify_role_granted": "\n🎖️ Вам выдана роль: **{role}**",
        "bot_action_success": "✓ Действие успешно выполнено!",
        "bot_action_processed": "✓ Действие обработано!",
        "bot_giveaway_ended_title": "🎉 **РОЗЫГРЫШ ЗАВЕРШЁН!**\n🎁 Приз: **{prize}**\n👑 Победители: {mentions}\nПоздравляем с победой! Спасибо всем за участие!",
        "bot_giveaway_ended_empty": "⏳ **РОЗЫГРЫШ ЗАВЕРШЁН!**\nК сожалению, участников не набралось.",
        "bot_roll_winner_public": "🎉 **ПОЗДРАВЛЯЕМ ПОБЕДИТЕЛЯ РОЗЫГРЫША!**\n🏆 Победитель: <@{user_id}> (`@{username}`)!\nСпасибо всем за участие!",

        # Settings
        "settings_title": "=== Настройки PRISM ===",
        "settings_lang": "Язык интерфейса (Language)",
        "settings_theme": "Тема оформления (Color Theme)",
        "settings_current_lang": "Текущий язык:",
        "settings_current_theme": "Текущая тема:",
    },

    "en": {
        # App Info
        "app_title": "Discord Bot Management & Control Suite",
        "app_subtitle": "Bot Management • Autonomous Modules • Systems",
        
        # Main Menu
        "menu_title": "PRISM Control Center",
        "menu_send": "Send Message (Presets or Custom)",
        "menu_studio": "Modular Studio (Build Embed & Components)",
        "menu_engines": "Bot Studio & Engines (AutoMod, AI Assistant, Welcomer, Tickets)",
        "menu_fleet": "Sender Profiles (Manage Bots & Webhooks)",
        "menu_giveaways": "Interactive Listener & Giveaways (Live Dashboard)",
        "menu_messages": "Sent Messages (Edit / Delete by ID)",
        "menu_settings": "Settings (Language: RU/EN, Color Themes)",
        "menu_exit": "Exit PRISM",
        "prompt_action": "Select an option >",
        "press_enter": "Press Enter to return to menu...",
        "exit_farewell": "Thank you for using PRISM. Have a great day!",
        "op_cancelled": "Operation cancelled by user.",

        # Send Flow
        "send_flow_title": "Dispatch Message to Discord:",
        "send_opt_template": "Production Presets (Announcement, Status, Rules, Giveaway, Test)",
        "send_opt_scratch": "Build New Message from Scratch (Studio)",
        "send_opt_back": "Back to Menu",
        "send_prompt": "Choose an option >",
        "template_preview_title": "Preset Preview:",
        "template_what_to_do": "What would you like to do with this preset?",
        "template_action_send": "Dispatch to Discord right now",
        "template_action_edit": "Tweak text, components, or buttons (open in Studio)",
        "template_not_found": "Template not found.",
        "template_saved_success": "Template saved successfully:",

        # Modular Studio
        "studio_title": "=== Modular Embed Studio (Components & Parts) ===",
        "part_title": "Title",
        "part_desc": "Description/Text",
        "part_color": "Accent Color",
        "part_fields": "Fields",
        "part_buttons": "Buttons (Links & Scenarios)",
        "part_image": "Image/Banner",
        "part_author": "Author / Icon",
        "part_footer": "Footer Text",
        "action_dispatch": "Dispatch to Discord",
        "action_save_tpl": "Save as Reusable Template",
        "action_clear": "Clear All",
        "action_back": "Back to Main Menu",
        "prompt_detail": "Select component to edit >",
        "prompt_title": "Embed Title",
        "prompt_url": "Title URL (or leave empty)",
        "prompt_desc": "Description / Content",
        "prompt_img": "Large Image/Banner URL (or empty)",
        "prompt_thumb": "Thumbnail URL (top-right, or empty)",
        "prompt_author_name": "Author Name (or empty)",
        "prompt_author_icon": "Author Icon URL",
        "prompt_author_url": "Author Link URL",
        "prompt_footer_text": "Footer Text",
        "prompt_timestamp": "Include current timestamp?",
        "prompt_tpl_name": "Enter name for new template (e.g. my_event)",
        "reset_confirm": "Reset embed to clean blank slate?",

        # Sender Selection (Fleet)
        "sender_select_title": "Select Message Sender Profile:",
        "sender_via_bot": "Dispatch via Discord Bot (supports live buttons & roles)",
        "sender_via_webhook": "Dispatch via Webhook (instant, link buttons only)",
        "sender_choose_bot": "Select bot from saved profiles:",
        "sender_add_new_bot": "Add a new Discord Bot (token)",
        "sender_choose_webhook": "Select webhook from profiles:",
        "sender_add_new_webhook": "Enter custom Webhook URL manually",
        "sender_channel_id": "Enter Discord Text Channel ID",
        "sender_ping_content": "Content / Mention ping (e.g. @everyone or leave empty)",
        "sender_dispatch_now": "Send message to Discord right now?",
        "sender_success_bot": "✓ Message successfully dispatched by @{bot} to channel {channel}! (ID: {id})",
        "sender_success_webhook": "✓ Message successfully dispatched to Discord! (ID: {id})",

        # Buttons Menu
        "buttons_title": "=== Discord Buttons & ActionRow Setup ===",
        "buttons_empty": "No buttons attached yet. You can attach up to 5 link or scenario buttons.",
        "buttons_add": "Add button",
        "buttons_remove": "Remove button",
        "buttons_clear": "Clear all buttons",
        "buttons_save_back": "Save and return to Studio",
        "btn_type_link": "Link Button ↗",
        "btn_type_link_desc": "Opens website, Telegram, Discord invite. Works instantly with any webhook.",
        "btn_type_giveaway": "Scenario: Timed Giveaway 🎉",
        "btn_type_giveaway_desc": "'Enter' button, participant tracking, timer, and automated winner draw.",
        "btn_type_verify": "Scenario: Verification / Role Assignment ✅",
        "btn_type_verify_desc": "Rule confirmation button with REAL server role assignment.",
        "btn_type_custom": "Custom Scenario (Ephemeral Pop-up 💬)",
        "btn_type_custom_desc": "Custom button with private ephemeral response text.",
        "btn_prompt_label": "Button Label",
        "btn_prompt_url": "Target URL (where click navigates)",
        "btn_prompt_emoji": "Emoji prefix (or empty)",
        "btn_prompt_role": "Role ID to assign (or Enter for confirmation only)",
        "btn_prompt_response": "Ephemeral message shown to user on click",
        "btn_prompt_prize": "Prize name for giveaway (e.g. Discord Nitro Full)",
        "btn_prompt_minutes": "Giveaway duration in minutes (0 for manual draw)",
        "btn_limit_reached": "Limit reached: Discord allows up to 5 buttons in 1 row.",

        # Live Giveaway & Listener Dashboard
        "listener_active": "✓ PRISM Interactive Listener is Live!",
        "listener_waiting": "Waiting for Discord button interactions...",
        "listener_cmd_roll": "Roll random giveaway winner (Roll Winner) 🏆",
        "listener_cmd_list": "Display all registered participants ({count}) 👥",
        "listener_cmd_stop": "Stop listener and return to menu",
        "listener_new_participant": "+ New giveaway participant:",
        "listener_verified": "✓ Role assigned to user:",
        "listener_winner_box_title": "GIVEAWAY WINNER RESULTS",
        "listener_winner_congrats": "🏆 GIVEAWAY WINNER DRAWN!",
        "listener_winner_user": "User:",
        "listener_winner_total": "Total participants:",
        "listener_post_channel_confirm": "Post congratulation announcement to Discord channel? (y/n)",
        "listener_post_channel_done": "✓ Announcement successfully posted to Discord channel!",

        # Discord Bot Messages (Sent to Discord)
        "bot_giveaway_already": "ℹ️ You are already participating in this giveaway!\n👥 Total participants: **{count}**",
        "bot_giveaway_success": "🎉 You have successfully entered the giveaway! Best of luck!",
        "bot_giveaway_part_num": "\n👥 You are participant **#{count}**.",
        "bot_verify_already": "ℹ️ You already have the **{role}** role!",
        "bot_verify_forbidden": "⚠️ Error: The bot does not have sufficient permissions to assign **{role}**.\n(Move the bot's role higher than **{role}** in Discord Server Settings).",
        "bot_verify_success": "✅ Verification completed! Access granted.",
        "bot_verify_role_granted": "\n🎖️ You have been granted the role: **{role}**",
        "bot_action_success": "✓ Action completed successfully!",
        "bot_action_processed": "✓ Action processed!",
        "bot_giveaway_ended_title": "🎉 **GIVEAWAY ENDED!**\n🎁 Prize: **{prize}**\n👑 Winner(s): {mentions}\nCongratulations! Thank you all for participating!",
        "bot_giveaway_ended_empty": "⏳ **GIVEAWAY ENDED!**\nUnfortunately, no participants entered.",
        "bot_roll_winner_public": "🎉 **CONGRATULATIONS TO THE GIVEAWAY WINNER!**\n🏆 Winner: <@{user_id}> (`@{username}`)!\nThank you all for participating!",

        # Settings
        "settings_title": "=== PRISM Settings ===",
        "settings_lang": "Interface Language",
        "settings_theme": "UI Theme",
        "settings_current_lang": "Current Language:",
        "settings_current_theme": "Current Theme:",
    }
}


def detect_system_language() -> str:
    """Detects system language: returns 'ru' for Russian/CIS locales, 'en' otherwise."""
    try:
        loc = locale.getdefaultlocale()[0] or ""
        loc = loc.lower()
        if any(code in loc for code in ("ru", "rus", "be", "uk", "kk", "ky", "uz")):
            return "ru"
    except Exception:
        pass

    env_lang = (os.environ.get("LANG", "") + os.environ.get("LANGUAGE", "")).lower()
    if any(code in env_lang for code in ("ru", "rus", "be", "uk")):
        return "ru"

    return "en"


def get_language(preference: str = "auto") -> str:
    if preference in ("ru", "en"):
        return preference
    return detect_system_language()


def set_active_language(lang: str) -> None:
    global _CURRENT_LANGUAGE
    _CURRENT_LANGUAGE = lang


def t(key: str, lang: str = "", **kwargs: Any) -> str:
    """Translates a key into current language string with string formatting support."""
    chosen_lang = lang or _CURRENT_LANGUAGE
    if chosen_lang not in ("ru", "en"):
        chosen_lang = detect_system_language()

    dict_map = TRANSLATIONS.get(chosen_lang, TRANSLATIONS["en"])
    text = dict_map.get(key) or TRANSLATIONS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
