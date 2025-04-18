# bot.py
import logging
import asyncio
import traceback

from aiogram import Bot, Dispatcher, types, F, exceptions
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo, CallbackQuery, Message
)
# Убираем импорт hbold
# from aiogram.utils.markdown import hbold

# Импорты конфига и баз данных
from config import BOT_TOKEN, ADMINS, DB_PATH
from database import (
    init_db, add_content, get_content, get_post_details, delete_content, delete_all_content,
    add_moderator, remove_moderator, is_moderator, get_moderators, CONTENT_SECTIONS
)
from database_users import (
    init_users_db, add_user as add_user_to_list, get_all_users, remove_user as remove_user_from_list
)
# Импорты сервисов
from service import backup_service
from utils import send_new_post

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        # logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Инициализация бота и диспетчера ---
# Убираем parse_mode по умолчанию
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Разделы ---
sections = {
    "about_artist": "🎨 О художнике", "about_style": "🤍 Life", "catalog": "🖼 Каталог картин",
    "icons": "☦️ Иконы", "events": "📅 Мероприятия", "guests": "👥 Наши гости",
    "cooperation": "🤝 Сотрудничество", "contacts": "📞 Контакты"
}
if not all(key in CONTENT_SECTIONS for key in sections.keys()):
    logger.critical("Mismatch between 'sections' dict and CONTENT_SECTIONS in database.py!")
SECTIONS_WITH_DESCRIPTION_TOGGLE = ["catalog", "icons"]

# --- Состояния FSM ---
class AdminStates(StatesGroup):
    add_content_choose_section = State()
    add_content_enter_title = State()
    add_content_enter_description = State()
    add_content_upload_media = State()
    delete_content_choose_section = State()
    delete_content_choose_post = State()
    clear_section_choose_section = State()
    clear_section_confirm = State()
    add_moderator_enter_id = State()
    remove_moderator_choose_id = State()
    remove_moderator_confirm = State()

# --- Хелперы ---
async def is_admin_or_moderator(user_id: int) -> tuple[bool, bool]:
    is_adm = user_id in ADMINS
    is_mod = await is_moderator(user_id) if not is_adm else False
    return is_adm, is_mod

# --- Отображение контента пользователю ---

async def send_post_item(message: types.Message, section: str, post_details: dict) -> Message | None:
    """
    Отправляет один пост пользователю. Возвращает объект отправленного сообщения (или первого из группы)
    для возможности ответа на него.
    """
    # (Логика проверки post_details и section без изменений)
    if not post_details: return None
    if not section or section not in sections:
        logger.error(f"Invalid section ('{section}') for post id {post_details.get('id')}")
        await message.answer("⚠️ Ошибка: Неверный раздел поста.")
        return None

    post_id = post_details["id"]
    title = post_details["title"]
    description = post_details["description"] or ""
    media = post_details["media"]

    use_description_toggle = section in SECTIONS_WITH_DESCRIPTION_TOGGLE
    keyboard = None
    text_to_send = "" # Текст для текстового сообщения или caption
    caption_for_group_first = "" # Caption для первого элемента группы
    button_message_text = "Меню поста:" # Текст для сообщения с кнопкой

    # Убираем hbold, используем простой текст
    title_formatted = f"📌 {title}" # Просто заголовок

    if use_description_toggle:
        # --- Логика для Скрытого Описания ---
        text_to_send = title_formatted
        caption_for_group_first = title_formatted
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ℹ️ ОПИСАНИЕ", callback_data=f"show_desc_{section}_{post_id}")]
        ])
        button_message_text = "Меню поста:"
    else:
        # --- Логика для Обычных Разделов ---
        text_to_send = f"{title_formatted}\n\n{description}" # Полный текст
        caption_for_group_first = text_to_send
        keyboard = None

    sent_message_object = None # Будем хранить объект первого сообщения

    try:
        # --- Отправка сообщения ---
        if not media:
            sent_message_object = await message.answer(text_to_send, reply_markup=keyboard)
        elif len(media) == 1:
            item = media[0]
            common_args = {"caption": text_to_send, "reply_markup": keyboard}
            if item['type'] == 'photo':
                 sent_message_object = await message.answer_photo(photo=item['file_id'], **common_args)
            elif item['type'] == 'video':
                 sent_message_object = await message.answer_video(video=item['file_id'], **common_args)
        else:
            # Медиагруппа
            media_group = []
            for i, item in enumerate(media):
                caption_to_add = caption_for_group_first if i == 0 else None
                # Убираем parse_mode
                common_params = {"media": item['file_id']}
                if caption_to_add: common_params["caption"] = caption_to_add
                if item['type'] == 'photo': media_group.append(InputMediaPhoto(**common_params))
                elif item['type'] == 'video': media_group.append(InputMediaVideo(**common_params))

            if media_group:
                sent_messages = await message.answer_media_group(media=media_group)
                if sent_messages: # Если группа успешно отправлена
                    sent_message_object = sent_messages[0] # Сохраняем первое сообщение группы
                    # Кнопка (если нужна) ВСЕГДА отдельным сообщением-ответом
                    if keyboard:
                        await message.answer(button_message_text, reply_markup=keyboard,
                                              reply_to_message_id=sent_messages[0].message_id,
                                              disable_notification=True)
            else:
                 sent_message_object = await message.answer(text_to_send, reply_markup=keyboard)

    # --- Обработка исключений ---
    except exceptions.TelegramForbiddenError:
         logger.warning(f"User {message.chat.id} blocked the bot.")
         await remove_user_from_list(message.chat.id)
    except exceptions.TelegramRetryAfter as e:
         logger.warning(f"Flood limit exceeded for chat {message.chat.id}. Sleeping for {e.retry_after}s.")
         await asyncio.sleep(e.retry_after)
         # Повторяем отправку этого же поста
         sent_message_object = await send_post_item(message, section, post_details)
    except exceptions.TelegramBadRequest as e:
         logger.error(f"Bad Request sending post {post_id} section {section} to chat {message.chat.id}: {e}")
         await message.answer("⚠️ Произошла ошибка при отображении поста. Возможно, файл был удален или поврежден.")
    except Exception as e:
         logger.error(f"Unexpected error sending post {post_id} section {section} to chat {message.chat.id}: {e}\n{traceback.format_exc()}")
         await message.answer("⚠️ Произошла внутренняя ошибка при отображении поста.")

    return sent_message_object # Возвращаем объект сообщения (или None если ошибка)

