import logging
import os
import shutil
from pathlib import Path

import torch
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

DEBUG = os.getenv('DEBUG', default='False') == 'True'


def get_image_predict(photo_weld):
    # clean temp dir
    shutil.rmtree('./tmp')

    # Model
    model = torch.hub.load(
        './yolov5/',
        'custom',
        source='local',
        path='/models/yolov5s.pt',
        force_reload=True,
    )
    # model = torch.hub.load("ultralytics/yolov5", "yolov5s")

    results = model(photo_weld, size=640)
    results.save(save_dir='./tmp')
    return f'./tmp/{results.files[0]}'


def get_predict(update, context, photo=True):
    chat = update.effective_chat
    try:
        if photo:
            photo_weld = context.bot.get_file(update.message.photo[-1].file_id)
        else:
            photo_weld = context.bot.get_file(update.message.document)

        inference_file = open(get_image_predict(photo_weld.file_path), 'rb')

        context.bot.send_photo(chat.id, inference_file, 'Мой вердикт')
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

    updater.dispatcher.add_handler(MessageHandler(Filters.photo, get_predict))
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.dispatcher.add_handler(CommandHandler('feedback', feedback))
    updater.dispatcher.add_handler(MessageHandler(~Filters.photo, only_photo))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
