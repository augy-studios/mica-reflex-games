import discord
from discord import app_commands
from discord.ext import commands

# (group, subcommand_or_None, description)
PAGES = [
    {
        "title": "🎮 Help — Server Config  (1/4)",
        "description": "Requires **Manage Channels** permission.",
        "color": discord.Color.blurple(),
        "entries": [
            ("games", "enable",      "Enable a specific game in this server."),
            ("games", "disable",     "Disable a specific game in this server."),
            ("games", "setchannel",    "Set which channel a game triggers in."),
            ("games", "setchannelall", "Set one channel for all games at once."),
            ("games", "clearchannel",  "Remove the custom channel for a game."),
            ("games", "status",      "View all games and their enabled status."),
            ("games", "enableall",   "Enable all 15 games at once."),
            ("games", "disableall",  "Disable all 15 games at once."),
        ],
    },
    {
        "title": "🎯 Help — Manual Triggers  (2/4)",
        "description": "Force-start any game right now. Requires **Manage Channels** permission.",
        "color": discord.Color.orange(),
        "entries": [
            ("trigger",  "dropzone", "Trigger Drop Zone."),
            ("trigger",  "ghosthunt","Trigger Ghost Hunt."),
            ("trigger",  "burst",    "Trigger Burst Round."),
            ("trigger",  "copycat",  "Trigger Copycat."),
            ("ktrigger", "bait",     "Trigger Bait and Hook."),
            ("ktrigger", "bounty",   "Trigger Open Bounty."),
            ("ktrigger", "flag",     "Trigger Flag Blitz."),
            ("ktrigger", "blurred",  "Trigger Blurred Vision."),
            ("rtrigger", "bomb",     "Trigger Don't Touch It."),
            ("rtrigger", "sniper",   "Trigger Sniper Window."),
            ("rtrigger", "echo",     "Trigger Echo Chamber."),
            ("rtrigger", "freeze",   "Trigger Freeze Tag."),
        ],
    },
    {
        "title": "🏆 Help — Leaderboards  (3/4)",
        "description": "Public — anyone can use these.",
        "color": discord.Color.gold(),
        "entries": [
            ("lb", "alltime", "All-time points leaderboard."),
            ("lb", "weekly",  "Weekly points leaderboard (7-day rolling)."),
            ("lb", "duels",   "Duel win/loss leaderboard."),
            ("lb", "streaks", "Current hot streaks."),
            ("lb", "cursed",  "Cursed Crown — most points lost to penalties."),
            ("lb", "score",   "Your personal stats and rank."),
        ],
    },
    {
        "title": "⚔️ Help — Duels & Info  (4/4)",
        "description": "Public — challenge other members and learn about chaos.",
        "color": discord.Color.red(),
        "entries": [
            ("quickdraw",   None, "Challenge someone to a Quickdraw duel (Best of 3)."),
            ("copycatduel", None, "Challenge someone to a Copycat Duel (5 rounds)."),
            ("triviaclash", None, "Challenge someone to a Trivia Clash (5 questions)."),
            ("chaos",       None, "Learn about the chaos modifier system."),
            ("activechaos", None, "Check if a chaos modifier is currently active."),
            ("help",        None, "Show this help menu."),
        ],
    },
]


def _mention(synced: dict, group: str, sub: str | None) -> str:
    cmd = synced.get(group)
    if cmd is None:
        return f"`/{group}{' ' + sub if sub else ''}`"
    if sub:
        return f"</{group} {sub}:{cmd.id}>"
    return f"</{group}:{cmd.id}>"


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.bot = bot
        self.page = 0

    def build_embed(self) -> discord.Embed:
        page = PAGES[self.page]
        synced = getattr(self.bot, "_synced_commands", {})
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=page["color"],
        )
        lines = [
            f"{_mention(synced, grp, sub)} — {desc}"
            for grp, sub, desc in page["entries"]
        ]
        embed.add_field(name="​", value="\n".join(lines), inline=False)
        embed.set_footer(text=f"Page {self.page + 1} of {len(PAGES)}")
        return embed

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % len(PAGES)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % len(PAGES)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all bot commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        view = HelpView(self.bot)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