async def handle_section_button(message: types.Message):
    """Обрабатывает нажатие на кнопку раздела из главного меню."""
    section_key = None
    for key, value in sections.items():
        if message.text == value: section_key = key; break
    if not section_key: return await message.answer("Неизвестный раздел.")

    logger.info(f"User {message.from_user.id} requested section '{section_key}'")
    # Используем get_content, который теперь сортирует ASC (старые первыми)
    content_rows = await get_content(section_key)
    if not content_rows: return await message.answer(f"ℹ️ В разделе '{sections[section_key]}' пока нет контента.")

    posts_map = {}
    # Группируем по post_id, сохраняя порядок извлечения из БД
    post_ids_in_order = []
    for row in content_rows:
        post_id, title, description, media_type, file_id = row
        if post_id not in posts_map:
            posts_map[post_id] = {"id": post_id, "title": title, "description": description, "media": []}
            post_ids_in_order.append(post_id) # Сохраняем порядок ID
        if media_type and file_id:
             posts_map[post_id]["media"].append({"type": media_type, "file_id": file_id})

    first_sent_message = None # Для хранения первого сообщения
    sent_count = 0

    # Отправляем посты в порядке их получения из БД
    for post_id in post_ids_in_order:
        sent_msg = await send_post_item(message, section_key, posts_map[post_id])
        if sent_msg and first_sent_message is None:
            first_sent_message = sent_msg # Запоминаем первое успешно отправленное сообщение
        if sent_msg:
             sent_count += 1
        await asyncio.sleep(0.2) # Задержка

    logger.info(f"Sent {sent_count} posts from section '{section_key}' to user {message.from_user.id}")

    # --- Отправка сообщения "Перейти в начало" ---
    if first_sent_message:
        try:
            await message.answer(
                "⬆️ ПЕРЕЙТИ В НАЧАЛО ⬆️",
                reply_to_message_id=first_sent_message.message_id,
                disable_notification=True # Отправляем тихо
            )
        except Exception as e:
            logger.error(f"Failed to send 'Scroll to Top' message for section '{section_key}': {e}")
    # --- Конец отправки "Перейти в начало" ---

# --- Обработчики для кнопок Описание / Скрыть описание ---

