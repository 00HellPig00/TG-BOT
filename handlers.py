"""
Обработчики команд, инлайн-кнопок и шагов регистрации команды на турнир.
"""
import csv
import io
import os

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)

import database as db
import sheets
import excel_export
from states import Registration

router = Router()

ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}
MAX_PARTICIPANTS = int(os.getenv("MAX_PARTICIPANTS", "0"))

TOURNAMENT_NAME = "Звенигородский турнир по дисциплине Dota 2"

CANCEL_TEXT = "❌ Отмена"
CONFIRM_TEXT = "✅ Подтвердить"
RETRY_TEXT = "✏️ Ввести заново"

# ---------- инлайн-клавиатуры ----------

main_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data="menu_register")],
        [InlineKeyboardButton(text="✅ Проверить регистрацию", callback_data="menu_check")],
    ]
)

cancel_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text=CANCEL_TEXT, callback_data="reg_cancel")]]
)

confirm_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=CONFIRM_TEXT, callback_data="reg_confirm")],
        [InlineKeyboardButton(text=RETRY_TEXT, callback_data="reg_retry")],
        [InlineKeyboardButton(text=CANCEL_TEXT, callback_data="reg_cancel")],
    ]
)

status_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data="status_delete_ask")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="status_back")],
    ]
)

status_delete_confirm_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отменить", callback_data="status_delete_yes")],
        [InlineKeyboardButton(text="⬅️ Нет, назад", callback_data="status_delete_no")],
    ]
)

NO_SUBSTITUTES_TEXT = "Без замен"

substitutes_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Без замен", callback_data="subs_skip")],
        [InlineKeyboardButton(text=CANCEL_TEXT, callback_data="reg_cancel")],
    ]
)


def status_text(row: tuple) -> str:
    team_name, captain_contact, mmr, players_info, substitutes_info, registered_at = row
    return (
        "✅ Вы зарегистрированы на турнир.\n\n"
        f"🏳 Команда: {team_name}\n"
        f"👤 Капитан: {captain_contact}\n"
        f"📊 MMR команды: {mmr}\n"
        f"👥 Основной состав:\n{players_info}\n\n"
        f"🔁 Замены:\n{substitutes_info}\n\n"
        f"🗓 Дата регистрации: {registered_at}"
    )


def parse_player_lines(text: str) -> list[str]:
    """Возвращает непустые строки ввода — каждая строка считается одним игроком."""
    return [line.strip() for line in text.splitlines() if line.strip()]


# ---------- приветствие и главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"👋 Добро пожаловать на {TOURNAMENT_NAME}!\n\n"
        "Выберите действие ниже:",
        reply_markup=main_menu_kb,
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=main_menu_kb)


@router.callback_query(F.data == "menu_check")
async def cb_check(callback: CallbackQuery) -> None:
    row = await db.get_participant(callback.from_user.id)
    if row:
        await callback.message.edit_text(status_text(row), reply_markup=status_kb)
    else:
        await callback.message.edit_text(
            "Вы ещё не зарегистрированы.\n\nВыберите действие:",
            reply_markup=main_menu_kb,
        )
    await callback.answer()


@router.callback_query(F.data == "status_back")
async def cb_status_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Выберите действие:", reply_markup=main_menu_kb)
    await callback.answer()


@router.callback_query(F.data == "status_delete_ask")
async def cb_status_delete_ask(callback: CallbackQuery) -> None:
    row = await db.get_participant(callback.from_user.id)
    if not row:
        await callback.message.edit_text("Вы уже не зарегистрированы.", reply_markup=main_menu_kb)
        await callback.answer()
        return

    team_name = row[0]
    await callback.message.edit_text(
        f"Вы уверены, что хотите отменить регистрацию команды «{team_name}»?\n"
        "Это действие нельзя отменить — придётся регистрироваться заново.",
        reply_markup=status_delete_confirm_kb,
    )
    await callback.answer()


@router.callback_query(F.data == "status_delete_no")
async def cb_status_delete_no(callback: CallbackQuery) -> None:
    row = await db.get_participant(callback.from_user.id)
    if row:
        await callback.message.edit_text(status_text(row), reply_markup=status_kb)
    else:
        await callback.message.edit_text("Выберите действие:", reply_markup=main_menu_kb)
    await callback.answer()


@router.callback_query(F.data == "status_delete_yes")
async def cb_status_delete_yes(callback: CallbackQuery) -> None:
    removed = await db.remove_participant(callback.from_user.id)
    if removed:
        if sheets.is_enabled():
            sheets.mark_cancelled(callback.from_user.id)
        if excel_export.is_enabled():
            await excel_export.remove_registration(callback.from_user.id)
        await callback.message.edit_text(
            "Регистрация команды отменена. Если передумаете — /menu.",
            reply_markup=main_menu_kb,
        )
        await callback.answer("Регистрация отменена")
    else:
        await callback.message.edit_text("Вы не были зарегистрированы.", reply_markup=main_menu_kb)
        await callback.answer()


