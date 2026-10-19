# ==========================================================
# DEEP EMOTIONS — DATABASE
# SQLite Database
# ==========================================================

from pathlib import Path

import aiosqlite


# ==========================================================
# DATABASE PATH / RETENTION
# ==========================================================

DB_PATH = Path("data/deep_emotions.db")

# Keep the database small and prevent old conversations from
# growing forever.
MESSAGE_RETENTION_DAYS = 7
MEMORY_RETENTION_DAYS = 30
MAX_MEMORIES_PER_USER = 20
MAX_GROUP_MESSAGES_PER_CHAT = 50


# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================

async def init_db():
    """
    Create database directory and all required tables.
    Also clean old stored data.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with aiosqlite.connect(DB_PATH) as db:

        # --------------------------------------------------
        # Personal Conversation History
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # --------------------------------------------------
        # Long-Term Memories
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                memory TEXT NOT NULL,
                created_at DATETIME
                    DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # --------------------------------------------------
        # Group Conversation Context
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                display_name TEXT,
                content TEXT NOT NULL,
                created_at DATETIME
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # --------------------------------------------------
        # Indexes
        # --------------------------------------------------

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_messages_chat_user
            ON messages(chat_id, user_id, id)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_memories_user
            ON memories(user_id, id)
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_group_messages_chat
            ON group_messages(chat_id, id)
            """
        )

        # Clean old data every time the bot starts.
        await cleanup_old_data(db)

        await db.commit()


async def cleanup_old_data(db=None):
    """
    Remove old conversation data and keep only a small memory set.

    - Personal/group messages older than 7 days are deleted.
    - Memories older than 30 days are deleted.
    - Only the latest 20 memories per user are retained.
    - Group context is capped at 50 messages per group.
    """

    owns_connection = db is None

    if owns_connection:
        db = await aiosqlite.connect(DB_PATH)

    try:
        await db.execute(
            """
            DELETE FROM messages
            WHERE created_at < datetime('now', ?)
            """,
            (f"-{MESSAGE_RETENTION_DAYS} days",),
        )

        await db.execute(
            """
            DELETE FROM group_messages
            WHERE created_at < datetime('now', ?)
            """,
            (f"-{MESSAGE_RETENTION_DAYS} days",),
        )

        await db.execute(
            """
            DELETE FROM memories
            WHERE created_at < datetime('now', ?)
            """,
            (f"-{MEMORY_RETENTION_DAYS} days",),
        )

        # Keep only the latest MAX_MEMORIES_PER_USER memories
        # for each user.
        cursor = await db.execute(
            """
            SELECT DISTINCT user_id
            FROM memories
            """
        )
        users = await cursor.fetchall()

        for (user_id,) in users:
            await db.execute(
                """
                DELETE FROM memories
                WHERE user_id = ?
                AND id NOT IN (
                    SELECT id
                    FROM memories
                    WHERE user_id = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT ?
                )
                """,
                (
                    user_id,
                    user_id,
                    MAX_MEMORIES_PER_USER,
                ),
            )

        if owns_connection:
            await db.commit()

    finally:
        if owns_connection:
            await db.close()


# ==========================================================
# PROACTIVE GROUP STATE
# ==========================================================

async def init_proactive_state_table(db=None):
    owns_connection = db is None
    if owns_connection:
        db = await aiosqlite.connect(DB_PATH)
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS proactive_state (
                chat_id INTEGER PRIMARY KEY,
                period TEXT,
                greeting_date TEXT,
                last_sent_at REAL DEFAULT 0,
                next_due REAL DEFAULT 0
            )
            """
        )
        if owns_connection:
            await db.commit()
    finally:
        if owns_connection:
            await db.close()


async def get_proactive_state(chat_id):
    await init_proactive_state_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT period, greeting_date, last_sent_at, next_due
            FROM proactive_state
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        return await cursor.fetchone()


async def set_proactive_state(chat_id, period, greeting_date, last_sent_at, next_due):
    await init_proactive_state_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO proactive_state(
                chat_id, period, greeting_date, last_sent_at, next_due
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                period = excluded.period,
                greeting_date = excluded.greeting_date,
                last_sent_at = excluded.last_sent_at,
                next_due = excluded.next_due
            """,
            (chat_id, period, greeting_date, last_sent_at, next_due),
        )
        await db.commit()


# ==========================================================
# PERSONAL MESSAGE HISTORY
# ==========================================================

async def add_message(
    chat_id,
    user_id,
    role,
    content,
):
    """
    Save one message to conversation history.
    """

    if not content:
        return

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT INTO messages(
                chat_id,
                user_id,
                role,
                content
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                role,
                content,
            ),
        )

        # Keep only the latest 30 messages for this chat/user.
        await db.execute(
            """
            DELETE FROM messages
            WHERE chat_id = ?
            AND user_id = ?
            AND id NOT IN (
                SELECT id
                FROM messages
                WHERE chat_id = ?
                AND user_id = ?
                ORDER BY id DESC
                LIMIT 30
            )
            """,
            (
                chat_id,
                user_id,
                chat_id,
                user_id,
            ),
        )

        await db.commit()