@dp.callback_query(F.data.startswith("show_desc_"))
async def show_description_handler(callback: CallbackQuery):
    """Обрабатывает нажатие кнопки 'Описание'."""
    logger.info(f"Received callback: {callback.data}")
    if not callback.data: logger.error(f"Empty callback data (show_desc)"); return await callback.answer("Ошибка!", show_alert=True)

    try:
        parts = callback.data.split("_")
        logger.debug(f"Callback data parts (show_desc): {parts}")
        if len(parts) != 4 or parts[0] != "show" or parts[1] != "desc": raise ValueError("Invalid format")
        prefix1, prefix2, section, post_id_str = parts
        if not section or section not in sections: raise ValueError(f"Invalid section: '{section}'")
        post_id = int(post_id_str); assert post_id > 0
    except (ValueError, IndexError, TypeError, AssertionError) as e:
        logger.error(f"Invalid callback data format for show_desc: '{callback.data}'. Error: {e}")
        await callback.answer("Ошибка формата данных!", show_alert=True)
        try: await callback.message.edit_reply_markup(reply_markup=None)
        except: pass
        return

    logger.info(f"User {callback.from_user.id} requested description for post_id={post_id} in section='{section}'")
    post_details = await get_post_details(section, post_id)
    if not post_details:
        logger.warning(f"Post not found for show_desc: section='{section}', post_id={post_id}")
        await callback.answer("❗️ Пост не найден.", show_alert=True)
        try: await callback.message.edit_text(callback.message.text or "Пост удален.", reply_markup=None)
        except: pass
        return

    title = post_details["title"]
    description = post_details["description"] or "Нет описания."
    media = post_details["media"]

    # Формируем полный текст (без HTML) и кнопку "Скрыть"
    full_post_text = f"📌 {title}\n\n{description}"
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➖ Скрыть описание", callback_data=f"hide_desc_{section}_{post_id}")]
    ])

    try:
        # Редактируем сообщение, где была кнопка "Описание"
        if not media: await callback.message.edit_text(text=full_post_text, reply_markup=new_keyboard)
        elif len(media) == 1: await callback.message.edit_caption(caption=full_post_text, reply_markup=new_keyboard)
        else: await callback.message.edit_text(text=full_post_text, reply_markup=new_keyboard) # Редактируем сообщение с кнопкой
        await callback.answer()
    except exceptions.TelegramBadRequest as e:
        logger.error(f"Error editing message (show desc) mid={callback.message.message_id}: {e}")
        if "message is not modified" in str(e): await callback.answer()
        elif "message to edit not found" in str(e): await callback.answer("Сообщение не найдено.", show_alert=True)
        elif "message can't be edited" in str(e): await callback.answer("Не изменить.", show_alert=True)
        else: await callback.answer("❗️ Не обновить.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error editing message (show desc) mid={callback.message.message_id}: {e}\n{traceback.format_exc()}")
        await callback.answer("❗️ Ошибка.", show_alert=True)

@dp.callback_query(F.data.startswith("hide_desc_"))
async def hide_description_handler(callback: CallbackQuery):
    """Обрабатывает нажатие кнопки 'Скрыть описание'."""
    logger.info(f"Received callback: {callback.data}")
    if not callback.data: logger.error(f"Empty callback data (hide_desc)"); return await callback.answer("Ошибка!", show_alert=True)

    try:
        parts = callback.data.split("_")
        logger.debug(f"Callback data parts (hide_desc): {parts}")
        if len(parts) != 4 or parts[0] != "hide" or parts[1] != "desc": raise ValueError("Invalid format")
        prefix1, prefix2, section, post_id_str = parts
        if not section or section not in sections: raise ValueError(f"Invalid section: '{section}'")
        post_id = int(post_id_str); assert post_id > 0
    except (ValueError, IndexError, TypeError, AssertionError) as e:
        logger.error(f"Invalid callback data format for hide_desc: '{callback.data}'. Error: {e}")
        await callback.answer("Ошибка формата данных!", show_alert=True)
        try: await callback.message.edit_reply_markup(reply_markup=None)
        except: pass
        return

    logger.info(f"User {callback.from_user.id} requested to hide description for post_id={post_id} in section='{section}'")
    post_details = await get_post_details(section, post_id) # Нужны title и media
    if not post_details:
        logger.warning(f"Post not found for hide_desc: section='{section}', post_id={post_id}")
        await callback.answer("❗️ Пост не найден.", show_alert=True)
        try: await callback.message.edit_text(callback.message.text or "Пост удален.", reply_markup=None)
        except: pass
        return

    title = post_details["title"]
    media = post_details["media"]

    # Формируем кнопку "Описание"
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ ОПИСАНИЕ", callback_data=f"show_desc_{section}_{post_id}")]
    ])
    # Формируем текст для начального состояния (без HTML)
    short_text = f"📌 {title}"
    button_message_text = "Меню поста:"

    try:
        # Редактируем сообщение, где была кнопка "Скрыть описание"
        if not media: await callback.message.edit_text(text=short_text, reply_markup=new_keyboard)
        elif len(media) == 1: await callback.message.edit_caption(caption=short_text, reply_markup=new_keyboard)
        else: await callback.message.edit_text(text=button_message_text, reply_markup=new_keyboard) # Возвращаем к "Меню поста:"
        await callback.answer()
    except exceptions.TelegramBadRequest as e:
        logger.error(f"Error editing message (hide_desc) mid={callback.message.message_id}: {e}")
        if 'message is not modified' in str(e): await callback.answer()
        elif "message to edit not found" in str(e): await callback.answer("Сообщение не найдено.", show_alert=True)
        elif "message can't be edited" in str(e): await callback.answer("Не изменить.", show_alert=True)
        else: await callback.answer("❗️ Не обновить.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error editing message (hide_desc) mid={callback.message.message_id}: {e}\n{traceback.format_exc()}")
        await callback.answer("❗️ Ошибка.", show_alert=True)


