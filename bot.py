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

        # # Проверяем, является ли пользователь администратором
        # if message.from_user.id in ADMIN_IDS:
        #     # Клавиатура для администраторов
        #     keyboard = types.ReplyKeyboardMarkup(
        #         keyboard=[
        #             [types.KeyboardButton(text="🖌 О художнике"), types.KeyboardButton(text="🎨 О направлении")],
        #             [types.KeyboardButton(text="🖼 Каталог картин"), types.KeyboardButton(text="📅 Мероприятия")],
        #             [types.KeyboardButton(text="👥 Наши гости"), types.KeyboardButton(text="🤝 Сотрудничество")],
        #             [types.KeyboardButton(text="📞 Контакты")],
        #             [types.KeyboardButton(text="⚙ Админ панель")]# Кнопка для админов
        #         ], resize_keyboard=True
        #     )
        # else:
        #     # Клавиатура для обычных пользователей
        #     keyboard = types.ReplyKeyboardMarkup(
        #         keyboard=[
        #             [types.KeyboardButton(text="🖌 О художнике"), types.KeyboardButton(text="🎨 О направлении")],
        #             [types.KeyboardButton(text="🖼 Каталог картин"), types.KeyboardButton(text="📅 Мероприятия")],
        #             [types.KeyboardButton(text="👥 Наши гости"), types.KeyboardButton(text="🤝 Сотрудничество")],
        #             [types.KeyboardButton(text="📞 Контакты")]
        #         ], resize_keyboard=True
        #     )

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
        await message.answer("🎨 Добро пожаловать в ONLINE GALLERY OF AIRO!", reply_markup=keyboard)

    from aiogram.types import FSInputFile
    from aiogram.utils.media_group import MediaGroupBuilder

    # Хендлер для кнопки "🖌 О художнике"
    @dp.message(lambda message: message.text == "🖌 О художнике")
    async def about_artist(message: types.Message):
        artist_info = """
        🎨 **Художник Сергей AIRO** 🎨

        Родился в 1960 году в Новороссийске. Детство и юность провел на Кубани, а сегодня Сергей живет и работает в Москве. 🌆  
        Является постоянным членом **«Союза художников»**, **«Ассоциации новых художников»** и **«Общества изобразительного искусства»**.  
        Награжден Зурабом Церетели почетным званием академика **«Международной Академии культуры и Искусства»**. 🏅

        Его картины были представлены на выставках в таких странах, как:
        - 🇨🇭 Швейцария
        - 🇦🇪 ОАЭ
        - 🇦🇹 Австрия
        - 🇩🇪 Германия
        - 🇪🇸 Испания
        - 🌍 Африка
        - 🇷🇺 Россия

        Член **Союза художников**. 🌟

        📸 Прикрепленные изображения дают возможность более детально познакомиться с его работами.
        """

        # Создание MediaGroupBuilder для добавления медиа
        media_group = MediaGroupBuilder(caption=artist_info)

        # Используем InputFile для добавления фото
        photo1 = FSInputFile("media/1.jpg")  # Передаем путь к файлу
        photo2 = FSInputFile("media/2.jpg")  # Передаем путь к файлу

        # Добавляем фотографии в MediaGroupBuilder
        media_group.add_photo(type="photo", media=photo1)
        media_group.add_photo(type="photo", media=photo2)

        # Отправляем медиа-группу
        await message.answer_media_group(media=media_group.build())

    @dp.message(lambda message: message.text == "🎨 О направлении")
    async def about_style(message: types.Message):
        # Длинный текст
        style_info = """
        🎨 **Художник и его стиль: "Ретрофутуризм" и "Русский космизм"**

        Художник называет стиль, в котором работает, **«ретрофутуризмом»** или **«русским космизмом»**. Это популярное и растущее направление среди художников и коллекционеров по всему миру. 🌍

        Он связывает **прошлое** с **будущим** в **настоящем времени**. Этот стиль — как мост между временами, отражающий глубину истории и её перспективы. 🕰️🚀

        🔹 **Техника исполнения**:
        - Художник использует разнообразные техники, чтобы создать своё **уникальное выражение**.
        - Внимание уделяется произведениям и образам **мифической жизни**, что придает работам мистическую атмосферу.

        🔸 **Исследования и влияние**:
        - В дальнейшем художник концентрируется на изучении **средневековых мастеров**.
        - В основном исследует **религиозное направление** и влияние **фламандских средневековых художников**.

        ✨ **Сюрреалистичные полотна** отличаются **особой техникой исполнения**. AIRO искусственно состаривает свои работы, делая их **"мудрыми"**. 
    
        🌿 **Другие виды искусства**:
        Помимо живописи, художник занимается **созданием инсталляций**, **предметов интерьера** и **цифровым искусством**.
        """

        await message.answer(style_info)

        # # Создаем MediaGroup для фотографий
        # media_group = MediaGroupBuilder()
        # media_group.add_photo(type="photo", media=FSInputFile("media/3.jpg"))
        # media_group.add_photo(type="photo", media=FSInputFile("media/4.jpg"))
        # media_group.add_photo(type="photo", media=FSInputFile("media/5.jpg"))
        #
        # # Отправляем медиа-группу с фотографиями
        # await message.answer_media_group(media=media_group.build())

    # Хендлер для кнопки "🖼 Каталог картин"
    @dp.message(lambda message: message.text == "🖼 Каталог картин")
    async def show_catalog(message: types.Message):
        section = "catalog"
        content = get_content(section)

        for id, media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "📅 Мероприятия"
    @dp.message(lambda message: message.text == "📅 Мероприятия")
    async def show_events(message: types.Message):
        section = "events"
        content = get_content(section)

        for id, media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "👥 Наши гости"
    @dp.message(lambda message: message.text == "👥 Наши гости")
    async def show_guests(message: types.Message):
        section = "guests"
        content = get_content(section)

        for id, media_type, media_url, description in content:
            if media_type == "photo":
                await message.answer_photo(media_url, caption=description)
            else:
                await message.answer_video(media_url, caption=description)

    # Хендлер для кнопки "🤝 Сотрудничество"
    @dp.message(lambda message: message.text == "🤝 Сотрудничество")
    async def cooperation_info(message: types.Message):
        cooperation_info = """
        ✨ **Рестораны и заведения:**

        - 🍽 **Ресторан «BLANC»** — изысканная атмосфера для ценителей высокой кухни.
        - 🍴 **Ресторан «RAZGAR»** — место, где восточная кухня встречается с современными тенденциями.
        - 🏙 **Клубное пространство «Смоленка7»** — стильный уголок для развлечений и встреч.

        🌊 **Эксклюзивные услуги:**

        - 🐟 **Премиальная океаническая доставка «BLUEFIN»** — свежие морепродукты, доставленные прямо к вашему столу.
        - 🦑 **Магазин черной икры и астраханской рыбы «ASTRAKHAN FISH»** — лучшие деликатесы для гурманов.

        🍵 **Чай и здоровье:**

        - 🍃 **Чайный дом «VAN TEA»** — атмосфера уюта и восхитительных вкусов чая.

        📺 **Медиа и пресс:**

        - 📡 **Телеканал «LISCHANNEL»** — всегда актуальные новости и интересные программы.
        - 📖 **Журнал «BABYER MAGAZINE»** — уникальные статьи и советы для современных родителей.

        🍩 **Здоровое питание и клиники:**

        - 🍓 **Бренд ПП десертов «CRYSTAL MOCHI»** — полезные и вкусные десерты для всех.
        - 🏥 **Сеть клиник «МЕДЦЕНТРСЕРВИС»** — забота о вашем здоровье и комфорте.

        🛡 **Социальные инициативы:**

        - 🌟 **АНО «ОБЕРЕГ»** — поддержка и защита тех, кто нуждается в помощи.
        """
        await message.answer(cooperation_info)

    # Хендлер для кнопки "📞 Контакты"
    @dp.message(lambda message: message.text == "📞 Контакты")
    async def contact_info(message: types.Message):
        contact_info = """
        Наши контактные данные:

        🖋 **Арт-директор:**
        - 👤 **АЛЁХИН НИКОЛАЙ ОЛЕГОВИЧ**
        - 📞 **Телефон:** +7 926 211-11-70
        """
        await message.answer(contact_info)

    # Хендлер для кнопки "⚙ Админ панель" (если это администратор)
    # @dp.message(lambda message: message.text == "⚙ Админ панель")
    # async def admin_panel(message: types.Message):
    #     if message.from_user.id in ADMIN_IDS:
    #         # Приветственное сообщение в админ панель
    #         await message.answer(
    #             "Добро пожаловать в админ панель! Вы можете добавить новый контент или управлять пользователями.")
    #
    #         # Здесь можно дополнительно добавить меню для админов
    #         keyboard = types.ReplyKeyboardMarkup(
    #             keyboard=[
    #                 [types.KeyboardButton(text="➕ Добавить фото"), types.KeyboardButton(text="➕ Добавить видео")]
    #             ],
    #             resize_keyboard=True
    #         )
    #
    #         # Отправка клавиатуры с опциями для администраторов
    #         await message.answer("Выберите, что хотите добавить:", reply_markup=keyboard)
    #     else:
    #         await message.answer("У вас нет доступа к админ панели.")

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
