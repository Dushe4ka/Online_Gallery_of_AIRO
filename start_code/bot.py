import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN
from database import init_db, add_user, get_content
from admin import router as admin_router  # Импортируем только роутер, не бота

# Список ID администраторов (можно заменить на чтение из базы данных)
from config import ADMINS as ADMIN_IDS

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрация обработчиков
def register_handlers():
    # Регистрируем обработчики админского роутера
    dp.include_router(admin_router)

    # Регистрация хендлеров для команды /start
    @dp.message(Command("start"))
    async def start_command(message: types.Message):
        add_user(message.from_user.id)

        # Проверяем, является ли пользователь администратором
        if message.from_user.id in ADMIN_IDS:
            # Клавиатура для администраторов
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🖌 О художнике"), types.KeyboardButton(text="🎨 О направлении")],
                    [types.KeyboardButton(text="🖼 Каталог картин"), types.KeyboardButton(text="📅 Мероприятия")],
                    [types.KeyboardButton(text="👥 Наши гости"), types.KeyboardButton(text="🤝 Сотрудничество")],
                    [types.KeyboardButton(text="📞 Контакты")],
                    [types.KeyboardButton(text="⚙ Админ панель")]# Кнопка для админов
                ], resize_keyboard=True
            )
        else:
            # Клавиатура для обычных пользователей
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🖌 О художнике"), types.KeyboardButton(text="🎨 О направлении")],
                    [types.KeyboardButton(text="🖼 Каталог картин"), types.KeyboardButton(text="📅 Мероприятия")],
                    [types.KeyboardButton(text="👥 Наши гости"), types.KeyboardButton(text="🤝 Сотрудничество")],
                    [types.KeyboardButton(text="📞 Контакты")]
                ], resize_keyboard=True
            )

        # Отправляем сообщение с соответствующей клавиатурой
        await message.answer("🎨 Добро пожаловать в Online Gallery of Aigo!", reply_markup=keyboard)

    # Хендлер для кнопки "🖌 О художнике"
    @dp.message(lambda message: message.text == "🖌 О художнике")
    async def about_artist(message: types.Message):
        # Здесь можно добавить информацию о художнике
        artist_info = "Это художник с уникальным стилем, который вдохновляет многих людей."
        await message.answer(artist_info)

    # Хендлер для кнопки "🎨 О направлении"
    @dp.message(lambda message: message.text == "🎨 О направлении")
    async def about_style(message: types.Message):
        # Здесь можно добавить информацию о художественном стиле
        style_info = "Это направление в искусстве, которое фокусируется на..."
        await message.answer(style_info)

    # Хендлер для кнопки "🖼 Каталог картин"
    @dp.message(lambda message: message.text == "🖼 Каталог картин")
    async def show_catalog(message: types.Message):
        section = "catalog"
        content = get_content(section)

        for media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "📅 Мероприятия"
    @dp.message(lambda message: message.text == "📅 Мероприятия")
    async def show_events(message: types.Message):
        section = "events"
        content = get_content(section)

        for media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "👥 Наши гости"
    @dp.message(lambda message: message.text == "👥 Наши гости")
    async def show_guests(message: types.Message):
        section = "guests"
        content = get_content(section)

        for media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "🤝 Сотрудничество"
    @dp.message(lambda message: message.text == "🤝 Сотрудничество")
    async def cooperation_info(message: types.Message):
        cooperation_info = "Для сотрудничества с нами, пожалуйста, свяжитесь по указанным контактам."
        await message.answer(cooperation_info)

    # Хендлер для кнопки "📞 Контакты"
    @dp.message(lambda message: message.text == "📞 Контакты")
    async def contact_info(message: types.Message):
        contact_info = "Наши контактные данные:\nТелефон: +123456789\nEmail: contact@aigo.com"
        await message.answer(contact_info)

    # Хендлер для кнопки "⚙ Админ панель" (если это администратор)
    # Хендлер для кнопки "⚙ Админ панель" (если это администратор)
    @dp.message(lambda message: message.text == "⚙ Админ панель")
    async def admin_panel(message: types.Message):
        if message.from_user.id in ADMIN_IDS:
            # Приветственное сообщение в админ панель
            await message.answer(
                "Добро пожаловать в админ панель! Вы можете добавить новый контент или управлять пользователями.")

            # Здесь можно дополнительно добавить меню для админов
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="➕ Добавить фото"), types.KeyboardButton(text="➕ Добавить видео")]
                ],
                resize_keyboard=True
            )

            # Отправка клавиатуры с опциями для администраторов
            await message.answer("Выберите, что хотите добавить:", reply_markup=keyboard)
        else:
            await message.answer("У вас нет доступа к админ панели.")

# Основная асинхронная функция для запуска бота
async def main():
    # Инициализация базы данных
    init_db()

    # Регистрация обработчиков
    register_handlers()

    # Запуск бота
    await dp.start_polling(bot)

# Запуск приложения
if __name__ == "__main__":
    asyncio.run(main())
