import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
TEMP_DIR = './tmp/'
MODEL_NAME = 'yolov8_n_200epoch.pt'


def delete_files_in_directory(directory_path):
    try:
        files = os.listdir(directory_path)
        for file in files:
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print('All temp files deleted successfully.')
    except OSError:
        print('Error occurred while deleting temp files.')


def get_image_predict(photo_weld):
    # clean temp dir
    delete_files_in_directory(TEMP_DIR)

    model = YOLO(MODEL_NAME)

    results = model(photo_weld)

    tmp_file_name = (
        os.path.basename(tempfile.TemporaryFile(dir=TEMP_DIR).name) + '.jpg'
    )
    tmp_file = os.path.join(TEMP_DIR, tmp_file_name)
    results[0].save(filename=tmp_file)
    return tmp_file


def get_predict(update, context, photo=True):
    chat = update.effective_chat
    try:
        if photo:
            photo_weld = context.bot.get_file(update.message.photo[-1].file_id)
        else:
            photo_weld = context.bot.get_file(update.message.document)

        inference_file = open(get_image_predict(photo_weld.file_path), 'rb')
        button = ReplyKeyboardMarkup([['Не согласны?']], resize_keyboard=True)
        context.bot.send_photo(
            chat.id, inference_file, 'Мой вердикт', reply_markup=button
        )
        inference_file.close()
    except Exception as error:
        context.bot.send_message(
            chat_id=chat.id,
            text=f'При детекции произошла ошибка, {error}!',
        )


def only_photo(update, context):
    if update.message.text != None and len(update.message.text) > 0:
        chat = update.effective_chat
        name = update.message.chat.first_name

        context.bot.send_message(
            chat_id=chat.id,
            text=f'Ожидаю только фото сварного шва для детекции дефектов! Большего, я пока не могу, {name}!',
        )
    elif update.message.document != None:
        get_predict(update, context, photo=False)


def feedback(update, context):
    chat = update.effective_chat
    name = update.message.chat.first_name

    context.bot.send_message(
        chat_id=chat.id,
        text=f'Спасибо! Учту твое мнение, {name}.',
    )


def wake_up(update, context):
    chat = update.effective_chat

    context.bot.send_message(
        chat_id=chat.id,
        text='Ожидаю фото сварочного шва',
    )


def main():
    updater = Updater(token=BOT_TOKEN)

    updater.dispatcher.add_handler(MessageHandler(Filters.photo, get_predict))
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.dispatcher.add_handler(CommandHandler('feedback', feedback))
    updater.dispatcher.add_handler(MessageHandler(~Filters.photo, only_photo))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
