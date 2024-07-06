import logging
import logging.handlers
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv('BOT_TOKEN')
TEMP_DIR = 'tmp'
MODEL_NAME = './yolov8m_200epoch_rus_cls_name.pt'
USERS = pd.DataFrame(
    columns=['start_period', 'count_photos', 'tmp_dir']
)
PERIOD_LIMIT_MINUTES = 10
COUNT_PHOTOS_LIMIT = 3


def setup_logger(logger, file_name):
    logging.basicConfig(
        format='%(levelname)s:%(message)s',
        level=logging.INFO,
    )
    handler = logging.handlers.RotatingFileHandler(
        filename=file_name,
        encoding='utf-8',
        maxBytes=1024 * 1024 * 10,
        backupCount=5,
    )
    logger.addHandler(handler)

def delete_temp_dir(directory_path):
    try:
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                os.remove(file_path)
        for root, dirs, files in os.walk(directory_path):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                os.rmdir(dir_path)

        print("Temp directory deleted successfully.")
    except OSError:
        print("Error occurred while deleting temp directory.")

def delete_files_in_directory(directory_path):
    try:
        files = os.listdir(directory_path)
        for file in files:
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        print('All temp files deleted successfully.')
    except OSError as error:
        logger.error(
            f'Raise error on temp files delete: {error}'
        )
        print('Error occurred while deleting temp files.')


def get_image_predict(photo_weld, tmp_dir):
    # clean temp dir
    delete_files_in_directory(tmp_dir)

    model = YOLO(MODEL_NAME)
    results = model.predict(
        source=photo_weld,
    )
    # move source file to user's tmp_dir
    files = os.listdir('./')
    for file in files:
        if file.endswith('.jpg'):
            file_path_source = os.path.join('./', file)
            file_path_destination = os.path.join(tmp_dir, file)
            if os.path.isfile(file_path_source):
                os.rename(file_path_source, file_path_destination)

    tmp_file_name = str(tempfile.TemporaryFile(dir=tmp_dir).name) + '.jpg'
    results[0].save(filename=tmp_file_name)
    labels = []
    for cls in results[0].boxes.cls:
        class_label = model.names[int(cls)]
        labels.append(class_label)

    return tmp_file_name, pd.Series(labels)


def get_user_info(chat_id):
    now = datetime.now()
    if chat_id in USERS.index:
        USERS.at[chat_id, 'count_photos'] = USERS.loc[chat_id, 'count_photos'] + 1
    else:
        tempfile.tempdir = os.path.join(BASE_DIR, TEMP_DIR)
        temp_dir = tempfile.mkdtemp()
        USERS.loc[chat_id] = [now, 1, temp_dir]

    user_data = USERS.loc[chat_id].to_dict()
    user_data['access_allowed'] = True
    if (
        (now - user_data['start_period']).total_seconds() / 60
        <= PERIOD_LIMIT_MINUTES
        and user_data['count_photos'] > COUNT_PHOTOS_LIMIT
    ):
        user_data['access_allowed'] = False
    elif (now - user_data['start_period']).total_seconds() / 60 > PERIOD_LIMIT_MINUTES:
        USERS.loc[chat_id] = [now, 1, USERS.loc[chat_id]['tmp_dir']]

    return user_data


def get_predict(update, context, photo=True):
    chat = update.effective_chat
    name = update.message.chat.first_name
    user_data = get_user_info(chat.id)
    if not user_data['access_allowed']:
        logger.info(f'User {name} chat_id={chat.id} reached the limit photos.')
        context.bot.send_message(
            chat_id=chat.id,
            text=f'Вы достигли ограничения по загрузке фото, пожалуйста подождите {PERIOD_LIMIT_MINUTES} минут!',
        )
        return

    try:
        if photo:
            photo_weld = context.bot.get_file(update.message.photo[-1].file_id)
        else:
            photo_weld = context.bot.get_file(update.message.document)

        logger.info(
            f'User {name} chat_id={chat.id} upload photo to {user_data["tmp_dir"]}'
        )
        inference_file_name, labels = get_image_predict(
            photo_weld.file_path, user_data['tmp_dir']
        )
        inference_file = open(inference_file_name, 'rb')
        message = 'Недостатков не обнаружено!'
        if labels.shape[0] > 0:
            message = (
                'Обнаружены следующие недостатки:\n'
                + labels.value_counts().to_string()
            )
        button = ReplyKeyboardMarkup([['Не согласны?']], resize_keyboard=True)
        context.bot.send_photo(
            chat.id, inference_file, message, reply_markup=button
        )
        inference_file.close()
    except Exception as error:
        logger.error(
            f'User {name} chat_id={chat.id} raise error on prediction {error}'
        )
        context.bot.send_message(
            chat_id=chat.id,
            text=f'При детекции произошла ошибка, {error}!',
        )


def only_photo(update, context):
    if update.message.text != None and len(update.message.text) > 0:
        chat = update.effective_chat
        name = update.message.chat.first_name
        logger.info(f'User {name} chat_id={chat.id} upload not photo.')
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
    setup_logger(logger, file_name='logs/ai_weldbot.log')
    delete_temp_dir(os.path.join(BASE_DIR, TEMP_DIR))

    updater = Updater(token=BOT_TOKEN)
    updater.dispatcher.add_handler(MessageHandler(Filters.photo, get_predict))
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.dispatcher.add_handler(CommandHandler('feedback', feedback))
    updater.dispatcher.add_handler(MessageHandler(~Filters.photo, only_photo))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
