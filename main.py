import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import yadisk
import os
from config import TELEGRAM_TOKEN, YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_state = {}  # Хранилище состояний

def get_yandex_disk():
    return yadisk.YaDisk(YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать в бот для загрузки фото для ваших заказов с Озон.\n"
        "Пожалуйста, введите номер заказа:"
    )
    user_state[message.from_user.id] = {"step": "order_number"}

@dp.message(F.text & ~F.command())
async def process_order_number(message: types.Message):
    user_id = message.from_user.id
    if user_state.get(user_id, {}).get("step") != "order_number":
        return

    order_number = message.text.strip()
    user_state[user_id] = {
        "step": "upload_photos",
        "order_number": order_number,
        "photos": []
    }
    await message.answer(
        f"Загрузите фотографии (до 200 шт).\n"
        "После отправки всех фото напишите «ГОТОВО»."
    )

@dp.message(F.photo)
async def process_photo(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    if not state or state["step"] != "upload_photos":
        return

    if len(state["photos"]) >= 200:
        await message.answer("Достигнут лимит в 200 фото. Напишите «ГОТОВО».")
        return

    photo_id = message.photo[-1].file_id
    state["photos"].append(photo_id)
    await message.answer("Фото принято. Отправьте ещё или напишите «ГОТОВО».")

@dp.message(F.text.lower() == "готово")
async def finish_upload(message: types.Message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    if not state or state["step"] != "upload_photos":
        return

    order_number = state["order_number"]
    photos = state["photos"]

    if not photos:
        await message.answer("Вы не загрузили ни одного фото. Начните заново.")
        return

    y = get_yandex_disk()
    folder_path = f"/OzonOrders/{order_number}"

    try:
        y.mkdir(folder_path)
    except yadisk.exceptions.PathExistsError:
        pass

    for photo_id in photos:
        try:
            photo = await bot.get_file(photo_id)
            downloaded_file = await bot.download_file(photo.file_path)
            temp_path = f"/tmp/{photo_id}.jpg"
            with open(temp_path, "wb") as f:
                f.write(downloaded_file.read())
            y.upload(temp_path, f"{folder_path}/{photo_id}.jpg")
            os.remove(temp_path)
        except Exception as e:
            logger.error(f"Ошибка при загрузке фото {photo_id}: {e}")
            continue

    await message.answer("Ваши фото приняты.")
    user_state.pop(user_id, None)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
