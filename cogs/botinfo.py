import discord
from discord import app_commands
from discord.ext import commands
import platform
import socket
import os
import time
import psutil

logger = __import__("logging").getLogger("mica.botinfo")


def _count_commands(cmds) -> int:
    total = 0
    for cmd in cmds:
        if isinstance(cmd, app_commands.Group):
            total += _count_commands(cmd.commands)
        else:
            total += 1
    return total


class BotInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="botinfo", description="Show information about the bot and host system.")
    async def botinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()

        uname = platform.uname()
        os_str = f"{uname.system} {uname.release}"
        hostname = socket.gethostname()
        arch = platform.machine()
        cpu_cores = os.cpu_count() or 1
        cpu_usage = psutil.cpu_percent(interval=0.5)

        mem = psutil.virtual_memory()
        mem_used_mb = mem.used / (1024 ** 2)
        mem_total_gb = mem.total / (1024 ** 3)

        python_version = platform.python_version()
        dpy_version = discord.__version__

        guilds = len(self.bot.guilds)
        channels = sum(len(g.channels) for g in self.bot.guilds)
        users = sum(g.member_count or 0 for g in self.bot.guilds)

        total_commands = _count_commands(self.bot.tree.get_commands())

        start_time = getattr(self.bot, "start_time", time.time())
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        uptime_str = f"{hours:02d}:{minutes:02d}"

        lines = [
            f"**Operating System**: {os_str}",
            f"**Uptime**: {uptime_str}",
            f"**Hostname**: {hostname}",
            f"**CPU Architecture**: {arch} ({cpu_cores} cores)",
            f"**CPU Usage**: {cpu_usage:.0f}%",
            f"**Memory Usage**: {mem_used_mb:.2f}MB / {mem_total_gb:.2f}GB",
            f"**Python Version**: v{python_version}",
            f"**discord.py Version**: {dpy_version}",
            f"**Connected to** {guilds} guilds, {channels} channels, and {users} users",
            f"**Total Commands**: {total_commands}",
        ]

        embed = discord.Embed(
            title="Bot Information:",
            description="\n".join(f"• {line}" for line in lines),
            color=discord.Color.blurple(),
        )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(BotInfo(bot))
