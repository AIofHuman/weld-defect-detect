import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

DEBUG = os.getenv('DEBUG', default='False') == 'True'

# bot = Bot(token=BOT_TOKEN)
# # Укажите id своего аккаунта в Telegram
# chat_id = CHAT_ID
# text = 'Вам телеграмма!'
# # Отправка сообщения
# bot.send_message(chat_id, text)

# def get_new_image():
#     try:
#         response = requests.get(URL)
#     except Exception as error:
#         print(error)
#         new_url = 'https://api.thedogapi.com/v1/images/search'
#         response = requests.get(new_url)


#     response = response.json()
#     random_cat = response[0].get('url')
#     return random_cat


def get_image_predict(photo_weld):
    # f = BytesIO(file.download_as_bytearray)
    # file_bytes = np.asarray(bytearray(f.read(), dtype=np.uint8))
    pass


def get_predict(update, context):
    chat = update.effective_chat
    try:
        photo_weld = context.bot.get_file(update.message.photo[-1].file_id)

        context.bot.send_photo(chat.id, get_image_predict(photo_weld))
    except Exception as error:
        context.bot.send_message(
            chat_id=chat.id,
            text=f'При детекции произошла ошибка, {error}!',
        )


def only_photo(update, context):
    chat = update.effective_chat
    name = update.message.chat.first_name

    context.bot.send_message(
        chat_id=chat.id,
        text=f'Ожидаю только фото сварного шва для детекции дефектов! Большего, я пока не могу, {name}!',
    )


def feedback(update, context):
    chat = update.effective_chat
    name = update.message.chat.first_name
    button = ReplyKeyboardMarkup([['/feedback']], resize_keyboard=True)

    context.bot.send_message(
        chat_id=chat.id,
        text=f'Спасибо! Учту твое мнение, {name}.',
        reply_markup=button,
    )


def wake_up(update, context):
    chat = update.effective_chat

    context.bot.send_message(
        chat_id=chat.id,
        text='Ожидаю фото сварочного шва',
    )


def main():
    updater = Updater(token=BOT_TOKEN)

    # updater.dispatcher.add_handler(MessageHandler(~Filters.photo, only_photo))
    updater.dispatcher.add_handler(MessageHandler(Filters.photo, get_predict))
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.dispatcher.add_handler(CommandHandler('feedback', feedback))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