# --- Админ-панель ---
async def get_admin_moderator_panel(user_id: int) -> tuple[str, InlineKeyboardMarkup] | tuple[str, None]:
    """Генерирует текст и клавиатуру админ/модератор панели (без HTML)."""
    is_adm, is_mod = await is_admin_or_moderator(user_id)
    if not is_adm and not is_mod: return "⛔ У вас нет доступа к панели управления.", None
    common_buttons = [
        [InlineKeyboardButton(text="➕ Добавить контент", callback_data="admin:add_content")],
        [InlineKeyboardButton(text="🗑 Удалить контент", callback_data="admin:del_content")],
    ]
    admin_only_buttons = [
        [InlineKeyboardButton(text="🔥 Очистить раздел", callback_data="admin:clear_section")],
        [InlineKeyboardButton(text="➕ Добавить модератора", callback_data="admin:add_moderator")],
        [InlineKeyboardButton(text="❌ Удалить модератора", callback_data="admin:remove_moderator")],
    ]
    if is_adm:
        text = "🔧 Админ-панель 🔧\nВыберите действие:" # Убрали Markdown
        keyboard = InlineKeyboardMarkup(inline_keyboard=common_buttons + admin_only_buttons)
    else:
        text = "🔹 Модераторская панель 🔹\nВыберите действие:" # Убрали Markdown
        keyboard = InlineKeyboardMarkup(inline_keyboard=common_buttons)
    return text, keyboard

