import discord
from discord import app_commands
from discord.ext import commands
from utils.chaos import get_chaos, CHAOS_MODIFIERS
import logging

logger = logging.getLogger("mica.chaos_cog")

CHAOS_DESCRIPTIONS = {
    "double_points": (
        "⚡ **Double Points**",
        "Randomly declared for the next event. No warning until it triggers. Points are doubled."
    ),
    "cursed_round": (
        "💀 **Cursed Round**",
        "Rules invert for one round. Fastest answer loses, slowest correct answer wins."
    ),
    "fog_of_war": (
        "🌫️ **Fog of War**",
        "The bot doesn't announce what game is starting. Members must figure out the rules from context clues."
    ),
    "bounty_target": (
        "🎯 **Bounty Target**",
        "One member is secretly designated the target. If anyone beats them specifically, they earn double points. Target doesn't know."
    ),
}


class Chaos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="chaos", description="Learn about the chaos modifier system.")
    async def chaos_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎲 Chaos Modifiers",
            description=(
                "Chaos modifiers activate randomly on top of any game, with no warning. "
                f"There's a **{int(20)}% chance** any game trigger includes a chaos modifier.\n\n"
                "Here are all possible modifiers:"
            ),
            color=discord.Color.dark_red()
        )
        for key, (title, desc) in CHAOS_DESCRIPTIONS.items():
            embed.add_field(name=title, value=desc, inline=False)

        active = get_chaos(interaction.guild_id)
        if active.active:
            embed.set_footer(text=f"🎲 A chaos modifier is currently active in this server: {active.modifier}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="activechaos", description="See if a chaos modifier is currently active.")
    async def active_chaos(self, interaction: discord.Interaction):
        state = get_chaos(interaction.guild_id)
        if state.active:
            title, desc = CHAOS_DESCRIPTIONS.get(state.modifier, ("Unknown", "No description."))
            embed = discord.Embed(
                title=f"🎲 Active Chaos: {title}",
                description=desc,
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="🎲 No Active Chaos",
                description="No chaos modifier is active right now. One might be lurking for the next game...",
                color=discord.Color.green()
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Chaos(bot))
