from __future__ import annotations

"""
Дублирование регистраций команд в Google Sheets.

Работает только если в .env заданы:
  GOOGLE_SHEETS_CREDENTIALS_FILE — путь к JSON-ключу сервисного аккаунта
  GOOGLE_SHEETS_SPREADSHEET_ID   — ID таблицы (из её ссылки)

Если переменные не заданы, все функции тихо ничего не делают —
бот продолжает работать только с локальной SQLite-базой.
"""
import logging
import os

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
WORKSHEET_NAME = os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME", "Регистрации")

HEADER = [
    "Telegram ID",
    "Telegram username",
    "Команда",
    "Капитан",
    "MMR",
    "Основной состав",
    "Замены",
    "Дата регистрации",
]

_client = None
_worksheet = None
_enabled = bool(CREDENTIALS_FILE and SPREADSHEET_ID)


def is_enabled() -> bool:
    return _enabled


def _get_worksheet():
    """Ленивая инициализация клиента gspread. Возвращает None, если что-то не так."""
    global _client, _worksheet

    if not _enabled:
        return None

    if _worksheet is not None:
        return _worksheet

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        _client = gspread.authorize(creds)

        spreadsheet = _client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=len(HEADER))

        # если лист пустой — добавляем заголовок
        if not worksheet.get_all_values():
            worksheet.append_row(HEADER)

        _worksheet = worksheet
        return _worksheet
    except Exception:
        logger.exception("Не удалось подключиться к Google Sheets")
        return None


def append_registration(
    tg_user_id: int,
    tg_username: str | None,
    team_name: str,
    captain_contact: str,
    mmr: str,
    players_info: str,
    substitutes_info: str,
    registered_at: str,
) -> bool:
    """Добавляет строку с регистрацией команды. Возвращает True при успехе."""
    worksheet = _get_worksheet()
    if worksheet is None:
        return False

    try:
        worksheet.append_row(
            [
                str(tg_user_id),
                f"@{tg_username}" if tg_username else "",
                team_name,
                captain_contact,
                mmr,
                players_info,
                substitutes_info,
                registered_at,
            ],
            value_input_option="USER_ENTERED",
        )
        return True
    except Exception:
        logger.exception("Не удалось записать регистрацию в Google Sheets")
        return False


def mark_cancelled(tg_user_id: int) -> bool:
    """Помечает строку команды как отменённую (не удаляет, чтобы сохранить историю)."""
    worksheet = _get_worksheet()
    if worksheet is None:
        return False

    try:
        cell = worksheet.find(str(tg_user_id), in_column=1)
        if cell is None:
            return False
        last_col = len(HEADER)
        worksheet.update_cell(cell.row, last_col + 1, "ОТМЕНЕНО")
        return True
    except Exception:
        logger.exception("Не удалось отметить отмену регистрации в Google Sheets")
        return False