from __future__ import annotations

"""
Работа с базой данных SQLite для регистрации команд на турнир по Dota 2.
"""
import aiosqlite

DB_PATH = "tournament.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER UNIQUE NOT NULL,
    tg_username TEXT,
    team_name TEXT NOT NULL,
    captain_contact TEXT NOT NULL,
    mmr TEXT NOT NULL,
    players_info TEXT NOT NULL,
    substitutes_info TEXT NOT NULL,
    registered_at TEXT DEFAULT (datetime('now'))
);
"""


async def init_db() -> None:
    """Создаёт таблицу, если её ещё нет. Вызывать один раз при старте бота."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def is_registered(tg_user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM participants WHERE tg_user_id = ?", (tg_user_id,)
        )
        row = await cursor.fetchone()
        return row is not None


async def get_participant(tg_user_id: int) -> tuple | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT team_name, captain_contact, mmr, players_info, substitutes_info, registered_at
            FROM participants WHERE tg_user_id = ?
            """,
            (tg_user_id,),
        )
        return await cursor.fetchone()


async def count_participants() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM participants")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_participant(
    tg_user_id: int,
    tg_username: str | None,
    team_name: str,
    captain_contact: str,
    mmr: str,
    players_info: str,
    substitutes_info: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO participants
                (tg_user_id, tg_username, team_name, captain_contact, mmr, players_info, substitutes_info)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tg_user_id, tg_username, team_name, captain_contact, mmr, players_info, substitutes_info),
        )
        await db.commit()


async def get_all_participants() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT team_name, captain_contact, mmr, players_info, substitutes_info, tg_username, registered_at
            FROM participants
            ORDER BY registered_at
            """
        )
        return await cursor.fetchall()


async def remove_participant(tg_user_id: int) -> bool:
    """Отменяет регистрацию. Возвращает True, если запись была удалена."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM participants WHERE tg_user_id = ?", (tg_user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0