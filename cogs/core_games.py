import asyncio
import random
import time
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.chaos import maybe_activate_chaos, get_chaos, clear_chaos, is_cursed, is_fog
from utils.api_helpers import generate_random_string, pick_secret_word

logger = logging.getLogger("mica.core_games")

PACKAGES = ["📦", "🎁", "💌", "🧧", "🎀", "💝", "🛍️", "📫"]


class CoreGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._active: dict[tuple, asyncio.Task] = {}

    def _get_channel(self, guild_id: int, game_key: str) -> discord.TextChannel | None:
        setting = self.bot.db.get_game_setting(guild_id, game_key)
        if not setting or not setting["enabled"]:
            return None
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None
        if setting["channel_id"]:
            return guild.get_channel(setting["channel_id"])
        return next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
            None
        )

    # ── DROP ZONE ──────────────────────────────────────────────────────────

    async def trigger_game(self, channel: discord.TextChannel, game_key: str = None):
        """Called by scheduler; routes to correct trigger by game_key."""
        pass  # Individual triggers used directly

    async def trigger_drop_zone(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "drop_zone"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "drop_zone")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        pkg = random.choice(PACKAGES)
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        desc = f"A package {pkg} has dropped! First to react with ✅ claims it!"
        if cursed:
            desc = f"A package {pkg} has dropped! **CURSED:** Last to react ✅ before timeout wins!"
        if fog:
            desc = f"Something appeared... 👀"
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="📦 Drop Zone!", description=desc, color=discord.Color.yellow())
        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        self.bot.db.set_active_game(guild_id, "drop_zone", channel.id)

        claimed = False
        start = time.time()
        timeout = 90

        def check(reaction, user):
            return (
                str(reaction.emoji) == "✅"
                and reaction.message.id == msg.id
                and not user.bot
            )

        try:
            if cursed:
                # Cursed: last reactor before timeout wins
                reactors = []
                end_time = time.time() + timeout
                while time.time() < end_time:
                    try:
                        reaction, user = await self.bot.wait_for(
                            "reaction_add", timeout=min(10, end_time - time.time()), check=check
                        )
                        reactors.append(user)
                    except asyncio.TimeoutError:
                        break
                if reactors:
                    winner = reactors[-1]
                    pts = 1
                    self.bot.db.add_points(guild_id, winner.id, "drop_zone", pts)
                    await channel.send(f"🏆 {winner.mention} wins the **CURSED** Drop Zone! (+{pts} pt)")
            else:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=timeout, check=check)
                elapsed = time.time() - start
                chaos_state = get_chaos(guild_id)
                pts = 2 if chaos_state.active and chaos_state.modifier == "double_points" else 1
                self.bot.db.add_points(guild_id, user.id, "drop_zone", pts)
                self.bot.db.increment_streak(guild_id, user.id, "drop_zone")
                await channel.send(f"🎉 {user.mention} claimed the package in **{elapsed:.2f}s**! (+{pts} pt)")
                claimed = True
        except asyncio.TimeoutError:
            if not claimed:
                await channel.send("📦 The package went unclaimed...")
        finally:
            self.bot.db.clear_active_game(guild_id, "drop_zone")
            clear_chaos(guild_id)

    # ── GHOST HUNT ─────────────────────────────────────────────────────────

    async def trigger_ghost_hunt(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "ghost_hunt"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "ghost_hunt")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        desc = "A 👻 has appeared! First to react with ⚡ banishes it!"
        if fog:
            desc = "Something spooky lurks... 🌑"
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="👻 Ghost Hunt!", description=desc, color=discord.Color.dark_gray())
        msg = await channel.send(embed=embed)
        await msg.add_reaction("⚡")
        self.bot.db.set_active_game(guild_id, "ghost_hunt", channel.id)

        def check(reaction, user):
            return str(reaction.emoji) == "⚡" and reaction.message.id == msg.id and not user.bot

        claimed = False
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60, check=check)
            pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
            if cursed:
                pts = max(0, pts - 1)
                await channel.send(f"💀 **CURSED:** {user.mention} banished the ghost but lost momentum. (+{pts} pt)")
            else:
                self.bot.db.add_points(guild_id, user.id, "ghost_hunt", pts)
                self.bot.db.increment_streak(guild_id, user.id, "ghost_hunt")
                streak = self.bot.db.get_streak(guild_id, user.id, "ghost_hunt")
                streak_msg = f" 🔥 Streak: {streak['current']}!" if streak["current"] > 1 else ""
                await channel.send(f"⚡ {user.mention} banished the ghost! (+{pts} pt){streak_msg}")
            claimed = True
        except asyncio.TimeoutError:
            if not claimed:
                await channel.send("👻 The ghost escaped into the void...")
        finally:
            self.bot.db.clear_active_game(guild_id, "ghost_hunt")
            clear_chaos(guild_id)

    # ── BURST ROUND ────────────────────────────────────────────────────────

    async def trigger_burst_round(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "burst_round"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "burst_round")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        secret = pick_secret_word()
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        if fog:
            desc = "⚡ **BURST ROUND!** A word has been chosen. Type it to win — 60 seconds!"
        else:
            desc = f"⚡ **BURST ROUND!** Type the secret word to win!\n🔑 Secret word: **`{secret}`**\n⏱️ You have 60 seconds!"

        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        self.bot.db.set_active_game(guild_id, "burst_round", channel.id, secret)
        embed = discord.Embed(title="💥 Burst Round!", description=desc, color=discord.Color.orange())
        await channel.send(embed=embed)

        def check(m: discord.Message):
            return (
                m.channel.id == channel.id
                and not m.author.bot
                and m.content.strip().lower() == secret.lower()
            )

        try:
            msg = await self.bot.wait_for("message", timeout=60, check=check)
            pts = 3 if (chaos.active and chaos.modifier == "double_points") else 2 if not cursed else 1
            winner = msg.author
            self.bot.db.add_points(guild_id, winner.id, "burst_round", pts)
            await channel.send(f"💥 {winner.mention} said the magic word! (+{pts} pts)")
        except asyncio.TimeoutError:
            await channel.send(f"💨 Nobody said **`{secret}`** in time. The window closes.")
        finally:
            self.bot.db.clear_active_game(guild_id, "burst_round")
            clear_chaos(guild_id)

    # ── COPYCAT ────────────────────────────────────────────────────────────

    async def trigger_copycat(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "copycat"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "copycat")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        use_emoji = random.choice([True, False])
        target = generate_random_string(random.randint(6, 10), use_emoji=use_emoji)
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        desc = f"🐱 **COPYCAT!** Copy the sequence below exactly.\n```{target}```\n⚠️ Wrong answer = 30 second lockout!"
        if fog:
            desc = f"🐱 Something is written... copy it exactly.\n```{target}```"
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        self.bot.db.set_active_game(guild_id, "copycat", channel.id, target)
        embed = discord.Embed(title="🐱 Copycat!", description=desc, color=discord.Color.teal())
        await channel.send(embed=embed)

        wrong_users: set[int] = set()
        winner_found = False

        def check(m: discord.Message):
            return m.channel.id == channel.id and not m.author.bot

        end_time = asyncio.get_event_loop().time() + 60
        while not winner_found:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
                user = msg.author
                if self.bot.db.is_locked_out(guild_id, user.id):
                    await msg.add_reaction("🔒")
                    continue
                if msg.content.strip() == target:
                    pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
                    if cursed and not wrong_users:
                        # Cursed: first correct answer loses
                        self.bot.db.deduct_points(guild_id, user.id, "copycat", 1)
                        await channel.send(f"💀 **CURSED:** {user.mention} was first — and that means you LOSE. (-1 pt)")
                        continue
                    self.bot.db.add_points(guild_id, user.id, "copycat", pts)
                    await channel.send(f"✅ {user.mention} copied it perfectly! (+{pts} pt)")
                    winner_found = True
                else:
                    if user.id not in wrong_users:
                        wrong_users.add(user.id)
                        self.bot.db.set_lockout(guild_id, user.id, 30)
                        self.bot.db.deduct_points(guild_id, user.id, "copycat", 1)
                        await msg.add_reaction("❌")
                        await channel.send(
                            f"❌ {user.mention} got it wrong! Locked out for 30 seconds. (-1 pt)",
                            delete_after=10
                        )
            except asyncio.TimeoutError:
                break

        if not winner_found:
            await channel.send(f"⏱️ Time's up! The sequence was: `{target}`")
        self.bot.db.clear_active_game(guild_id, "copycat")
        clear_chaos(guild_id)

    # ── Slash commands (manual triggers for testing / admin use) ───────────

    trigger = app_commands.Group(name="trigger", description="Manually trigger games (admin only).")

    @trigger.command(name="dropzone", description="Manually trigger Drop Zone.")
    async def trigger_drop_zone_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Drop Zone...", ephemeral=True)
        await self.trigger_drop_zone(interaction.channel)

    @trigger.command(name="ghosthunt", description="Manually trigger Ghost Hunt.")
    async def trigger_ghost_hunt_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Ghost Hunt...", ephemeral=True)
        await self.trigger_ghost_hunt(interaction.channel)

    @trigger.command(name="burst", description="Manually trigger Burst Round.")
    async def trigger_burst_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Burst Round...", ephemeral=True)
        await self.trigger_burst_round(interaction.channel)

    @trigger.command(name="copycat", description="Manually trigger Copycat.")
    async def trigger_copycat_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Copycat...", ephemeral=True)
        await self.trigger_copycat(interaction.channel)


async def setup(bot):
    await bot.add_cog(CoreGames(bot))