@dp.message(Command("admin"), StateFilter(None))
async def admin_command(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    text, keyboard = await get_admin_moderator_panel(user_id)
    # Убираем parse_mode
    if keyboard: await message.answer(text, reply_markup=keyboard)
    else: await message.answer(text)

# -- Добавление контента --
@dp.callback_query(F.data == "admin:add_content", StateFilter(None))
async def admin_add_content_start(callback: CallbackQuery, state: FSMContext):
    is_adm, is_mod = await is_admin_or_moderator(callback.from_user.id)
    if not (is_adm or is_mod): return await callback.answer("⛔ Нет доступа.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"admin:add_select:{section}")] for section, name in sections.items()] + [[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin:back_to_panel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try: await callback.message.edit_text("📝 Выберите раздел для добавления контента:", reply_markup=keyboard)
    except: await callback.message.delete(); await callback.message.answer("📝 Выберите раздел:", reply_markup=keyboard)
    await state.set_state(AdminStates.add_content_choose_section); await callback.answer()
@dp.callback_query(F.data.startswith("admin:add_select:"), AdminStates.add_content_choose_section)
async def admin_add_content_section_selected(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":")[-1]
    if section not in sections: return await callback.answer("⚠️ Неверный раздел.", show_alert=True)
    await state.update_data(current_section=section, media_buffer=[])
    # Используем обычный текст
    await callback.message.edit_text(f"📝 Раздел '{sections[section]}'. Введите название поста:")
    await state.set_state(AdminStates.add_content_enter_title); await callback.answer()
@dp.message(AdminStates.add_content_enter_title)
async def admin_add_content_title_entered(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2: return await message.reply("⚠️ Слишком короткое название.")
    await state.update_data(current_title=message.text.strip())
    # Используем обычный текст
    await message.answer("📝 Отлично. Теперь введите описание поста:")
    await state.set_state(AdminStates.add_content_enter_description)
@dp.message(AdminStates.add_content_enter_description)
async def admin_add_content_description_entered(message: Message, state: FSMContext):
    # Сохраняем обычный текст
    await state.update_data(current_description=message.text or "")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить добавление медиа", callback_data="admin:add_finish_media")],
        [InlineKeyboardButton(text="⏭️ Пропустить медиа / Без медиа", callback_data="admin:add_skip_media")]])
    # Используем обычный текст
    await message.answer(
        "🖼️ Теперь отправьте фото или видео.\n"
        "Когда все файлы будут отправлены, нажмите кнопку 'Завершить'.\n"
        "Или нажмите 'Пропустить медиа', если пост только текстовый.",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.add_content_upload_media)
# Обработчики admin_add_content_media_uploaded, admin_add_content_skip_media, admin_add_content_finish_media
# остаются без изменений в логике, но без HTML
@dp.message(F.photo | F.video, AdminStates.add_content_upload_media)
async def admin_add_content_media_uploaded(message: Message, state: FSMContext):
    media_type, file_id = ("", "")
    if message.photo: media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video: media_type, file_id = "video", message.video.file_id
    if not (media_type and file_id): return await message.reply("⚠️ Не удалось распознать.")
    data = await state.get_data(); media_buffer = data.get("media_buffer", [])
    if any(m['file_id'] == file_id for m in media_buffer): return await message.reply("⚠️ Уже добавлен.")
    media_buffer.append({"type": media_type, "file_id": file_id}); await state.update_data(media_buffer=media_buffer)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ Завершить ({len(media_buffer)} медиа)", callback_data="admin:add_finish_media")]])
    await message.reply(f"✅ {media_type.capitalize()} добавлен. Еще или 'Завершить'.", reply_markup=keyboard)
@dp.callback_query(F.data == "admin:add_skip_media", AdminStates.add_content_upload_media)
async def admin_add_content_skip_media(callback: CallbackQuery, state: FSMContext):
    await state.update_data(media_buffer=[])
    await admin_add_content_finish_media(callback, state, from_skip=True)
@dp.callback_query(F.data == "admin:add_finish_media", AdminStates.add_content_upload_media)
async def admin_add_content_finish_media(callback: CallbackQuery, state: FSMContext, from_skip: bool = False):
    data = await state.get_data()
    section, title, description, media_files = data.get("current_section"), data.get("current_title"), data.get("current_description"), data.get("media_buffer", [])
    if not all([section, title is not None, description is not None]):
        logger.error(f"Incomplete data for adding content: {data}")
        await callback.answer("⚠️ Ошибка сбора данных.", show_alert=True); await state.clear()
        text, kb = await get_admin_moderator_panel(callback.from_user.id)
        try: # Пытаемся отредактировать или отправить новое
            if kb: await callback.message.edit_text(text, reply_markup=kb)
            else: await callback.message.edit_text(text)
        except:
            if kb: await callback.message.answer(text, reply_markup=kb)
            else: await callback.message.answer(text)
        return
    content_id = await add_content(section, title, description, media_files)
    final_message = ""
    if content_id:
        final_message = f"✅ Пост добавлен в '{sections[section]}' (ID: {content_id})."
        logger.info(f"Admin/Mod {callback.from_user.id} added content to '{section}', id={content_id}")
        users_to_notify = await get_all_users()
        if users_to_notify: asyncio.create_task(send_new_post(bot, section, content_id, users_to_notify)); final_message += f"\n🚀 Рассылка для {len(users_to_notify)}."
        else: final_message += "\nℹ️ Нет пользователей для рассылки."
    else: final_message = "❌ Ошибка сохранения."; logger.error(f"Failed add content by {callback.from_user.id}. Data: {data}")
    try: await callback.message.edit_text(final_message, reply_markup=None)
    except: await callback.message.delete(); await callback.message.answer(final_message)
    await callback.answer("Готово!"); await state.clear()

# -- Удаление контента --
# (Обработчики del_content и clear_section остаются без изменений в логике, но используют обычный текст)
@dp.callback_query(F.data == "admin:del_content", StateFilter(None))
async def admin_delete_content_start(callback: CallbackQuery, state: FSMContext):
    is_adm, is_mod = await is_admin_or_moderator(callback.from_user.id)
    if not (is_adm or is_mod): return await callback.answer("⛔ Нет доступа.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"admin:del_select:{section}")] for section, name in sections.items()] + [[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin:back_to_panel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try: await callback.message.edit_text("🗑 Выберите раздел для удаления:", reply_markup=keyboard)
    except: await callback.message.delete(); await callback.message.answer("🗑 Выберите раздел:", reply_markup=keyboard)
    await state.set_state(AdminStates.delete_content_choose_section); await callback.answer()
@dp.callback_query(F.data.startswith("admin:del_select:"), AdminStates.delete_content_choose_section)
async def admin_delete_content_section_selected(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":")[-1]
    if section not in sections: return await callback.answer("⚠️ Неверный раздел.", show_alert=True)
    await state.update_data(current_section=section); content_rows = await get_content(section)
    if not content_rows: await callback.message.edit_text(f"ℹ️ В '{sections[section]}' нет контента."); await callback.answer(); await state.clear(); return
    posts = {}; buttons = []
    for row in content_rows: post_id, title, _, _, _ = row; posts.setdefault(post_id, title or f"Пост #{post_id}")
    # Используем сортировку из get_content (ASC)
    for post_id in posts.keys(): title = posts[post_id]; button_text = f"{post_id}: {title[:40]}{'...' if len(title) > 40 else ''}"; buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"admin:del_post:{post_id}")])
    if not buttons: await callback.message.edit_text("⚠️ Не удалось список."); await state.clear(); return
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back_to_panel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(f"🗑 Выберите пост для удаления из '{sections[section]}':", reply_markup=keyboard)
    await state.set_state(AdminStates.delete_content_choose_post); await callback.answer()
