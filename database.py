import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mica.database")

DB_PATH = "mica.db"

GAME_KEYS = [
    "drop_zone",
    "ghost_hunt",
    "burst_round",
    "copycat",
    "bait_and_hook",
    "open_bounty",
    "flag_blitz",
    "blurred_vision",
    "dont_touch_it",
    "sniper_window",
    "echo_chamber",
    "freeze_tag",
    "quickdraw",
    "copycat_duel",
    "trivia_clash",
]


class Database:
    def __init__(self):
        self._local = threading.local()

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    @property
    def conn(self):
        return self._get_conn()

    def init(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id    INTEGER PRIMARY KEY,
                registered_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS game_settings (
                guild_id    INTEGER NOT NULL,
                game_key    TEXT NOT NULL,
                enabled     INTEGER NOT NULL DEFAULT 1,
                channel_id  INTEGER,
                PRIMARY KEY (guild_id, game_key),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scores (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                game_key    TEXT NOT NULL,
                points      INTEGER NOT NULL DEFAULT 0,
                week_points INTEGER NOT NULL DEFAULT 0,
                week_start  TEXT NOT NULL DEFAULT (strftime('%Y-%W', 'now')),
                PRIMARY KEY (guild_id, user_id, game_key),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS streaks (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                game_key    TEXT NOT NULL,
                current     INTEGER NOT NULL DEFAULT 0,
                best        INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, game_key),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS penalties (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                total_lost  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS duel_records (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                wins        INTEGER NOT NULL DEFAULT 0,
                losses      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS open_bounties (
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER,
                question    TEXT NOT NULL,
                answer      TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS active_games (
                guild_id    INTEGER NOT NULL,
                game_key    TEXT NOT NULL,
                channel_id  INTEGER NOT NULL,
                state       TEXT,
                started_at  TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (guild_id, game_key),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scheduled_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                game_key    TEXT NOT NULL,
                fire_at     TEXT NOT NULL,
                fired       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS flag_blitz_stats (
                guild_id        INTEGER NOT NULL,
                total_correct   INTEGER NOT NULL DEFAULT 0,
                total_attempts  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS copycat_lockouts (
                guild_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                locked_until TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        c.commit()
        logger.info("Database initialised.")

    # ── Guild ──────────────────────────────────────────────────────────────

    def register_guild(self, guild_id: int):
        c = self.conn
        c.execute("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,))
        for key in GAME_KEYS:
            c.execute(
                "INSERT OR IGNORE INTO game_settings (guild_id, game_key) VALUES (?, ?)",
                (guild_id, key)
            )
        c.commit()

    # ── Game settings ──────────────────────────────────────────────────────

    def get_game_setting(self, guild_id: int, game_key: str) -> Optional[sqlite3.Row]:
        self.register_guild(guild_id)
        return self.conn.execute(
            "SELECT * FROM game_settings WHERE guild_id=? AND game_key=?",
            (guild_id, game_key)
        ).fetchone()

    def set_game_enabled(self, guild_id: int, game_key: str, enabled: bool):
        self.register_guild(guild_id)
        self.conn.execute(
            "UPDATE game_settings SET enabled=? WHERE guild_id=? AND game_key=?",
            (1 if enabled else 0, guild_id, game_key)
        )
        self.conn.commit()

    def set_game_channel(self, guild_id: int, game_key: str, channel_id: Optional[int]):
        self.register_guild(guild_id)
        self.conn.execute(
            "UPDATE game_settings SET channel_id=? WHERE guild_id=? AND game_key=?",
            (channel_id, guild_id, game_key)
        )
        self.conn.commit()

    def get_all_game_settings(self, guild_id: int):
        self.register_guild(guild_id)
        return self.conn.execute(
            "SELECT * FROM game_settings WHERE guild_id=? ORDER BY game_key",
            (guild_id,)
        ).fetchall()

    def get_enabled_games(self, guild_id: int):
        self.register_guild(guild_id)
        return self.conn.execute(
            "SELECT * FROM game_settings WHERE guild_id=? AND enabled=1",
            (guild_id,)
        ).fetchall()

    # ── Scoring ────────────────────────────────────────────────────────────

    def _ensure_score_row(self, guild_id: int, user_id: int, game_key: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO scores (guild_id, user_id, game_key) VALUES (?, ?, ?)",
            (guild_id, user_id, game_key)
        )

    def add_points(self, guild_id: int, user_id: int, game_key: str, points: int):
        current_week = datetime.utcnow().strftime("%Y-%W")
        self._ensure_score_row(guild_id, user_id, game_key)
        # Reset weekly if stale
        self.conn.execute("""
            UPDATE scores SET week_points=0, week_start=?
            WHERE guild_id=? AND user_id=? AND game_key=? AND week_start != ?
        """, (current_week, guild_id, user_id, game_key, current_week))
        self.conn.execute("""
            UPDATE scores
            SET points = points + ?,
                week_points = week_points + ?
            WHERE guild_id=? AND user_id=? AND game_key=?
        """, (points, points, guild_id, user_id, game_key))
        self.conn.commit()

    def deduct_points(self, guild_id: int, user_id: int, game_key: str, points: int):
        """Deduct points (floor at 0) and track in penalties."""
        self._ensure_score_row(guild_id, user_id, game_key)
        self.conn.execute("""
            UPDATE scores
            SET points = MAX(0, points - ?),
                week_points = MAX(0, week_points - ?)
            WHERE guild_id=? AND user_id=? AND game_key=?
        """, (points, points, guild_id, user_id, game_key))
        self.conn.execute("""
            INSERT INTO penalties (guild_id, user_id, total_lost) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET total_lost = total_lost + ?
        """, (guild_id, user_id, points, points))
        self.conn.commit()

    def get_score(self, guild_id: int, user_id: int, game_key: str) -> int:
        self._ensure_score_row(guild_id, user_id, game_key)
        row = self.conn.execute(
            "SELECT points FROM scores WHERE guild_id=? AND user_id=? AND game_key=?",
            (guild_id, user_id, game_key)
        ).fetchone()
        return row["points"] if row else 0

    def get_alltime_leaderboard(self, guild_id: int, limit: int = 10):
        return self.conn.execute("""
            SELECT user_id, SUM(points) as total
            FROM scores WHERE guild_id=?
            GROUP BY user_id ORDER BY total DESC LIMIT ?
        """, (guild_id, limit)).fetchall()

    def get_weekly_leaderboard(self, guild_id: int, limit: int = 10):
        current_week = datetime.utcnow().strftime("%Y-%W")
        return self.conn.execute("""
            SELECT user_id, SUM(week_points) as total
            FROM scores WHERE guild_id=? AND week_start=?
            GROUP BY user_id ORDER BY total DESC LIMIT ?
        """, (guild_id, current_week, limit)).fetchall()

    def get_cursed_crown(self, guild_id: int, limit: int = 10):
        return self.conn.execute("""
            SELECT user_id, total_lost FROM penalties
            WHERE guild_id=? ORDER BY total_lost DESC LIMIT ?
        """, (guild_id, limit)).fetchall()

    # ── Streaks ────────────────────────────────────────────────────────────

    def increment_streak(self, guild_id: int, user_id: int, game_key: str):
        self.conn.execute("""
            INSERT INTO streaks (guild_id, user_id, game_key, current, best) VALUES (?, ?, ?, 1, 1)
            ON CONFLICT(guild_id, user_id, game_key) DO UPDATE SET
                current = current + 1,
                best = MAX(best, current + 1)
        """, (guild_id, user_id, game_key))
        self.conn.commit()

    def reset_streak(self, guild_id: int, user_id: int, game_key: str):
        self.conn.execute("""
            INSERT INTO streaks (guild_id, user_id, game_key, current, best) VALUES (?, ?, ?, 0, 0)
            ON CONFLICT(guild_id, user_id, game_key) DO UPDATE SET current = 0
        """, (guild_id, user_id, game_key))
        self.conn.commit()

    def get_streak(self, guild_id: int, user_id: int, game_key: str) -> dict:
        row = self.conn.execute(
            "SELECT current, best FROM streaks WHERE guild_id=? AND user_id=? AND game_key=?",
            (guild_id, user_id, game_key)
        ).fetchone()
        return {"current": row["current"], "best": row["best"]} if row else {"current": 0, "best": 0}

    def get_hot_streaks(self, guild_id: int, limit: int = 10):
        return self.conn.execute("""
            SELECT user_id, MAX(current) as hot_streak
            FROM streaks WHERE guild_id=?
            GROUP BY user_id ORDER BY hot_streak DESC LIMIT ?
        """, (guild_id, limit)).fetchall()

    # ── Duel records ───────────────────────────────────────────────────────

    def record_duel_win(self, guild_id: int, user_id: int):
        self.conn.execute("""
            INSERT INTO duel_records (guild_id, user_id, wins, losses) VALUES (?, ?, 1, 0)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET wins = wins + 1
        """, (guild_id, user_id))
        self.conn.commit()

    def record_duel_loss(self, guild_id: int, user_id: int):
        self.conn.execute("""
            INSERT INTO duel_records (guild_id, user_id, wins, losses) VALUES (?, ?, 0, 1)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET losses = losses + 1
        """, (guild_id, user_id))
        self.conn.commit()

    def get_duel_leaderboard(self, guild_id: int, limit: int = 10):
        return self.conn.execute("""
            SELECT user_id, wins, losses,
                   CAST(wins AS FLOAT) / MAX(1, wins + losses) AS ratio
            FROM duel_records WHERE guild_id=?
            ORDER BY wins DESC, ratio DESC LIMIT ?
        """, (guild_id, limit)).fetchall()

    # ── Active games ───────────────────────────────────────────────────────

    def set_active_game(self, guild_id: int, game_key: str, channel_id: int, state: str = ""):
        self.conn.execute("""
            INSERT INTO active_games (guild_id, game_key, channel_id, state)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, game_key) DO UPDATE SET
                channel_id=excluded.channel_id,
                state=excluded.state,
                started_at=datetime('now')
        """, (guild_id, game_key, channel_id, state))
        self.conn.commit()

    def clear_active_game(self, guild_id: int, game_key: str):
        self.conn.execute(
            "DELETE FROM active_games WHERE guild_id=? AND game_key=?",
            (guild_id, game_key)
        )
        self.conn.commit()

    def get_active_game(self, guild_id: int, game_key: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM active_games WHERE guild_id=? AND game_key=?",
            (guild_id, game_key)
        ).fetchone()

    def is_game_active(self, guild_id: int, game_key: str) -> bool:
        return self.get_active_game(guild_id, game_key) is not None

    # ── Open Bounty ────────────────────────────────────────────────────────

    def set_bounty(self, guild_id: int, channel_id: int, question: str, answer: str, message_id: int = None):
        self.conn.execute("""
            INSERT INTO open_bounties (guild_id, channel_id, question, answer, message_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id=excluded.channel_id,
                question=excluded.question,
                answer=excluded.answer,
                message_id=excluded.message_id,
                created_at=datetime('now')
        """, (guild_id, channel_id, question, answer, message_id))
        self.conn.commit()

    def get_bounty(self, guild_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM open_bounties WHERE guild_id=?", (guild_id,)
        ).fetchone()

    def clear_bounty(self, guild_id: int):
        self.conn.execute("DELETE FROM open_bounties WHERE guild_id=?", (guild_id,))
        self.conn.commit()

    def update_bounty_message_id(self, guild_id: int, message_id: int):
        self.conn.execute(
            "UPDATE open_bounties SET message_id=? WHERE guild_id=?",
            (message_id, guild_id)
        )
        self.conn.commit()

    # ── Flag Blitz stats ───────────────────────────────────────────────────

    def record_flag_attempt(self, guild_id: int, correct: bool):
        self.conn.execute("""
            INSERT INTO flag_blitz_stats (guild_id, total_correct, total_attempts)
            VALUES (?, ?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET
                total_correct = total_correct + ?,
                total_attempts = total_attempts + 1
        """, (guild_id, 1 if correct else 0, 1 if correct else 0))
        self.conn.commit()

    def get_flag_accuracy(self, guild_id: int) -> float:
        row = self.conn.execute(
            "SELECT total_correct, total_attempts FROM flag_blitz_stats WHERE guild_id=?",
            (guild_id,)
        ).fetchone()
        if not row or row["total_attempts"] == 0:
            return 0.0
        return row["total_correct"] / row["total_attempts"]

    # ── Copycat lockout ────────────────────────────────────────────────────

    def set_lockout(self, guild_id: int, user_id: int, seconds: int = 30):
        until = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        self.conn.execute("""
            INSERT INTO copycat_lockouts (guild_id, user_id, locked_until) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET locked_until=excluded.locked_until
        """, (guild_id, user_id, until))
        self.conn.commit()

    def is_locked_out(self, guild_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT locked_until FROM copycat_lockouts WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ).fetchone()
        if not row:
            return False
        return datetime.fromisoformat(row["locked_until"]) > datetime.utcnow()

    # ── Scheduled events ───────────────────────────────────────────────────

    def schedule_event(self, guild_id: int, game_key: str, fire_at: datetime):
        self.conn.execute(
            "INSERT INTO scheduled_events (guild_id, game_key, fire_at) VALUES (?, ?, ?)",
            (guild_id, game_key, fire_at.isoformat())
        )
        self.conn.commit()

    def get_due_events(self):
        now = datetime.utcnow().isoformat()
        return self.conn.execute(
            "SELECT * FROM scheduled_events WHERE fire_at <= ? AND fired=0",
            (now,)
        ).fetchall()

    def mark_event_fired(self, event_id: int):
        self.conn.execute(
            "UPDATE scheduled_events SET fired=1 WHERE id=?", (event_id,)
        )
        self.conn.commit()

    def prune_old_events(self):
        self.conn.execute("DELETE FROM scheduled_events WHERE fired=1")
        self.conn.commit()
