import logging
import asyncio
from aiogram.types import InputMediaPhoto, InputMediaVideo
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramAPIError, TelegramForbiddenError


async def send_new_post(bot, section: str, content_id: int, users: list[int]):
    """
    Отправляет только что добавленный пост с медиафайлами.

    :param bot: Экземпляр бота.
    :param section: Раздел, в котором добавлен контент.
    :param content_id: ID добавленного поста.
    :param users: Список ID пользователей для рассылки.
    """
    from database import get_content

    # Получаем контент по ID
    content = await get_content(section, content_id)

    if not content:
        logging.error(f"Контент с ID {content_id} не найден в разделе {section}.")
        return

    # Группируем данные по постам
    posts = {}
    for row in content:
        post_id = row[0]
        if post_id not in posts:
            posts[post_id] = {
                "title": row[1],
                "description": row[2],
                "photos": [],
                "videos": []
            }
        if row[3] == "photo":
            posts[post_id]["photos"].append(row[4])
        elif row[3] == "video":
            posts[post_id]["videos"].append(row[4])

    # Отправляем пост каждому пользователю
    for user_id in users:
        for post in posts.values():
            text = f"📌 <b>{post['title']}</b>\n\n{post['description']}"

            # Создаем медиагруппу
            media_group = []

            # Добавляем первое фото с текстом
            if post["photos"]:
                media_group.append(
                    InputMediaPhoto(
                        media=post["photos"][0],
                        caption=text,
                        parse_mode="HTML"
                    )
                )
                # Добавляем остальные фото
                for file_id in post["photos"][1:]:
                    media_group.append(InputMediaPhoto(media=file_id))

            # Добавляем видео
            for video_id in post["videos"]:
                media_group.append(InputMediaVideo(media=video_id))

            try:
                # Отправляем медиагруппу
                if media_group:
                    await bot.send_media_group(chat_id=user_id, media=media_group)
                else:
                    # Если нет медиафайлов, отправляем только текст
                    await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")

            except TelegramForbiddenError:
                logging.warning(f"Пользователь {user_id} заблокировал бота или удалил чат. Пропускаем.")
                continue  # Переход к следующему пользователю

            except TelegramRetryAfter as e:
                logging.warning(f"Превышен лимит запросов! Ожидание {e.retry_after} секунд...")
                await asyncio.sleep(e.retry_after)  # Ждём указанное время и повторяем

            except (TelegramBadRequest, TelegramAPIError) as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                continue  # Пропускаем пользователя и идём дальше
