# Telegram-бот регистрации на турнир по Dota 2

Бот принимает заявки команд на турнир по Dota 2. Участники регистрируются в Telegram за пару минут, организатор получает список команд в базе, в Excel и (по желанию) в Google Таблицах.

**Стек:** Python 3.12 · aiogram 3 · SQLite (aiosqlite) · openpyxl · gspread (опционально)

## Возможности

- Пошаговая регистрация команды:
  1. название команды;
  2. контакт капитана (@username);
  3. средний MMR команды;
  4. ровно 5 игроков основного состава: `никнейм — ссылка на профиль Steam`;
  5. 1–2 запасных игрока в том же формате или кнопка «Без замен»;
  6. подтверждение заявки.
- Проверка статуса регистрации и отмена регистрации (кнопки и команды).
- Защита от повторной регистрации: один аккаунт Telegram — одна команда.
- Дублирование данных в **Excel** (`teams.xlsx`): строка добавляется при регистрации и удаляется при отмене.
- Опциональная синхронизация с **Google Таблицами**.
- Выгрузка всех заявок в CSV для организаторов (`/export`).
- Необязательный лимит числа команд.
- Работа 24/7 на VPS через systemd.

## Команды бота

| Команда | Кто | Что делает |
|---|---|---|
| `/start`, `/menu` | все | главное меню: регистрация, проверка статуса |
| `/status` | все | показать данные своей команды |
| `/cancel_registration` | все | отменить регистрацию |
| `/export` | организаторы | прислать CSV со всеми заявками |

## Быстрый старт (локально)

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd <ПАПКА_РЕПОЗИТОРИЯ>

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # затем заполните .env
python3 bot.py
```

При первом запуске автоматически создаётся база `tournament.db`.

## Настройка (.env)

Токен и ключи **не хранятся в репозитории**: файл `.env` добавлен в `.gitignore`.

```env
# Обязательно
BOT_TOKEN=токен_от_@BotFather

# ID организаторов через запятую (узнать свой ID можно у @userinfobot)
ADMIN_IDS=123456789

# Лимит команд, 0 — без ограничений
MAX_PARTICIPANTS=0

# Название турнира в приветствии (по умолчанию: «Турнир по дисциплине Dota 2»)
TOURNAMENT_NAME=Название вашего турнира

# Excel (по умолчанию включено)
EXCEL_EXPORT_ENABLED=1
EXCEL_FILE_PATH=teams.xlsx

# Google Таблицы (опционально, можно не заполнять)
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SHEETS_WORKSHEET_NAME=Регистрации

# Прокси к Telegram API (только если api.telegram.org недоступен у хостера)
TELEGRAM_API_PROXY=
```

### Google Таблицы (необязательно)

1. Создайте сервисный аккаунт в Google Cloud и скачайте JSON-ключ.
2. Включите Google Sheets API и Google Drive API.
3. Откройте нужную таблицу и дайте сервисному аккаунту (email из ключа) права редактора.
4. Укажите путь к ключу и ID таблицы (часть ссылки между `/d/` и `/edit`) в `.env`.

Если переменные не заданы, синхронизация с Google Таблицами просто отключена.

## Деплой на VPS (Ubuntu, 24/7)

Бот запускается как служба systemd и переживает перезагрузку сервера.

1. Скопируйте проект на сервер, например в `/root/TGBOT`, создайте `venv` и установите зависимости (см. выше), положите `.env`.
2. Установите службу:

   ```bash
   cp tgbot.service /etc/systemd/system/tgbot.service
   systemctl daemon-reload
   systemctl enable tgbot
   systemctl start tgbot
   ```

3. Полезные команды:

   ```bash
   systemctl status tgbot        # состояние (выход из просмотра: q)
   systemctl restart tgbot       # перезапуск после обновления кода
   systemctl stop tgbot          # остановка
   journalctl -u tgbot -f        # логи в реальном времени (выход: Ctrl+C)
   ```

4. Обновление бота: загрузите новые файлы на сервер и выполните `systemctl restart tgbot`.
   Скачать Excel на свой компьютер:

   ```bash
   scp root@IP_СЕРВЕРА:/root/TGBOT/teams.xlsx ~/Desktop/teams.xlsx
   ```

> Важно: на один токен бота должен работать только один экземпляр, иначе Telegram вернёт `TelegramConflictError`. Перед запуском на новом сервере остановите бота на старом.

## Если Telegram заблокирован у хостера

Лучше выбрать VPS за пределами РФ. Запасной вариант — прокси на Cloudflare Workers: код в `cloudflare-worker.js`, адрес прокси указывается в `TELEGRAM_API_PROXY`.

## Структура проекта

```
.
├── bot.py                 # точка входа, запуск polling
├── handlers.py            # обработчики команд и шагов регистрации
├── states.py              # состояния FSM
├── database.py            # SQLite (aiosqlite)
├── excel_export.py        # запись и удаление строк в teams.xlsx
├── sheets.py              # Google Таблицы (опционально)
├── cloudflare-worker.js   # прокси к Telegram API (опционально)
├── tgbot.service          # unit-файл systemd
├── requirements.txt
├── .env.example
└── README.md
```