@dp.callback_query(F.data.startswith("admin:del_post:"), AdminStates.delete_content_choose_post)
async def admin_delete_content_post_selected(callback: CallbackQuery, state: FSMContext):
    try: post_id = int(callback.data.split(":")[-1])
    except: logger.error(f"Invalid callback data: {callback.data}"); await callback.answer("⚠️ Ошибка данных.", show_alert=True); return
    data = await state.get_data(); section = data.get("current_section")
    if not section: logger.error("Section not in state."); await callback.answer("⚠️ Ошибка состояния.", show_alert=True); await state.clear(); return
    success = await delete_content(section, post_id); final_text = ""
    if success: final_text = f"✅ Пост ID {post_id} удалён из '{sections[section]}'."; await callback.answer("Удалено!"); logger.info(f"User {callback.from_user.id} deleted content id={post_id} from '{section}'")
    else: final_text = f"❌ Не удалось удалить ID {post_id}."; await callback.answer("Ошибка!", show_alert=True)
    await state.clear(); panel_text, panel_kb = await get_admin_moderator_panel(callback.from_user.id); final_text += "\n\n" + panel_text
    try:
        if panel_kb: await callback.message.edit_text(final_text, reply_markup=panel_kb)
        else: await callback.message.edit_text(final_text)
    except:
         if panel_kb: await callback.message.answer(final_text, reply_markup=panel_kb)
         else: await callback.message.answer(final_text)

