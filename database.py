"""
SQLite persistent database for Telegram Thumbnail Watermark Bot.
Tracks user statistics, admin configuration, and state handling.
"""

import sqlite3
import datetime
from typing import Dict, Any, List, Optional
from config import DB_PATH, DEFAULT_SETTINGS

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Settings table (key-value store for watermark configurations)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    total_processed INTEGER DEFAULT 0,
                    joined_at TEXT NOT NULL,
                    last_active TEXT NOT NULL
                )
            """)

            # Global counters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)

            # User admin state table (e.g. waiting_for_watermark)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # User custom thumbnails table (per-user active thumbnail)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_thumbnails (
                    user_id INTEGER PRIMARY KEY,
                    thumbnail_bytes BLOB NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Pending video operations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_videos (
                    user_id INTEGER PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    file_name TEXT,
                    width INTEGER,
                    height INTEGER,
                    duration INTEGER,
                    file_size INTEGER,
                    extracted_thumb BLOB,
                    created_at TEXT NOT NULL
                )
            """)

            # Seed default settings if not exists
            for key, default_val in DEFAULT_SETTINGS.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO settings (key, value)
                    VALUES (?, ?)
                """, (key, str(default_val)))

            # Seed global counter
            cursor.execute("""
                INSERT OR IGNORE INTO counters (name, count)
                VALUES ('total_watermarked', 0)
            """)

            conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                val = row["value"]
                # Convert numeric if applicable
                if val.isdigit():
                    return int(val)
                return val
            return default

    def set_setting(self, key: str, value: Any):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
            conn.commit()

    def get_all_settings(self) -> Dict[str, Any]:
        settings = dict(DEFAULT_SETTINGS)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            for row in cursor.fetchall():
                key = row["key"]
                val = row["value"]
                if val.isdigit():
                    settings[key] = int(val)
                else:
                    settings[key] = val
        return settings

    def reset_settings(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for key, default_val in DEFAULT_SETTINGS.items():
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (key, str(default_val)))
            conn.commit()

    def register_or_update_user(self, user_id: int, username: Optional[str], first_name: Optional[str]):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, joined_at, last_active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_active = excluded.last_active
            """, (user_id, username or "", first_name or "", now, now))
            conn.commit()

    def increment_processed(self, user_id: int):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET total_processed = total_processed + 1,
                    last_active = ?
                WHERE user_id = ?
            """, (now, user_id))

            cursor.execute("""
                UPDATE counters
                SET count = count + 1
                WHERE name = 'total_watermarked'
            """)
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

            cursor.execute("SELECT count FROM counters WHERE name = 'total_watermarked'")
            counter_row = cursor.fetchone()
            total_processed = counter_row["count"] if counter_row else 0

            return {
                "total_users": total_users,
                "total_processed": total_processed
            }

    def get_all_user_ids(self) -> List[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            rows = cursor.fetchall()
            return [row["user_id"] for row in rows]

    def set_user_state(self, user_id: int, state: Optional[str]):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if state is None:
                cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("""
                    INSERT INTO user_states (user_id, state, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        state = excluded.state,
                        updated_at = excluded.updated_at
                """, (user_id, state, now))
            conn.commit()

    def get_user_state(self, user_id: int) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state FROM user_states WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["state"] if row else None

    # User custom thumbnail methods
    def set_user_thumbnail(self, user_id: int, image_bytes: bytes):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_thumbnails (user_id, thumbnail_bytes, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    thumbnail_bytes = excluded.thumbnail_bytes,
                    updated_at = excluded.updated_at
            """, (user_id, image_bytes, now))
            conn.commit()

    def get_user_thumbnail(self, user_id: int) -> Optional[bytes]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT thumbnail_bytes FROM user_thumbnails WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["thumbnail_bytes"] if row else None

    def has_user_thumbnail(self, user_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM user_thumbnails WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def clear_user_thumbnail(self, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_thumbnails WHERE user_id = ?", (user_id,))
            conn.commit()

    # Pending video methods
    def set_pending_video(
        self,
        user_id: int,
        file_id: str,
        file_name: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[int] = None,
        file_size: Optional[int] = None,
        extracted_thumb: Optional[bytes] = None
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pending_videos (user_id, file_id, file_name, width, height, duration, file_size, extracted_thumb, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    file_id = excluded.file_id,
                    file_name = excluded.file_name,
                    width = excluded.width,
                    height = excluded.height,
                    duration = excluded.duration,
                    file_size = excluded.file_size,
                    extracted_thumb = excluded.extracted_thumb,
                    created_at = excluded.created_at
            """, (user_id, file_id, file_name or "video.mp4", width or 0, height or 0, duration or 0, file_size or 0, extracted_thumb, now))
            conn.commit()

    def get_pending_video(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_videos WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def clear_pending_video(self, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_videos WHERE user_id = ?", (user_id,))
            conn.commit()


# Global database instance
db = Database()