async def get_history(
    chat_id,
    user_id,
    limit=10,
):
    """
    Get latest conversation messages.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT role, content
            FROM messages
            WHERE chat_id = ?
            AND user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                chat_id,
                user_id,
                limit,
            ),
        )

        rows = await cursor.fetchall()

    return list(
        reversed(rows)
    )


async def clear_history(
    chat_id,
    user_id,
):
    """
    Delete conversation history
    for one user in one chat.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            DELETE FROM messages
            WHERE chat_id = ?
            AND user_id = ?
            """,
            (
                chat_id,
                user_id,
            ),
        )

        await db.commit()


async def count_messages(
    chat_id,
    user_id,
):
    """
    Count saved conversation messages.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE chat_id = ?
            AND user_id = ?
            """,
            (
                chat_id,
                user_id,
            ),
        )

        row = await cursor.fetchone()

    return row[0]


# ==========================================================
# LONG-TERM MEMORY
# ==========================================================

async def add_memory(
    user_id,
    memory,
):
    """
    Save a long-term memory.

    Duplicate memories are ignored.
    """

    if not memory:
        return False

    memory = memory.strip()

    if not memory:
        return False

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT id
            FROM memories
            WHERE user_id = ?
            AND LOWER(memory) = LOWER(?)
            LIMIT 1
            """,
            (
                user_id,
                memory,
            ),
        )

        existing = await cursor.fetchone()

        if existing:
            return False

        await db.execute(
            """
            INSERT INTO memories(
                user_id,
                memory
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                memory,
            ),
        )

        # Keep only the latest 20 memories for this user.
        await db.execute(
            """
            DELETE FROM memories
            WHERE user_id = ?
            AND id NOT IN (
                SELECT id
                FROM memories
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
            )
            """,
            (
                user_id,
                user_id,
                MAX_MEMORIES_PER_USER,
            ),
        )

        await db.commit()

    return True


async def get_memories(
    user_id,
    limit=10,
):
    """
    Get latest long-term memories.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT id, memory
            FROM memories
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        )

        rows = await cursor.fetchall()

    return rows


async def delete_memory(
    user_id,
    memory_id,
):
    """
    Delete one specific memory.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            DELETE FROM memories
            WHERE id = ?
            AND user_id = ?
            """,
            (
                memory_id,
                user_id,
            ),
        )

        await db.commit()

    return cursor.rowcount > 0


async def clear_memories(
    user_id,
):
    """
    Delete all memories for one user.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            DELETE FROM memories
            WHERE user_id = ?
            """,
            (user_id,),
        )

        await db.commit()


async def count_memories(
    user_id,
):
    """
    Count user's saved memories.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM memories
            WHERE user_id = ?
            """,
            (user_id,),
        )

        row = await cursor.fetchone()

    return row[0]


# ==========================================================
# GROUP CONVERSATION CONTEXT
# ==========================================================

async def add_group_message(
    chat_id,
    user_id,
    username,
    display_name,
    content,
):
    """
    Save a group message.

    Group context is completely separate
    from personal long-term memory.
    """

    if not content:
        return

    content = content.strip()

    if not content:
        return

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT INTO group_messages(
                chat_id,
                user_id,
                username,
                display_name,
                content
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                username,
                display_name,
                content,
            ),
        )

        # --------------------------------------------------
        # Keep latest 50 messages per group
        # --------------------------------------------------

        await db.execute(
            """
            DELETE FROM group_messages
            WHERE chat_id = ?
            AND id NOT IN (
                SELECT id
                FROM group_messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (
                chat_id,
                chat_id,
                MAX_GROUP_MESSAGES_PER_CHAT,
            ),
        )

        await db.commit()


async def get_group_context(
    chat_id,
    limit=10,
):
    """
    Get latest group messages.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT
                user_id,
                username,
                display_name,
                content
            FROM group_messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                chat_id,
                limit,
            ),
        )

        rows = await cursor.fetchall()

    return list(
        reversed(rows)
    )


async def clear_group_context(
    chat_id,
):
    """
    Delete stored group context.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            DELETE FROM group_messages
            WHERE chat_id = ?
            """,
            (chat_id,),
        )

        await db.commit()


async def count_group_messages(
    chat_id,
):
    """
    Count stored group context messages.
    """

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM group_messages
            WHERE chat_id = ?
            """,
            (chat_id,),
        )

        row = await cursor.fetchone()

    return row[0]


# ==========================================================
# ACTIVE GROUPS / MEMBERS FOR PROACTIVE CHAT
# ==========================================================

async def get_active_groups(limit=100):
    """Return groups that have recent stored conversation context."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT chat_id, MAX(id) AS last_id
            FROM group_messages
            GROUP BY chat_id
            ORDER BY last_id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def get_active_group_users(chat_id, limit=30):
    """Return recent distinct group participants."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id, username, display_name, MAX(id) AS last_id
            FROM group_messages
            WHERE chat_id = ?
            GROUP BY user_id, username, display_name
            ORDER BY last_id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
    return rows