@router.callback_query(F.data == "menu_register")
async def cb_register(callback: CallbackQuery, state: FSMContext) -> None:
    if await db.is_registered(callback.from_user.id):
        await callback.message.edit_text(
            "Ваша команда уже зарегистрирована.\n\n"
            "Если нужно изменить данные — сначала отмените регистрацию командой "
            "/cancel_registration, затем зарегистрируйтесь заново."
        )
        await callback.answer()
        return

    if MAX_PARTICIPANTS and await db.count_participants() >= MAX_PARTICIPANTS:
        await callback.message.edit_text("К сожалению, регистрация закрыта — набран лимит команд.")
        await callback.answer()
        return

    await state.set_state(Registration.waiting_for_team_name)
    await callback.message.edit_text(
        "Начнём регистрацию команды!\n\n1️⃣ Напишите название вашей команды:",
    )
    await callback.message.answer("Отменить регистрацию можно в любой момент:", reply_markup=cancel_inline_kb)
    await callback.answer()


# ---------- прочие команды ----------

@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    row = await db.get_participant(message.from_user.id)
    if row:
        await message.answer(status_text(row), reply_markup=status_kb)
    else:
        await message.answer("Вы ещё не зарегистрированы. Наберите /menu, чтобы начать.")


@router.message(Command("cancel_registration"))
async def cmd_cancel_registration(message: Message) -> None:
    removed = await db.remove_participant(message.from_user.id)
    if removed:
        if sheets.is_enabled():
            sheets.mark_cancelled(message.from_user.id)
        if excel_export.is_enabled():
            await excel_export.remove_registration(message.from_user.id)
        await message.answer("Регистрация команды отменена. Если передумаете — /menu.")
    else:
        await message.answer("Вы не были зарегистрированы.")


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда доступна только организаторам.")
        return

    rows = await db.get_all_participants()
    if not rows:
        await message.answer("Пока никто не зарегистрирован.")
        return

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Команда", "Капитан", "MMR", "Основной состав", "Замены", "Telegram", "Дата регистрации"])
    for team_name, captain_contact, mmr, players_info, substitutes_info, username, registered_at in rows:
        writer.writerow(
            [
                team_name,
                captain_contact,
                mmr,
                players_info,
                substitutes_info,
                f"@{username}" if username else "",
                registered_at,
            ]
        )

    file = BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename="teams.csv")
    await message.answer_document(file, caption=f"Всего команд: {len(rows)}")


# ---------- отмена в процессе регистрации ----------

@router.callback_query(F.data == "reg_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Регистрация отменена.")
    await callback.message.answer("Выберите действие:", reply_markup=main_menu_kb)
    await callback.answer()


# ---------- шаг 1: название команды ----------

@router.message(Registration.waiting_for_team_name)
async def process_team_name(message: Message, state: FSMContext) -> None:
    team_name = (message.text or "").strip()
    if len(team_name) < 2:
        await message.answer("Название команды слишком короткое. Попробуйте ещё раз:")
        return

    await state.update_data(team_name=team_name)
    await state.set_state(Registration.waiting_for_captain_contact)
    await message.answer(
        "2️⃣ Укажите @username капитана команды для связи:",
        reply_markup=cancel_inline_kb,
    )


# ---------- шаг 2: контакт капитана ----------

@router.message(Registration.waiting_for_captain_contact)
async def process_captain_contact(message: Message, state: FSMContext) -> None:
    contact = (message.text or "").strip()
    if len(contact) < 2:
        await message.answer("Введите корректный @username капитана.")
        return

    await state.update_data(captain_contact=contact)
    await state.set_state(Registration.waiting_for_mmr)
    await message.answer(
        "3️⃣ Напишите общий показатель MMR на команду "
        "(например, 10000 или 20000 — ограничений нет):",
        reply_markup=cancel_inline_kb,
    )


# ---------- шаг 3: MMR ----------

@router.message(Registration.waiting_for_mmr)
async def process_mmr(message: Message, state: FSMContext) -> None:
    mmr = (message.text or "").strip()
    if not mmr.isdigit():
        await message.answer("MMR должен быть числом. Попробуйте ещё раз, например: 15000")
        return

    await state.update_data(mmr=mmr)
    await state.set_state(Registration.waiting_for_players)
    await message.answer(
        "4️⃣ Напишите никнеймы всех игроков основного состава и ссылки на их профили Dotabuff.\n\n"
        "Ровно 5 человек, каждый — отдельной строкой, например:\n"
        "Nickname1 — https://www.dotabuff.com/players/100000001\n"
        "Nickname2 — https://www.dotabuff.com/players/100000002\n"
        "Nickname3 — https://www.dotabuff.com/players/100000003\n"
        "Nickname4 — https://www.dotabuff.com/players/100000004\n"
        "Nickname5 — https://www.dotabuff.com/players/100000005",
        reply_markup=cancel_inline_kb,
    )


