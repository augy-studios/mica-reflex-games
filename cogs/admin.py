import discord
from discord import app_commands
from discord.ext import commands
from database import GAME_KEYS
import logging

logger = logging.getLogger("mica.admin")

GAME_DISPLAY = {
    "drop_zone":      "Drop Zone",
    "ghost_hunt":     "Ghost Hunt",
    "burst_round":    "Burst Round",
    "copycat":        "Copycat",
    "bait_and_hook":  "Bait and Hook",
    "open_bounty":    "Open Bounty",
    "flag_blitz":     "Flag Blitz",
    "blurred_vision": "Blurred Vision",
    "dont_touch_it":  "Don't Touch It",
    "sniper_window":  "Sniper Window",
    "echo_chamber":   "Echo Chamber",
    "freeze_tag":     "Freeze Tag",
    "quickdraw":      "Quickdraw",
    "copycat_duel":   "Copycat Duel",
    "trivia_clash":   "Trivia Clash",
}

GAME_CHOICES = [
    app_commands.Choice(name=v, value=k)
    for k, v in GAME_DISPLAY.items()
]


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_channels

    # ── /games config ──────────────────────────────────────────────────────

    games = app_commands.Group(name="games", description="Manage reflex games for this server.")

    @games.command(name="enable", description="Enable a game in this server.")
    @app_commands.describe(game="The game to enable.")
    @app_commands.choices(game=GAME_CHOICES)
    async def games_enable(self, interaction: discord.Interaction, game: app_commands.Choice[str]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        self.bot.db.set_game_enabled(interaction.guild_id, game.value, True)
        await interaction.response.send_message(
            f"✅ **{game.name}** has been **enabled** in this server.",
            ephemeral=True
        )

    @games.command(name="disable", description="Disable a game in this server.")
    @app_commands.describe(game="The game to disable.")
    @app_commands.choices(game=GAME_CHOICES)
    async def games_disable(self, interaction: discord.Interaction, game: app_commands.Choice[str]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        self.bot.db.set_game_enabled(interaction.guild_id, game.value, False)
        await interaction.response.send_message(
            f"🚫 **{game.name}** has been **disabled** in this server.",
            ephemeral=True
        )

    @games.command(name="setchannel", description="Set which channel a game triggers in.")
    @app_commands.describe(game="The game to configure.", channel="The channel to use.")
    @app_commands.choices(game=GAME_CHOICES)
    async def games_setchannel(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
        channel: discord.TextChannel
    ):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        self.bot.db.set_game_channel(interaction.guild_id, game.value, channel.id)
        await interaction.response.send_message(
            f"📢 **{game.name}** will now trigger in {channel.mention}.",
            ephemeral=True
        )

    @games.command(name="clearchannel", description="Remove the custom channel for a game (uses default).")
    @app_commands.describe(game="The game to clear the channel for.")
    @app_commands.choices(game=GAME_CHOICES)
    async def games_clearchannel(self, interaction: discord.Interaction, game: app_commands.Choice[str]):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        self.bot.db.set_game_channel(interaction.guild_id, game.value, None)
        await interaction.response.send_message(
            f"🗑️ Custom channel for **{game.name}** has been cleared.",
            ephemeral=True
        )

    @games.command(name="status", description="View all games and their status for this server.")
    async def games_status(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        settings = self.bot.db.get_all_game_settings(interaction.guild_id)
        lines = []
        for s in settings:
            gk = s["game_key"]
            name = GAME_DISPLAY.get(gk, gk)
            status = "✅" if s["enabled"] else "🚫"
            ch = f" → <#{s['channel_id']}>" if s["channel_id"] else ""
            lines.append(f"{status} **{name}**{ch}")
        embed = discord.Embed(
            title="🎮 Game Status",
            description="\n".join(lines) or "No games configured.",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @games.command(name="enableall", description="Enable all games in this server.")
    async def games_enableall(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        for key in GAME_KEYS:
            self.bot.db.set_game_enabled(interaction.guild_id, key, True)
        await interaction.response.send_message("✅ All games **enabled**.", ephemeral=True)

    @games.command(name="disableall", description="Disable all games in this server.")
    async def games_disableall(self, interaction: discord.Interaction):
        if not self._is_admin(interaction):
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        for key in GAME_KEYS:
            self.bot.db.set_game_enabled(interaction.guild_id, key, False)
        await interaction.response.send_message("🚫 All games **disabled**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
