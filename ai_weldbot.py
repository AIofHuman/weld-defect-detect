import logging
import logging.handlers
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.chataction import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv('BOT_TOKEN')
TEMP_DIR = 'tmp'
USERS_DATA = 'users_data'
MODEL_NAME = './yolov8m_200epoch_rus_cls_name.pt'
USERS = pd.DataFrame(
    columns=['start_period', 'count_photos', 'tmp_dir', 'waiting_feedback']
)
PERIOD_LIMIT_MINUTES = 10
COUNT_PHOTOS_LIMIT = 10


def setup_logger(logger, file_name):
    format_string = '%(asctime)s-%(levelname)s:%(message)s'
    logging.basicConfig(
        format=format_string,
        datefmt='%Y/%m/%d/ %H:%M:%S',
        level=logging.INFO,
    )
    formatter = logging.Formatter(format_string)

    handler = logging.handlers.RotatingFileHandler(
        filename=file_name,
        encoding='utf-8',
        maxBytes=1024 * 1024 * 10,
        backupCount=5,
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def delete_temp_dir(directory_path):
    try:
        for root, dirs, files in os.walk(directory_path):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                delete_files_in_directory(dir_path)
                os.rmdir(dir_path)

        print('Temp directory deleted successfully.')
    except OSError:
        print('Error occurred while deleting temp directory.')


def delete_files_in_directory(directory_path):
    try:
        files = os.listdir(directory_path)
        for file in files:
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

    except OSError as error:
        logger.error(f'Raise error on temp files delete: {error}')
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
        USERS.at[chat_id, 'count_photos'] = (
            USERS.loc[chat_id, 'count_photos'] + 1
        )
    else:
        tempfile.tempdir = os.path.join(BASE_DIR, TEMP_DIR)
        temp_dir = tempfile.mkdtemp()
        USERS.loc[chat_id] = [now, 1, temp_dir, False]

    user_data = USERS.loc[chat_id].to_dict()
    user_data['access_allowed'] = True
    if (
        now - user_data['start_period']
    ).total_seconds() / 60 <= PERIOD_LIMIT_MINUTES and user_data[
        'count_photos'
    ] > COUNT_PHOTOS_LIMIT:
        user_data['access_allowed'] = False
    elif (
        now - user_data['start_period']
    ).total_seconds() / 60 > PERIOD_LIMIT_MINUTES:
        USERS.loc[chat_id] = [
            now,
            1,
            USERS.loc[chat_id, 'tmp_dir'],
            USERS.loc[chat_id, 'waiting_feedback'],
        ]

    return user_data


def get_predict(update, context, photo=True):
    chat = update.effective_chat
    name = update.message.chat.first_name
    context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
    user_data = get_user_info(chat.id)
    USERS.loc[chat.id, 'waiting_feedback'] = False

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

        context.bot.send_photo(
            chat.id,
            inference_file,
            message,
        )
        update.message.reply_text(
            text='Если есть замечания по диагностике жми на кнопку',
            reply_markup=get_buttons(),
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


def save_feedback(chat_id, text_message, tmp_dir):
    print('Saving feedback')
    # move image file to user_data\{chat_id} directory

    txt_created = False
    files = os.listdir(tmp_dir)
    for file in files:
        if file.endswith('.jpg'):
            file_path_source = os.path.join(tmp_dir, file)
            path_users_data = os.path.join(BASE_DIR, USERS_DATA)
            path_users_data = os.path.join(path_users_data, str(chat_id))
            file_path_destination = os.path.join(path_users_data, file)
            os.makedirs(os.path.dirname(file_path_destination), exist_ok=True)
            if os.path.isfile(file_path_source):
                os.rename(file_path_source, file_path_destination)
                # save text description as same file with .txt extension
                txt_file_name = (
                    os.path.splitext(file_path_destination)[0] + '.txt'
                )
                if not txt_created:
                    with open(txt_file_name, 'w', encoding='utf-8') as file:
                        file.write(text_message)
                    txt_created = True


def text_message(update, context):
    if update.message.text != None and len(update.message.text) > 0:
        chat = update.effective_chat
        name = update.message.chat.first_name
        if USERS.loc[chat.id, 'waiting_feedback']:
            save_feedback(
                chat.id, update.message.text, USERS.loc[chat.id, 'tmp_dir']
            )
            logger.info(f'User {name} chat_id={chat.id} save feedback.')
            context.bot.send_message(
                chat_id=chat.id,
                text=f'Спасибо, {name}!',
            )
            USERS.loc[chat.id, 'waiting_feedback'] = False
        else:
            logger.info(f'User {name} chat_id={chat.id} upload not photo.')
            context.bot.send_message(
                chat_id=chat.id,
                text=f'Ожидаю только фото сварного шва для детекции дефектов! Большего, я пока не могу, {name}!',
            )
    elif update.message.document != None:
        get_predict(update, context, photo=False)


def feedback(update, context):
    chat = update.effective_chat

    USERS.loc[chat.id, 'waiting_feedback'] = True
    context.bot.send_message(
        chat_id=chat.id,
        text='Прошу, как можно подробнее описать замечания к диагностике\n',
        # text=f'Спасибо! Учтем Ваши замечания и станем лучше!',
    )


def get_buttons():
    keyboard = [
        [
            InlineKeyboardButton(
                'Обратная связь по диагностике', callback_data='1'
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard, resize_keyboard=True)
    return reply_markup


def button(update, context):
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    if query.data == '1':
        feedback(update, context)
    else:
        print('Something unknown get')


def help(update, context):
    chat = update.effective_chat
    USERS.loc[chat.id, 'waiting_feedback'] = False
    context.bot.send_message(
        chat_id=chat.id,
        text='Ожидаю, либо фото сварного шва, либо комментарий к проведенной диагностике',
    )


def wake_up(update, context):
    chat = update.effective_chat

    context.bot.send_message(
        chat_id=chat.id,
        text='Приветствую Вас! Ожидаю фото сварного шва!',
    )


def main():
    setup_logger(
        logger, file_name=os.path.join(BASE_DIR, 'logs', 'ai_weldbot.log')
    )
    delete_temp_dir(os.path.join(BASE_DIR, TEMP_DIR))

    updater = Updater(token=BOT_TOKEN)
    updater.dispatcher.add_handler(MessageHandler(Filters.photo, get_predict))
    updater.dispatcher.add_handler(CommandHandler('start', wake_up))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(MessageHandler(~Filters.photo, text_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
