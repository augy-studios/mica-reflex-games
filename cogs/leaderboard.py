import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger("mica.leaderboard")

MEDALS = ["🥇", "🥈", "🥉"]


def medal(i: int) -> str:
    return MEDALS[i] if i < len(MEDALS) else f"**{i+1}.**"


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    lb = app_commands.Group(name="lb", description="View leaderboards.")

    @lb.command(name="alltime", description="All-time points leaderboard.")
    async def lb_alltime(self, interaction: discord.Interaction):
        rows = self.bot.db.get_alltime_leaderboard(interaction.guild_id)
        embed = await self._build_embed(
            interaction, "🏆 All-Time Leaderboard", rows, "total"
        )
        await interaction.response.send_message(embed=embed)

    @lb.command(name="weekly", description="Weekly points leaderboard (resets every 7 days).")
    async def lb_weekly(self, interaction: discord.Interaction):
        rows = self.bot.db.get_weekly_leaderboard(interaction.guild_id)
        embed = await self._build_embed(
            interaction, "📅 Weekly Leaderboard", rows, "total"
        )
        await interaction.response.send_message(embed=embed)

    @lb.command(name="duels", description="Duel win/loss leaderboard.")
    async def lb_duels(self, interaction: discord.Interaction):
        rows = self.bot.db.get_duel_leaderboard(interaction.guild_id)
        if not rows:
            return await interaction.response.send_message("No duel records yet!", ephemeral=True)
        lines = []
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row["user_id"])
            name = user.display_name if user else f"<@{row['user_id']}>"
            ratio = f"{row['ratio']:.0%}"
            lines.append(f"{medal(i)} **{name}** — {row['wins']}W / {row['losses']}L ({ratio})")
        embed = discord.Embed(
            title="⚔️ Duel Leaderboard",
            description="\n".join(lines),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @lb.command(name="streaks", description="Current hot streaks.")
    async def lb_streaks(self, interaction: discord.Interaction):
        rows = self.bot.db.get_hot_streaks(interaction.guild_id)
        if not rows:
            return await interaction.response.send_message("No streaks yet!", ephemeral=True)
        lines = []
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row["user_id"])
            name = user.display_name if user else f"<@{row['user_id']}>"
            lines.append(f"{medal(i)} **{name}** — 🔥 {row['hot_streak']} streak")
        embed = discord.Embed(
            title="🔥 Hot Streaks",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @lb.command(name="cursed", description="Cursed Crown — most points lost to penalties.")
    async def lb_cursed(self, interaction: discord.Interaction):
        rows = self.bot.db.get_cursed_crown(interaction.guild_id)
        if not rows:
            return await interaction.response.send_message("No penalties recorded yet!", ephemeral=True)
        lines = []
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row["user_id"])
            name = user.display_name if user else f"<@{row['user_id']}>"
            lines.append(f"{medal(i)} **{name}** — 💀 {row['total_lost']} pts lost")
        embed = discord.Embed(
            title="👑 Cursed Crown — Hall of Shame",
            description="\n".join(lines),
            color=discord.Color.dark_purple()
        )
        embed.set_footer(text="Wear it with pride.")
        await interaction.response.send_message(embed=embed)

    @lb.command(name="score", description="Check your own score.")
    async def lb_score(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        alltime_rows = self.bot.db.get_alltime_leaderboard(guild_id, limit=100)
        weekly_rows  = self.bot.db.get_weekly_leaderboard(guild_id, limit=100)
        alltime_total = next((r["total"] for r in alltime_rows if r["user_id"] == user_id), 0)
        weekly_total  = next((r["total"] for r in weekly_rows  if r["user_id"] == user_id), 0)
        alltime_rank  = next((i+1 for i, r in enumerate(alltime_rows) if r["user_id"] == user_id), None)
        weekly_rank   = next((i+1 for i, r in enumerate(weekly_rows)  if r["user_id"] == user_id), None)
        streak_rows   = self.bot.db.get_hot_streaks(guild_id, limit=100)
        hot_streak    = next((r["hot_streak"] for r in streak_rows if r["user_id"] == user_id), 0)
        penalty_rows  = self.bot.db.get_cursed_crown(guild_id, limit=100)
        total_lost    = next((r["total_lost"] for r in penalty_rows if r["user_id"] == user_id), 0)
        duel_rows     = self.bot.db.get_duel_leaderboard(guild_id, limit=100)
        duel_row      = next((r for r in duel_rows if r["user_id"] == user_id), None)

        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name}'s Stats",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🏆 All-Time",
            value=f"{alltime_total} pts" + (f" (Rank #{alltime_rank})" if alltime_rank else ""),
            inline=True
        )
        embed.add_field(
            name="📅 This Week",
            value=f"{weekly_total} pts" + (f" (Rank #{weekly_rank})" if weekly_rank else ""),
            inline=True
        )
        embed.add_field(name="🔥 Hot Streak", value=str(hot_streak), inline=True)
        embed.add_field(name="💀 Points Lost", value=str(total_lost), inline=True)
        if duel_row:
            embed.add_field(
                name="⚔️ Duels",
                value=f"{duel_row['wins']}W / {duel_row['losses']}L",
                inline=True
            )
        await interaction.response.send_message(embed=embed)

    async def _build_embed(self, interaction, title: str, rows, key: str) -> discord.Embed:
        if not rows:
            return discord.Embed(
                title=title,
                description="No scores yet — be the first!",
                color=discord.Color.blurple()
            )
        lines = []
        for i, row in enumerate(rows):
            user = interaction.guild.get_member(row["user_id"])
            name = user.display_name if user else f"<@{row['user_id']}>"
            lines.append(f"{medal(i)} **{name}** — {row[key]} pts")
        return discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.gold()
        )


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
