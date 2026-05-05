import asyncio
import random
import time
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.chaos import maybe_activate_chaos, get_chaos, clear_chaos, is_cursed, is_fog

logger = logging.getLogger("mica.reflex_games")


class ReflexGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def trigger_game(self, channel: discord.TextChannel, game_key: str = None):
        """Called by scheduler; routes to correct trigger by game_key."""
        dispatch = {
            "dont_touch_it": self.trigger_dont_touch_it,
            "sniper_window": self.trigger_sniper_window,
            "echo_chamber": self.trigger_echo_chamber,
            "freeze_tag": self.trigger_freeze_tag,
        }
        fn = dispatch.get(game_key)
        if fn:
            await fn(channel)

    # ── DON'T TOUCH IT ─────────────────────────────────────────────────────

    async def trigger_dont_touch_it(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "dont_touch_it"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "dont_touch_it")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        fuse = random.randint(8, 25)
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        desc = (
            f"💣 **A bomb has appeared!** Fuse: **{fuse} seconds**\n\n"
            f"React with 💣 — but the **LAST** to react before it explodes wins!\n"
            f"Reacting too early costs you 2 points!"
        )
        if fog:
            desc = f"💣 Something ticks... React with 💣 at the right moment."
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(
            title="💣 Don't Touch It!",
            description=desc,
            color=discord.Color.red()
        )
        msg = await channel.send(embed=embed)
        await msg.add_reaction("💣")
        self.bot.db.set_active_game(guild_id, "dont_touch_it", channel.id, str(fuse))
        start = time.time()
        early_reactors: list[tuple[int, float]] = []  # (user_id, elapsed)

        def check(reaction, user):
            return str(reaction.emoji) == "💣" and reaction.message.id == msg.id and not user.bot

        explode_time = start + fuse
        active = True
        while active and time.time() < explode_time:
            remaining = explode_time - time.time()
            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=min(1.0, remaining), check=check
                )
                elapsed = time.time() - start
                early_reactors.append((user.id, elapsed))
            except asyncio.TimeoutError:
                if time.time() >= explode_time:
                    active = False

        if not early_reactors:
            await channel.send("💥 The bomb exploded with no reactors! No winner.")
        else:
            pts_map = {}
            for user_id, elapsed in early_reactors:
                if elapsed < fuse * 0.5:
                    # Too early — penalty
                    self.bot.db.deduct_points(guild_id, user_id, "dont_touch_it", 2)
                    pts_map[user_id] = -2
            # Winner is the last reactor (regardless of early status, last = highest elapsed)
            last_user_id, last_elapsed = max(early_reactors, key=lambda x: x[1])
            if pts_map.get(last_user_id, 0) < 0:
                # Winner was penalised — still wins but with 0 net
                pts = 1
            else:
                pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
            if cursed:
                # Cursed: first reactor wins instead
                first_user_id, _ = min(early_reactors, key=lambda x: x[1])
                last_user_id = first_user_id
            member = channel.guild.get_member(last_user_id)
            name = member.mention if member else f"<@{last_user_id}>"
            self.bot.db.add_points(guild_id, last_user_id, "dont_touch_it", pts)
            for uid, _ in early_reactors:
                if uid != last_user_id and uid not in pts_map:
                    self.bot.db.deduct_points(guild_id, uid, "dont_touch_it", 1)
            await channel.send(f"💥 BOOM! {name} was last to touch it and survives! (+{pts} pt)")

        self.bot.db.clear_active_game(guild_id, "dont_touch_it")
        clear_chaos(guild_id)

    # ── SNIPER WINDOW ──────────────────────────────────────────────────────

    async def trigger_sniper_window(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "sniper_window"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "sniper_window")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        delay = random.randint(3, 12)
        fog = is_fog(guild_id)

        pre_desc = "🎯 **Sniper Window** — A window will open. React with 🎯 within EXACTLY 3 seconds. Too early or too late — you lose."
        if fog:
            pre_desc = "🎯 Stay ready..."
        if chaos.active and not fog:
            pre_desc = f"{chaos.describe()}\n\n{pre_desc}"

        embed = discord.Embed(title="🎯 Sniper Window!", description=pre_desc, color=discord.Color.dark_green())
        await channel.send(embed=embed)
        self.bot.db.set_active_game(guild_id, "sniper_window", channel.id)

        await asyncio.sleep(delay)

        window_embed = discord.Embed(
            title="🎯 WINDOW OPEN!",
            description="React with 🎯 NOW — you have exactly **3 seconds**!",
            color=discord.Color.green()
        )
        msg = await channel.send(embed=window_embed)
        await msg.add_reaction("🎯")
        window_open = time.time()

        reactors: list[tuple[int, float]] = []

        def check(reaction, user):
            return str(reaction.emoji) == "🎯" and reaction.message.id == msg.id and not user.bot

        window_end = window_open + 3.0
        while time.time() < window_end:
            remaining = window_end - time.time()
            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=min(0.5, remaining), check=check
                )
                elapsed = time.time() - window_open
                reactors.append((user.id, elapsed))
            except asyncio.TimeoutError:
                pass

        if not reactors:
            await channel.send("🎯 Nobody hit the window in time!")
        else:
            # Winner: closest to 1.5s (middle of the window)
            target = 1.5
            winner_id, elapsed = min(reactors, key=lambda x: abs(x[1] - target))
            pts = 3 if (chaos.active and chaos.modifier == "double_points") else 2
            self.bot.db.add_points(guild_id, winner_id, "sniper_window", pts)
            member = channel.guild.get_member(winner_id)
            name = member.mention if member else f"<@{winner_id}>"
            await channel.send(
                f"🎯 {name} hit the window at **{elapsed:.3f}s** — closest to perfect timing! (+{pts} pts)"
            )
            # Penalise those who were too late (> 3s shouldn't be possible, but >2.8s is risky)
            for uid, t in reactors:
                if uid != winner_id and t > 2.8:
                    self.bot.db.deduct_points(guild_id, uid, "sniper_window", 1)

        self.bot.db.clear_active_game(guild_id, "sniper_window")
        clear_chaos(guild_id)

    # ── ECHO CHAMBER ───────────────────────────────────────────────────────

    async def trigger_echo_chamber(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "echo_chamber"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "echo_chamber")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        words = ["echo", "ripple", "wave", "signal", "pulse", "chorus", "mirror", "bounce"]
        word = random.choice(words)
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        target_pos = 3 if not cursed else 1  # Cursed: first person wins

        desc = (
            f"🔊 **Echo Chamber!** The word is: **{word}**\n\n"
            f"Wait for at least **2 others** to type it first. "
            f"The **{_ordinal(target_pos)} person** to type it wins!"
        )
        if fog:
            desc = "🔊 A word echoes through the chamber... type it when you feel the moment is right."
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="🔊 Echo Chamber!", description=desc, color=discord.Color.purple())
        await channel.send(embed=embed)
        self.bot.db.set_active_game(guild_id, "echo_chamber", channel.id, word)

        typers: list[int] = []
        winner_found = False

        def check(m: discord.Message):
            return (
                m.channel.id == channel.id
                and not m.author.bot
                and m.content.strip().lower() == word.lower()
            )

        end_time = asyncio.get_event_loop().time() + 60
        while not winner_found:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
                user = msg.author
                if user.id not in typers:
                    typers.append(user.id)
                    pos = len(typers)
                    if pos == 1 and not cursed:
                        await msg.add_reaction("1️⃣")
                    elif pos == 2 and not cursed:
                        await msg.add_reaction("2️⃣")
                    elif pos == target_pos:
                        pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
                        self.bot.db.add_points(guild_id, user.id, "echo_chamber", pts)
                        await channel.send(
                            f"🔊 {user.mention} was the **{_ordinal(target_pos)}** to echo — they win! (+{pts} pt)"
                        )
                        winner_found = True
            except asyncio.TimeoutError:
                break

        if not winner_found:
            await channel.send(f"🔊 The echo faded... not enough people joined the chamber.")
        self.bot.db.clear_active_game(guild_id, "echo_chamber")
        clear_chaos(guild_id)

    # ── FREEZE TAG ─────────────────────────────────────────────────────────

    async def trigger_freeze_tag(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "freeze_tag"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "freeze_tag")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        if fog:
            desc = "⚠️ Something is happening... stay sharp."
        else:
            desc = "🧊 **FREEZE!** Anyone who types in the next **10 seconds** loses 1 point! Stay silent!"
        if cursed:
            desc = "🧊 **ANTI-FREEZE!** First person to type ANYTHING in the next 10 seconds gains 2 points!"
        if chaos.active and not fog and not cursed:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="🧊 Freeze Tag!", description=desc, color=discord.Color.light_grey())
        await channel.send(embed=embed)
        self.bot.db.set_active_game(guild_id, "freeze_tag", channel.id)

        talkers: list[int] = []

        def check(m: discord.Message):
            return m.channel.id == channel.id and not m.author.bot

        end_time = asyncio.get_event_loop().time() + 10
        while True:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
                if msg.author.id not in talkers:
                    talkers.append(msg.author.id)
                    if cursed:
                        pts = 2 if (chaos.active and chaos.modifier == "double_points") else 2
                        self.bot.db.add_points(guild_id, msg.author.id, "freeze_tag", pts)
                        await channel.send(f"🧊 {msg.author.mention} broke the anti-freeze! (+{pts} pts)")
                        break
                    else:
                        self.bot.db.deduct_points(guild_id, msg.author.id, "freeze_tag", 1)
                        await msg.add_reaction("🧊")
            except asyncio.TimeoutError:
                break

        if not cursed and not talkers:
            # Everyone survived
            await channel.send("✅ Everyone stayed frozen! No points lost this round.")
        elif not cursed and talkers:
            names = [f"<@{uid}>" for uid in talkers]
            await channel.send(f"🧊 These players couldn't stay quiet: {', '.join(names)} (-1 pt each)")

        self.bot.db.clear_active_game(guild_id, "freeze_tag")
        clear_chaos(guild_id)

    # ── Manual triggers ────────────────────────────────────────────────────

    rtrigger = app_commands.Group(name="rtrigger", description="Manually trigger reflex games (admin only).")

    @rtrigger.command(name="bomb", description="Trigger Don't Touch It.")
    async def rtrigger_bomb(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Don't Touch It...", ephemeral=True)
        await self.trigger_dont_touch_it(interaction.channel)

    @rtrigger.command(name="sniper", description="Trigger Sniper Window.")
    async def rtrigger_sniper(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Sniper Window...", ephemeral=True)
        await self.trigger_sniper_window(interaction.channel)

    @rtrigger.command(name="echo", description="Trigger Echo Chamber.")
    async def rtrigger_echo(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Echo Chamber...", ephemeral=True)
        await self.trigger_echo_chamber(interaction.channel)

    @rtrigger.command(name="freeze", description="Trigger Freeze Tag.")
    async def rtrigger_freeze(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Freeze Tag...", ephemeral=True)
        await self.trigger_freeze_tag(interaction.channel)


def _ordinal(n: int) -> str:
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    return f"{n}{suffixes.get(n if n < 20 else n % 10, 'th')}"


async def setup(bot):
    await bot.add_cog(ReflexGames(bot))