# Очистка раздела
@dp.callback_query(F.data == "admin:clear_section", StateFilter(None))
async def admin_clear_section_start(callback: CallbackQuery, state: FSMContext):
    is_adm, _ = await is_admin_or_moderator(callback.from_user.id)
    if not is_adm: return await callback.answer("⛔ Только админ.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"admin:clear_select:{section}")] for section, name in sections.items()] + [[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin:back_to_panel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try: await callback.message.edit_text("🔥 Выберите раздел для очистки:", reply_markup=keyboard)
    except: await callback.message.delete(); await callback.message.answer("🔥 Выберите раздел для очистки:", reply_markup=keyboard)
    await state.set_state(AdminStates.clear_section_choose_section); await callback.answer()
@dp.callback_query(F.data.startswith("admin:clear_select:"), AdminStates.clear_section_choose_section)
async def admin_clear_section_selected(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":")[-1]
    if section not in sections: return await callback.answer("⚠️ Неверный раздел.", show_alert=True)
    await state.update_data(section_to_clear=section)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 Да, очистить!", callback_data="admin:clear_confirm:yes"), InlineKeyboardButton(text="🟢 Нет, отмена", callback_data="admin:clear_confirm:no")]])
    await callback.message.edit_text(f"❓ Уверены, что хотите удалить ВЕСЬ контент из '{sections[section]}'? Необратимо!", reply_markup=keyboard)
    await state.set_state(AdminStates.clear_section_confirm); await callback.answer()
@dp.callback_query(F.data.startswith("admin:clear_confirm:"), AdminStates.clear_section_confirm)
async def admin_clear_section_confirmed(callback: CallbackQuery, state: FSMContext):
    confirm = callback.data.split(":")[-1]; data = await state.get_data(); section = data.get("section_to_clear"); final_text = ""
    if confirm == "yes":
        if section:
            success = await delete_all_content(section)
            if success: final_text = f"✅ Раздел '{sections[section]}' очищен."; await callback.answer("Очищено!"); logger.info(f"Admin {callback.from_user.id} cleared section '{section}'")
            else: final_text = f"❌ Ошибка очистки '{sections[section]}'."; await callback.answer("Ошибка!", show_alert=True)
        else: logger.error("Section clear error: no section in state."); final_text = "⚠️ Ошибка состояния."; await callback.answer("Ошибка!", show_alert=True)
    else: final_text = "🟢 Очистка отменена."; await callback.answer("Отменено")
    await state.clear(); panel_text, panel_kb = await get_admin_moderator_panel(callback.from_user.id); final_text += "\n\n" + panel_text
    try:
        if panel_kb: await callback.message.edit_text(final_text, reply_markup=panel_kb)
        else: await callback.message.edit_text(final_text)
    except:
         if panel_kb: await callback.message.answer(final_text, reply_markup=panel_kb)
         else: await callback.message.answer(final_text)

# Управление модераторами
@dp.callback_query(F.data == "admin:add_moderator", StateFilter(None))
async def admin_add_moderator_start(callback: CallbackQuery, state: FSMContext):
    is_adm, _ = await is_admin_or_moderator(callback.from_user.id)
    if not is_adm: return await callback.answer("⛔ Только админ.", show_alert=True)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin:back_to_panel")]])
    try: await callback.message.edit_text("👤 Введите ID пользователя (число):", reply_markup=keyboard)
    except: await callback.message.delete(); await callback.message.answer("👤 Введите ID пользователя (число):", reply_markup=keyboard)
    await state.set_state(AdminStates.add_moderator_enter_id); await callback.answer()
@dp.message(AdminStates.add_moderator_enter_id)
async def admin_add_moderator_id_entered(message: Message, state: FSMContext):
    try: user_id = int(message.text); assert user_id > 0
    except: await message.reply("⚠️ Некорректный ID. Введите число > 0 или 'Отмена'."); return
    is_target_admin = user_id in ADMINS; is_target_moderator = await is_moderator(user_id); result_text = ""
    if is_target_admin: result_text = f"ℹ️ Пользователь {user_id} админ."
    elif is_target_moderator: result_text = f"ℹ️ Пользователь {user_id} уже модератор."
    else: await add_moderator(user_id); result_text = f"✅ {user_id} назначен модератором."; logger.info(f"Admin {message.from_user.id} added moderator {user_id}")
    await state.clear(); panel_text, panel_kb = await get_admin_moderator_panel(message.from_user.id); final_text = result_text + "\n\n" + panel_text
    if panel_kb: await message.answer(final_text, reply_markup=panel_kb)
    else: await message.answer(final_text)
@dp.callback_query(F.data == "admin:remove_moderator", StateFilter(None))
async def admin_remove_moderator_start(callback: CallbackQuery, state: FSMContext):
    is_adm, _ = await is_admin_or_moderator(callback.from_user.id)
    if not is_adm: return await callback.answer("⛔ Только админ.", show_alert=True)
    moderators = await get_moderators()
    if not moderators: await callback.answer("ℹ️ Модераторов нет.", show_alert=True); return
    buttons = [[InlineKeyboardButton(text=f"❌ Удалить {mod_id}", callback_data=f"admin:rem_select:{mod_id}")] for mod_id in moderators] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back_to_panel")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try: await callback.message.edit_text("🚫 Выберите модератора:", reply_markup=keyboard)
    except: await callback.message.delete(); await callback.message.answer("🚫 Выберите модератора:", reply_markup=keyboard)
    await state.set_state(AdminStates.remove_moderator_choose_id); await callback.answer()
# Кнопка Назад
@dp.callback_query(F.data == "admin:back_to_panel", StateFilter('*'))
async def admin_back_to_panel(callback: CallbackQuery, state: FSMContext):
     await state.clear(); text, keyboard = await get_admin_moderator_panel(callback.from_user.id)
     try:
         if keyboard: await callback.message.edit_text(text, reply_markup=keyboard)
         else: await callback.message.edit_text(text)
     except:
          try: await callback.message.delete()
          except: pass
          if keyboard: await callback.message.answer(text, reply_markup=keyboard)
          else: await callback.message.answer(text)
     await callback.answer("Отмена")
@dp.callback_query(F.data.startswith("admin:rem_select:"), AdminStates.remove_moderator_choose_id)
async def admin_remove_moderator_selected(callback: CallbackQuery, state: FSMContext):
    try: mod_id_to_remove = int(callback.data.split(":")[-1])
    except: logger.error(f"Invalid callback data: {callback.data}"); await callback.answer("⚠️ Ошибка данных.", show_alert=True); return
    await state.update_data(moderator_to_remove=mod_id_to_remove)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, удалить", callback_data="admin:rem_confirm:yes"), InlineKeyboardButton(text="❌ Нет, оставить", callback_data="admin:rem_confirm:no")]])
    await callback.message.edit_text(f"❓ Удалить модератора {mod_id_to_remove}?", reply_markup=keyboard)
    await state.set_state(AdminStates.remove_moderator_confirm); await callback.answer()
@dp.callback_query(F.data.startswith("admin:rem_confirm:"), AdminStates.remove_moderator_confirm)
async def admin_remove_moderator_confirmed(callback: CallbackQuery, state: FSMContext):
    confirm = callback.data.split(":")[-1]; data = await state.get_data(); mod_id = data.get("moderator_to_remove"); final_text = ""
    if confirm == "yes":
        if mod_id: await remove_moderator(mod_id); final_text = f"✅ Модератор {mod_id} удалён."; logger.info(f"Admin {callback.from_user.id} removed moderator {mod_id}"); await callback.answer("Удалён!")
        else: logger.error("Mod ID not in state."); final_text = "⚠️ Ошибка состояния."; await callback.answer("Ошибка!", show_alert=True)
    else: mod_id_text = f" {mod_id}" if mod_id else ""; final_text = f"🟢 Удаление{mod_id_text} отменено."; await callback.answer("Отменено")
    await state.clear(); panel_text, panel_kb = await get_admin_moderator_panel(callback.from_user.id); final_text += "\n\n" + panel_text
    try:
        if panel_kb: await callback.message.edit_text(final_text, reply_markup=panel_kb)
        else: await callback.message.edit_text(final_text)
    except:
         try: await callback.message.delete()
         except: pass
         if panel_kb: await callback.message.answer(final_text, reply_markup=panel_kb)
         else: await callback.message.answer(final_text)


# --- Обработчик команды /start ---
@dp.message(Command("start"), StateFilter(None))
async def start_command(message: types.Message):
    user_id = message.from_user.id; username = message.from_user.username or "N/A"; first_name = message.from_user.first_name or ""; last_name = message.from_user.last_name or ""
    logger.info(f"User started bot: ID={user_id}, Username={username}, Name='{first_name} {last_name}'")
    await add_user_to_list(user_id) # Добавляем в отдельную БД
    buttons = []; row = []
    for section_name in sections.values():
        row.append(KeyboardButton(text=section_name));
        if len(row) == 2: buttons.append(row); row = []
    if row: buttons.append(row)
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("🎨 Добро пожаловать в ONLINE GALLERY OF AIRO!", reply_markup=keyboard)

# --- Регистрация обработчиков для кнопок разделов ---
def register_section_handlers():
    for section_text in sections.values():
        dp.message.register(handle_section_button, F.text == section_text, StateFilter(None))
    logger.info("Section button handlers registered.")

# --- Главная функция запуска ---
async def main():
    logger.info("Initializing databases...")
    await init_db(); await init_users_db()
    logger.info("Databases initialized.")
    register_section_handlers()
    asyncio.create_task(backup_service(bot))
    logger.info("Backup service task created.")
    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e: logger.critical(f"Polling failed: {e}\n{traceback.format_exc()}")
    finally:
        logger.warning("Stopping bot...")
        if bot.session: await bot.session.close()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
