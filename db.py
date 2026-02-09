import asyncpg
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")
DATABASE_URL = os.getenv("DB_URL")

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    name TEXT,
    username TEXT,
    birthdate TEXT,
    number TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ NULL
);
"""

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool

    if not DATABASE_URL:
        raise RuntimeError("DB_URL not found in .env")

    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        ssl="require",
        statement_cache_size=0,   # ✅ главное исправление
    )

    async with _pool.acquire() as conn:
        await conn.execute(CREATE_USERS_TABLE)


async def get_pool():
    if _pool is None:
        await init_db()
    return _pool


async def is_user_registered(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1
            FROM users
            WHERE id = $1 AND is_deleted = FALSE
            LIMIT 1
            """,
            user_id
        )
        return row is not None


async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE id = $1 AND is_deleted = FALSE
            LIMIT 1
            """,
            user_id
        )
        return dict(row) if row else None


async def add_user(user_id: int, name: str, username: str, number: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, name, username, number, is_deleted, deleted_at)
            VALUES ($1, $2, $3, $4, FALSE, NULL)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name,
                username = EXCLUDED.username,
                number = EXCLUDED.number,
                is_deleted = FALSE,
                deleted_at = NULL
            """,
            user_id, name, username, number
        )


async def soft_delete_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET is_deleted = TRUE, deleted_at = NOW()
            WHERE id = $1
            """,
            user_id
        )


async def restore_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET is_deleted = FALSE, deleted_at = NULL
            WHERE id = $1
            """,
            user_id
        )
