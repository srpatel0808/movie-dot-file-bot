"""
SQLite persistent database for MOVIE DOT Telegram Bot.
Handles movie records, multi-quality file IDs, user statistics,
dynamic channel configuration, and admin state management.
"""

import sqlite3
import datetime
from typing import Dict, Any, List, Optional
from config import DB_PATH, CHANNEL_ID


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Settings table (key-value store for dynamic configs like force_sub_channel)
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
                    total_requested INTEGER DEFAULT 0,
                    joined_at TEXT NOT NULL,
                    last_active TEXT NOT NULL
                )
            """)

            # Ensure total_requested column exists if migrating from older schema
            cursor.execute("PRAGMA table_info(users)")
            user_cols = [row["name"] for row in cursor.fetchall()]
            if "total_requested" not in user_cols:
                try:
                    cursor.execute("ALTER TABLE users ADD COLUMN total_requested INTEGER DEFAULT 0;")
                except Exception:
                    pass

            # Global counters
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)

            # User admin state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT,
                    updated_at TEXT NOT NULL
                )
            """)

            # Master Movies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    movie_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    year INTEGER,
                    poster_file_id TEXT,
                    description TEXT,
                    channel_id INTEGER,
                    channel_message_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Movie files table (links multiple file qualities to one movie ID)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS movie_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT UNIQUE,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    quality TEXT NOT NULL,
                    mime_type TEXT,
                    is_video INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movie_files_movie_id ON movie_files(movie_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title);")

            # Clean up deprecated legacy tables safely
            cursor.execute("DROP TABLE IF EXISTS user_thumbnails;")
            cursor.execute("DROP TABLE IF EXISTS pending_videos;")

            # Seed global counter for file deliveries
            cursor.execute("""
                INSERT OR IGNORE INTO counters (name, count)
                VALUES ('total_delivered', 0)
            """)

            # Seed default channel from config if set
            if CHANNEL_ID:
                cursor.execute("""
                    INSERT OR IGNORE INTO settings (key, value)
                    VALUES ('force_sub_channel', ?)
                """, (CHANNEL_ID,))

            conn.commit()

    # ==================== SETTINGS & FORCE JOIN CONFIG ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                val = row["value"]
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

    def get_force_sub_channel(self) -> str:
        """Returns the configured channel for mandatory subscription."""
        val = self.get_setting("force_sub_channel")
        if val:
            return str(val).strip()
        return (CHANNEL_ID or "").strip()

    def set_force_sub_channel(self, channel: str):
        """Updates the mandatory subscription channel."""
        clean = channel.strip()
        self.set_setting("force_sub_channel", clean)

    # ==================== USERS & STATS ====================

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

    def increment_delivered(self, user_id: int):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET total_requested = total_requested + 1,
                    last_active = ?
                WHERE user_id = ?
            """, (now, user_id))

            cursor.execute("""
                UPDATE counters
                SET count = count + 1
                WHERE name = 'total_delivered'
            """)
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

            cursor.execute("SELECT count FROM counters WHERE name = 'total_delivered'")
            counter_row = cursor.fetchone()
            total_delivered = counter_row["count"] if counter_row else 0

            cursor.execute("SELECT COUNT(*) as movie_count FROM movies")
            total_movies = cursor.fetchone()["movie_count"]

            cursor.execute("SELECT COUNT(*) as file_count, COALESCE(SUM(file_size), 0) as total_size FROM movie_files")
            file_stats = cursor.fetchone()

            return {
                "total_users": total_users,
                "total_delivered": total_delivered,
                "total_movies": total_movies,
                "total_files": file_stats["file_count"],
                "total_size_bytes": file_stats["total_size"],
                "force_sub_channel": self.get_force_sub_channel()
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

    # ==================== MOVIE & FILE MANAGEMENT ====================

    def add_or_update_movie(
        self,
        movie_id: str,
        title: str,
        year: Optional[int] = None,
        poster_file_id: Optional[str] = None,
        description: Optional[str] = None,
        channel_id: Optional[int] = None,
        channel_message_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Creates or updates a master movie record."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO movies (movie_id, title, year, poster_file_id, description, channel_id, channel_message_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(movie_id) DO UPDATE SET
                    title = excluded.title,
                    year = coalesce(excluded.year, movies.year),
                    poster_file_id = coalesce(excluded.poster_file_id, movies.poster_file_id),
                    description = coalesce(excluded.description, movies.description),
                    channel_id = coalesce(excluded.channel_id, movies.channel_id),
                    channel_message_id = coalesce(excluded.channel_message_id, movies.channel_message_id),
                    updated_at = excluded.updated_at
            """, (movie_id, title, year, poster_file_id, description, channel_id, channel_message_id, now, now))
            conn.commit()
            return self.get_movie(movie_id)

    def get_movie(self, movie_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves movie record by movie_id (exact or case-insensitive)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE movie_id = ? COLLATE NOCASE", (movie_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def find_movie_by_title_or_year(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Finds existing movie matching title and optional year."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if year:
                cursor.execute("SELECT * FROM movies WHERE title = ? AND year = ? COLLATE NOCASE", (title, year))
            else:
                cursor.execute("SELECT * FROM movies WHERE title = ? COLLATE NOCASE", (title,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_movies(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves list of all movies with file count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, COUNT(f.id) as file_count
                FROM movies m
                LEFT JOIN movie_files f ON m.movie_id = f.movie_id
                GROUP BY m.movie_id
                ORDER BY m.updated_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [dict(r) for r in cursor.fetchall()]

    def delete_movie(self, movie_id: str) -> bool:
        """Deletes a movie and all associated files (cascading)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM movies WHERE movie_id = ?", (movie_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_movie_file(
        self,
        movie_id: str,
        file_id: str,
        file_unique_id: str,
        file_name: str,
        file_size: int,
        quality: str,
        mime_type: Optional[str] = None,
        is_video: bool = True
    ) -> Dict[str, Any]:
        """
        Stores a Telegram file_id linked to a movie_id with detected quality.
        Prevents duplicate entries via unique file_unique_id or replaces older file for the same quality.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # MKV files are treated as documents in Telegram
        if file_name and file_name.lower().endswith(".mkv"):
            is_video = False

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Check if exact file_unique_id already registered
            cursor.execute("SELECT * FROM movie_files WHERE file_unique_id = ?", (file_unique_id,))
            existing_unique = cursor.fetchone()
            if existing_unique:
                cursor.execute("""
                    UPDATE movie_files
                    SET movie_id = ?, file_id = ?, file_name = ?, file_size = ?, quality = ?, mime_type = ?, is_video = ?
                    WHERE file_unique_id = ?
                """, (movie_id, file_id, file_name, file_size, quality, mime_type, 1 if is_video else 0, file_unique_id))
                conn.commit()
                return {"status": "updated", "id": existing_unique["id"], "action": "updated_unique"}

            # 2. Check if a file already exists for this movie and quality
            cursor.execute("SELECT * FROM movie_files WHERE movie_id = ? AND quality = ?", (movie_id, quality))
            existing_quality = cursor.fetchone()
            if existing_quality:
                cursor.execute("""
                    UPDATE movie_files
                    SET file_id = ?, file_unique_id = ?, file_name = ?, file_size = ?, mime_type = ?, is_video = ?, created_at = ?
                    WHERE id = ?
                """, (file_id, file_unique_id, file_name, file_size, mime_type, 1 if is_video else 0, now, existing_quality["id"]))
                conn.commit()
                return {"status": "replaced", "id": existing_quality["id"], "action": "replaced_quality"}

            # 3. Insert new file record
            cursor.execute("""
                INSERT INTO movie_files (movie_id, file_id, file_unique_id, file_name, file_size, quality, mime_type, is_video, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (movie_id, file_id, file_unique_id, file_name, file_size, quality, mime_type, 1 if is_video else 0, now))
            new_id = cursor.lastrowid
            conn.commit()
            return {"status": "inserted", "id": new_id, "action": "inserted"}

    def get_movie_files(self, movie_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all file versions for a movie sorted by quality resolution:
        480p -> 720p -> 1080p -> 2160p / 4K.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM movie_files
                WHERE movie_id = ?
                ORDER BY
                    CASE quality
                        WHEN '480p' THEN 1
                        WHEN '720p' THEN 2
                        WHEN '1080p' THEN 3
                        WHEN '2160p / 4K' THEN 4
                        WHEN '4K' THEN 4
                        ELSE 5
                    END ASC,
                    file_size ASC
            """, (movie_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_movie_file_by_quality(self, movie_id: str, quality: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific quality file for a movie."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM movie_files
                WHERE movie_id = ? AND quality = ? COLLATE NOCASE
                LIMIT 1
            """, (movie_id, quality))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_movie_file_by_id(self, file_id_int: int) -> Optional[Dict[str, Any]]:
        """Retrieves a specific file record by its database row ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movie_files WHERE id = ?", (file_id_int,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def delete_movie_file(self, file_id_int: int) -> bool:
        """Deletes a specific movie file by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM movie_files WHERE id = ?", (file_id_int,))
            conn.commit()
            return cursor.rowcount > 0

    def get_movie_stats(self) -> Dict[str, Any]:
        """Returns summary statistics for indexed movies and files."""
        return self.get_stats()


# Global database instance
db = Database()
