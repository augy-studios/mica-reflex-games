import discord
from discord.ext import commands
import logging

logger = logging.getLogger("mica.events")


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        # Route Open Bounty checks
        knowledge_cog = self.bot.cogs.get("KnowledgeGames")
        if knowledge_cog:
            await knowledge_cog.check_open_bounty(message)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.bot.db.register_guild(guild.id)
        logger.info(f"Registered new guild: {guild.name} ({guild.id})")

        # Send welcome message only to the guild's designated system channel
        channel = guild.system_channel
        if channel and not channel.permissions_for(guild.me).send_messages:
            channel = None
        if channel:
            embed = discord.Embed(
                title="👋 Hey there! I'm Mica.",
                description=(
                    "I bring **reflex games** to your server — drop zones, ghost hunts, trivia, duels, and more.\n\n"
                    "**Getting started:**\n"
                    "• Use `/games status` to see all available games\n"
                    "• Use `/games enable` and `/games disable` to toggle games\n"
                    "• Use `/games setchannel` to set which channel each game plays in\n"
                    "• Use `/lb alltime` to check the leaderboard\n\n"
                    "Games trigger automatically at random intervals. Challenge friends with `/quickdraw`, "
                    "`/copycatduel`, or `/triviaclash`!\n\n"
                    "Watch out for **Chaos Modifiers** — they can flip everything upside down. 🎲"
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text="All games are disabled by default — enable them with /games enable!")
            await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Events(bot))
