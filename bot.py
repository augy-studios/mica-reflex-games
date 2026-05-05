import discord
from discord.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv
from database import Database
from utils.scheduler import GameScheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("mica.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mica")

COGS = [
    "cogs.admin",
    "cogs.leaderboard",
    "cogs.core_games",
    "cogs.knowledge_games",
    "cogs.reflex_games",
    "cogs.duel_games",
    "cogs.chaos",
    "cogs.events",
    "cogs.help",
]


class Mica(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()
        self.scheduler = GameScheduler(self)

    async def setup_hook(self):
        self.db.init()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
        synced = await self.tree.sync()
        self._synced_commands = {cmd.name: cmd for cmd in synced}
        logger.info("Slash commands synced globally.")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for your reflexes 👀"
            )
        )
        self.scheduler.start()

    async def on_guild_join(self, guild: discord.Guild):
        self.db.register_guild(guild.id)
        logger.info(f"Joined guild: {guild.name} ({guild.id})")

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"Left guild: {guild.name} ({guild.id})")


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not set in environment.")
    bot = Mica()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