# ---------- шаг 4: основной состав (ровно 5 игроков) ----------

@router.message(Registration.waiting_for_players)
async def process_players(message: Message, state: FSMContext) -> None:
    lines = parse_player_lines(message.text or "")

    if len(lines) != 5:
        await message.answer(
            f"❗️ Ошибка регистрации: указано игроков — {len(lines)}, а нужно ровно 5.\n\n"
            "Пришлите данные заново, каждый игрок — отдельной строкой "
            "(никнейм и ссылка на профиль Dotabuff), минимум и максимум — 5 человек:"
        )
        return

    players_info = "\n".join(lines)
    await state.update_data(players_info=players_info)
    await state.set_state(Registration.waiting_for_substitutes)
    await message.answer(
        "5️⃣ Напишите никнеймы запасных игроков и ссылки на их профили Dotabuff.\n\n"
        "Можно указать 1 или 2 замены, каждая — отдельной строкой, например:\n"
        "SubNickname1 — https://www.dotabuff.com/players/200000001\n\n"
        "Если запасных нет — нажмите кнопку «Без замен» ниже.",
        reply_markup=substitutes_kb,
    )


# ---------- шаг 5: замены (0, 1 или 2 игрока) ----------

async def show_confirm_summary(state: FSMContext, answer_func) -> None:
    """Показывает итоговую сводку перед сохранением. answer_func — message.answer или callback.message.edit_text."""
    data = await state.get_data()
    summary = (
        "Проверьте данные:\n\n"
        f"🏳 Команда: {data['team_name']}\n"
        f"👤 Капитан: {data['captain_contact']}\n"
        f"📊 MMR команды: {data['mmr']}\n"
        f"👥 Основной состав:\n{data['players_info']}\n\n"
        f"🔁 Замены:\n{data['substitutes_info']}\n\n"
        "Всё верно?"
    )
    await state.set_state(Registration.waiting_for_confirm)
    await answer_func(summary, reply_markup=confirm_inline_kb)


@router.message(Registration.waiting_for_substitutes)
async def process_substitutes(message: Message, state: FSMContext) -> None:
    lines = parse_player_lines(message.text or "")

    if not (1 <= len(lines) <= 2):
        await message.answer(
            f"❗️ Ошибка регистрации: указано замен — {len(lines)}, а нужно 1 или 2.\n\n"
            "Пришлите данные заново, каждая замена — отдельной строкой "
            "(никнейм и ссылка на профиль Dotabuff), либо нажмите «Без замен» выше:"
        )
        return

    await state.update_data(substitutes_info="\n".join(lines))
    await show_confirm_summary(state, message.answer)


@router.callback_query(Registration.waiting_for_substitutes, F.data == "subs_skip")
async def cb_skip_substitutes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(substitutes_info=NO_SUBSTITUTES_TEXT)
    await show_confirm_summary(state, callback.message.edit_text)
    await callback.answer()


# ---------- подтверждение ----------

@router.callback_query(Registration.waiting_for_confirm, F.data == "reg_retry")
async def cb_retry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.waiting_for_team_name)
    await callback.message.edit_text("Хорошо, начнём заново.\n\n1️⃣ Напишите название вашей команды:")
    await callback.answer()


@router.callback_query(Registration.waiting_for_confirm, F.data == "reg_confirm")
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()

    await db.add_participant(
        tg_user_id=callback.from_user.id,
        tg_username=callback.from_user.username,
        team_name=data["team_name"],
        captain_contact=data["captain_contact"],
        mmr=data["mmr"],
        players_info=data["players_info"],
        substitutes_info=data["substitutes_info"],
    )

    if sheets.is_enabled() or excel_export.is_enabled():
        row = await db.get_participant(callback.from_user.id)
        registered_at = row[5] if row else ""

        if sheets.is_enabled():
            sheets.append_registration(
                tg_user_id=callback.from_user.id,
                tg_username=callback.from_user.username,
                team_name=data["team_name"],
                captain_contact=data["captain_contact"],
                mmr=data["mmr"],
                players_info=data["players_info"],
                substitutes_info=data["substitutes_info"],
                registered_at=registered_at,
            )

        if excel_export.is_enabled():
            await excel_export.append_registration(
                tg_user_id=callback.from_user.id,
                tg_username=callback.from_user.username,
                team_name=data["team_name"],
                captain_contact=data["captain_contact"],
                mmr=data["mmr"],
                players_info=data["players_info"],
                substitutes_info=data["substitutes_info"],
                registered_at=registered_at,
            )

    await state.clear()
    await callback.message.edit_text(
        "🎉 Готово! Ваша команда зарегистрирована на турнир.\n"
        "Проверить статус можно в любой момент через /menu."
    )
    await callback.answer("Команда зарегистрирована!")
