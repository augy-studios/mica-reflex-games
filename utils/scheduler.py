import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import Mica

logger = logging.getLogger("mica.scheduler")

# Intervals (seconds) between automatic game triggers
GAME_INTERVALS = {
    "drop_zone":      (120, 600),
    "ghost_hunt":     (180, 900),
    "burst_round":    (300, 1200),
    "copycat":        (240, 720),
    "bait_and_hook":  (300, 900),
    "flag_blitz":     (300, 900),
    "blurred_vision": (600, 1800),
    "dont_touch_it":  (300, 900),
    "sniper_window":  (180, 720),
    "echo_chamber":   (300, 900),
    "freeze_tag":     (120, 600),
    "open_bounty":    (600, 3600),
}


class GameScheduler:
    def __init__(self, bot: "Mica"):
        self.bot = bot
        self._task: asyncio.Task = None

    def start(self):
        self._task = asyncio.create_task(self._loop())
        logger.info("Game scheduler started.")

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}", exc_info=True)
            await asyncio.sleep(10)

    async def _tick(self):
        db = self.bot.db
        due = db.get_due_events()
        for event in due:
            db.mark_event_fired(event["id"])
            guild_id = event["guild_id"]
            game_key = event["game_key"]
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            cog = self._find_cog(game_key)
            if cog and hasattr(cog, "trigger_game"):
                channel = self._resolve_channel(guild_id, game_key, guild)
                if channel:
                    task = asyncio.create_task(cog.trigger_game(channel, game_key))
                    task.add_done_callback(
                        lambda t, gk=game_key, gid=guild_id: (
                            logger.error(
                                f"Error running {gk} in guild {gid}: {t.exception()}",
                                exc_info=t.exception(),
                            )
                            if not t.cancelled() and t.exception()
                            else None
                        )
                    )
                    logger.info(f"Triggered {game_key} in guild {guild_id}")
            # Schedule next occurrence
            self._schedule_next(guild_id, game_key)
        db.prune_old_events()
        # Ensure every enabled game has a pending scheduled event
        self._ensure_scheduled()

    def _find_cog(self, game_key: str):
        cog_map = {
            "drop_zone": "CoreGames",
            "ghost_hunt": "CoreGames",
            "burst_round": "CoreGames",
            "copycat": "CoreGames",
            "bait_and_hook": "KnowledgeGames",
            "open_bounty": "KnowledgeGames",
            "flag_blitz": "KnowledgeGames",
            "blurred_vision": "KnowledgeGames",
            "dont_touch_it": "ReflexGames",
            "sniper_window": "ReflexGames",
            "echo_chamber": "ReflexGames",
            "freeze_tag": "ReflexGames",
        }
        cog_name = cog_map.get(game_key)
        return self.bot.cogs.get(cog_name)

    def _resolve_channel(self, guild_id: int, game_key: str, guild):
        setting = self.bot.db.get_game_setting(guild_id, game_key)
        if setting and setting["channel_id"]:
            ch = guild.get_channel(setting["channel_id"])
            if ch:
                return ch
        return None

    def _schedule_next(self, guild_id: int, game_key: str):
        if game_key not in GAME_INTERVALS:
            return
        lo, hi = GAME_INTERVALS[game_key]
        delay = random.randint(lo, hi)
        fire_at = datetime.utcnow() + timedelta(seconds=delay)
        self.bot.db.schedule_event(guild_id, game_key, fire_at)

    def _ensure_scheduled(self):
        """Make sure every enabled game per guild has at least one future scheduled event."""
        db = self.bot.db
        existing = db.conn.execute(
            "SELECT guild_id, game_key FROM scheduled_events WHERE fired=0"
        ).fetchall()
        scheduled_set = {(r["guild_id"], r["game_key"]) for r in existing}

        for guild in self.bot.guilds:
            enabled = db.get_enabled_games(guild.id)
            for setting in enabled:
                gk = setting["game_key"]
                if gk not in GAME_INTERVALS:
                    continue
                if (guild.id, gk) not in scheduled_set:
                    self._schedule_next(guild.id, gk)
