"""关键词触发记录持久化存储"""
import sqlite3
import threading
from pathlib import Path


class KeywordTriggerStore:
    """SQLite-backed store for keyword trigger records."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keyword_triggers (
                    user_id TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    triggered_at REAL NOT NULL,
                    PRIMARY KEY (user_id, keyword)
                )
                """
            )
            conn.commit()

    def has_triggered(self, user_id: str, keyword: str) -> bool:
        """检查用户是否已触发过该关键词"""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM keyword_triggers WHERE user_id = ? AND keyword = ?",
                (user_id, keyword),
            )
            return cursor.fetchone() is not None

    def mark_triggered(self, user_id: str, keyword: str, triggered_at: float) -> None:
        """标记关键词已被触发"""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO keyword_triggers (user_id, keyword, triggered_at)
                VALUES (?, ?, ?)
                """,
                (user_id, keyword, triggered_at),
            )
            conn.commit()

    def clear_user_keywords(self, user_id: str) -> int:
        """清除某用户的所有关键词触发记录"""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM keyword_triggers WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount

    def clear_all(self) -> int:
        """清除所有关键词触发记录"""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM keyword_triggers")
            conn.commit()
            return cursor.rowcount
