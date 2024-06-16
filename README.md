### Описание проекта:

Это проект c хакатона АтомикХак 2.0:
Определение дефектов сварных швов с помощью ИИ и telegram-bot

### Как запустить проект:

Клонировать репозиторий и перейти в него в командной строке:

```
git clone https://github.com/AIofHuman/weld-defect-detect.git
```

```
cd weld-defect-detect

```

Cоздать и активировать виртуальное окружение:

```
python -m venv env
```

```
source env/bin/activate
```

Установить зависимости из файла requirements.txt:

```
python -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

Выполнить миграции:

создать чат бота в telegram и прописать его token в .env файле (см. .env.example)

Запустить проект:

```
python ai_weldbot.py
```
