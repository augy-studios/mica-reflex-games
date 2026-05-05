import asyncio
import random
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.chaos import maybe_activate_chaos, get_chaos, clear_chaos, is_cursed, is_fog
from utils.api_helpers import fetch_trivia, fetch_countries, fetch_bait_fact, pick_flag_by_difficulty

logger = logging.getLogger("mica.knowledge_games")

# Blurred Vision: approximate blurring using spoiler tags and "pixelated" descriptions
BLUR_LEVELS = ["🟫🟫🟫🟫🟫", "🟧🟧🟧", "🟨🟨", "🔶", "🖼️"]
REVEAL_POINTS = [5, 4, 3, 2, 1]  # Points based on how early they guessed


class KnowledgeGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._countries_cache: list[dict] = []

    async def _get_countries(self):
        if not self._countries_cache:
            self._countries_cache = await fetch_countries()
        return self._countries_cache

    async def trigger_game(self, channel: discord.TextChannel, game_key: str = None):
        """Called by scheduler; routes to correct trigger by game_key."""
        dispatch = {
            "bait_and_hook": self.trigger_bait_and_hook,
            "open_bounty": self.trigger_open_bounty,
            "flag_blitz": self.trigger_flag_blitz,
            "blurred_vision": self.trigger_blurred_vision,
        }
        fn = dispatch.get(game_key)
        if fn:
            await fn(channel)

    # ── BAIT AND HOOK ──────────────────────────────────────────────────────

    async def trigger_bait_and_hook(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "bait_and_hook"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "bait_and_hook")
        if not setting or not setting["enabled"]:
            return

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        bait = await fetch_bait_fact()
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        statement = bait["statement"]
        correct = bait["correct_answer"].strip().lower()

        desc = (
            f'🪝 **Is this true or bunk?**\n\n*"{statement}"*\n\n'
            f'Reply with the **correct information** to win! Wrong answers dock 1 point.'
        )
        if fog:
            desc = f'🪝 Something smells fishy...\n\n*"{statement}"*\n\nCan you correct it?'
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="🎣 Bait and Hook!", description=desc, color=discord.Color.dark_gold())
        await channel.send(embed=embed)
        self.bot.db.set_active_game(guild_id, "bait_and_hook", channel.id, correct)

        penalised: set[int] = set()
        winner_found = False

        def check(m: discord.Message):
            return m.channel.id == channel.id and not m.author.bot

        end_time = asyncio.get_event_loop().time() + 90
        while not winner_found:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
                answer = msg.content.strip().lower()
                user = msg.author
                if correct in answer or answer in correct:
                    pts = 3 if (chaos.active and chaos.modifier == "double_points") else 2
                    if cursed:
                        pts = max(1, pts - 1)
                    self.bot.db.add_points(guild_id, user.id, "bait_and_hook", pts)
                    await channel.send(
                        f"✅ {user.mention} got it! The correct answer: **{bait['correct_answer']}** (+{pts} pts)"
                    )
                    winner_found = True
                else:
                    if user.id not in penalised:
                        penalised.add(user.id)
                        self.bot.db.deduct_points(guild_id, user.id, "bait_and_hook", 1)
                        await msg.add_reaction("❌")
            except asyncio.TimeoutError:
                break

        if not winner_found:
            await channel.send(f"⏱️ Time's up! The correct answer was: **{bait['correct_answer']}**")
        self.bot.db.clear_active_game(guild_id, "bait_and_hook")
        clear_chaos(guild_id)

    # ── OPEN BOUNTY ────────────────────────────────────────────────────────

    async def trigger_open_bounty(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        setting = self.bot.db.get_game_setting(guild_id, "open_bounty")
        if not setting or not setting["enabled"]:
            return

        existing = self.bot.db.get_bounty(guild_id)
        if existing:
            return  # A bounty is already live

        items = await fetch_trivia(1)
        item = items[0]
        question = item["question"]
        answer = item["correct_answer"].strip().lower()

        chaos = maybe_activate_chaos(guild_id)
        fog = is_fog(guild_id)
        desc = (
            f"❓ **{question}**\n\n"
            f"First correct answer wins! This bounty stays open until claimed."
        )
        if fog:
            desc = f"❓ **{question}**\n\nA question hangs in the air..."
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"

        embed = discord.Embed(title="🎯 Open Bounty", description=desc, color=discord.Color.green())
        msg = await channel.send(embed=embed)
        self.bot.db.set_bounty(guild_id, channel.id, question, answer, msg.id)

    async def check_open_bounty(self, message: discord.Message):
        """Called from on_message event to check open bounty answers."""
        guild_id = message.guild.id
        bounty = self.bot.db.get_bounty(guild_id)
        if not bounty:
            return
        if message.channel.id != bounty["channel_id"]:
            return
        if message.author.bot:
            return

        answer = bounty["answer"].strip().lower()
        user_answer = message.content.strip().lower()

        if answer in user_answer or user_answer in answer:
            pts = 3
            chaos = get_chaos(guild_id)
            if chaos.active and chaos.modifier == "double_points":
                pts *= 2
            self.bot.db.add_points(guild_id, message.author.id, "open_bounty", pts)
            self.bot.db.clear_bounty(guild_id)
            await message.channel.send(
                f"🎯 {message.author.mention} claimed the bounty! Answer: **{bounty['answer']}** (+{pts} pts)"
            )
            clear_chaos(guild_id)
            # Post a new bounty after a short delay
            await asyncio.sleep(5)
            await self.trigger_open_bounty(message.channel)

    # ── FLAG BLITZ ─────────────────────────────────────────────────────────

    async def trigger_flag_blitz(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "flag_blitz"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "flag_blitz")
        if not setting or not setting["enabled"]:
            return

        countries = await self._get_countries()
        accuracy = self.bot.db.get_flag_accuracy(guild_id)
        country = pick_flag_by_difficulty(countries, accuracy)
        correct_name = country["name"].lower()

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        fog = is_fog(guild_id)
        cursed = is_cursed(guild_id)

        desc = f"# {country['flag']}\nWhat country does this flag belong to?"
        if fog:
            desc = f"# {country['flag']}\nSomething flutters in the wind..."
        if chaos.active and not fog:
            desc = f"{chaos.describe()}\n\n{desc}"
        if cursed:
            desc += "\n💀 **CURSED:** Slowest correct answer wins!"

        embed = discord.Embed(title="🚩 Flag Blitz!", description=desc, color=discord.Color.blue())
        await channel.send(embed=embed)
        self.bot.db.set_active_game(guild_id, "flag_blitz", channel.id, correct_name)

        def check(m: discord.Message):
            return m.channel.id == channel.id and not m.author.bot

        reactors = []
        winner_found = False
        end_time = asyncio.get_event_loop().time() + 45

        while not winner_found:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
                answer = msg.content.strip().lower()
                if correct_name in answer or answer in correct_name:
                    self.bot.db.record_flag_attempt(guild_id, True)
                    if cursed:
                        reactors.append(msg.author)
                        await msg.add_reaction("✅")
                        continue
                    pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
                    self.bot.db.add_points(guild_id, msg.author.id, "flag_blitz", pts)
                    await channel.send(
                        f"🚩 {msg.author.mention} knew it! It's **{country['name']}**! (+{pts} pt)"
                    )
                    winner_found = True
                else:
                    self.bot.db.record_flag_attempt(guild_id, False)
            except asyncio.TimeoutError:
                break

        if cursed and reactors:
            winner = reactors[-1]
            pts = 2 if (chaos.active and chaos.modifier == "double_points") else 1
            self.bot.db.add_points(guild_id, winner.id, "flag_blitz", pts)
            await channel.send(
                f"💀 **CURSED:** {winner.mention} was last and WINS! It was **{country['name']}**! (+{pts} pt)"
            )
            winner_found = True

        if not winner_found and not (cursed and reactors):
            await channel.send(f"⏱️ Nobody got it! The answer was **{country['name']}** {country['flag']}")

        self.bot.db.clear_active_game(guild_id, "flag_blitz")
        clear_chaos(guild_id)

    # ── BLURRED VISION ─────────────────────────────────────────────────────

    async def trigger_blurred_vision(self, channel: discord.TextChannel):
        guild_id = channel.guild.id
        if self.bot.db.is_game_active(guild_id, "blurred_vision"):
            return
        setting = self.bot.db.get_game_setting(guild_id, "blurred_vision")
        if not setting or not setting["enabled"]:
            return

        # Use trivia for subject since we can't attach real images
        # We simulate "blurred vision" with progressively-revealed clues
        items = await fetch_trivia(1)
        item = items[0]
        question = item["question"]
        answer = item["correct_answer"].strip().lower()
        correct_display = item["correct_answer"]

        # Build clue set: reveal letters/words progressively
        words = correct_display.split()
        clues = []
        clues.append("_ " * len(correct_display.replace(" ", "")))  # fully hidden
        if len(words) > 1:
            clues.append(f"{'_ ' * len(words[0])}{'_ ' * len(' '.join(words[1:]))}")
        clues.append(f"{correct_display[0]}{'_ ' * (len(correct_display) - 1)}")
        clues.append(f"{correct_display[:max(2, len(correct_display)//2)]}...")

        chaos = maybe_activate_chaos(guild_id, [m.id for m in channel.guild.members if not m.bot])
        fog = is_fog(guild_id)

        base_desc = f"🔍 **Blurred Vision!**\n*{question}*\n\nThe answer is slowly coming into focus..."
        if chaos.active and not fog:
            base_desc = f"{chaos.describe()}\n\n{base_desc}"

        self.bot.db.set_active_game(guild_id, "blurred_vision", channel.id, answer)

        current_reveal = 0
        winner_found = False
        msg = await channel.send(
            embed=discord.Embed(
                title="🔍 Blurred Vision!",
                description=f"{base_desc}\n\n`{clues[0]}`",
                color=discord.Color.dark_blue()
            )
        )

        def check(m: discord.Message):
            return m.channel.id == channel.id and not m.author.bot

        pts_map = REVEAL_POINTS  # [5, 4, 3, 2, 1]

        while current_reveal < len(clues) and not winner_found:
            remaining = 15
            try:
                m = await self.bot.wait_for("message", timeout=remaining, check=check)
                if answer in m.content.strip().lower() or m.content.strip().lower() in answer:
                    pts_base = pts_map[min(current_reveal, len(pts_map) - 1)]
                    pts = pts_base * 2 if (chaos.active and chaos.modifier == "double_points") else pts_base
                    self.bot.db.add_points(guild_id, m.author.id, "blurred_vision", pts)
                    await channel.send(
                        f"🔍 {m.author.mention} identified it with {current_reveal} reveal(s) used! "
                        f"Answer: **{correct_display}** (+{pts} pts)"
                    )
                    winner_found = True
            except asyncio.TimeoutError:
                current_reveal += 1
                if current_reveal < len(clues):
                    await msg.edit(
                        embed=discord.Embed(
                            title="🔍 Blurred Vision — Reveal!",
                            description=f"{base_desc}\n\n`{clues[current_reveal]}`\n\n*Reveal {current_reveal}/{len(clues)-1}*",
                            color=discord.Color.blue()
                        )
                    )

        if not winner_found:
            await channel.send(f"⏱️ Nobody guessed it! The answer was **{correct_display}**.")
        self.bot.db.clear_active_game(guild_id, "blurred_vision")
        clear_chaos(guild_id)

    # ── Manual triggers ────────────────────────────────────────────────────

    ktrigger = app_commands.Group(name="ktrigger", description="Manually trigger knowledge games (admin only).")

    @ktrigger.command(name="bait", description="Trigger Bait and Hook.")
    async def ktrigger_bait(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Bait and Hook...", ephemeral=True)
        await self.trigger_bait_and_hook(interaction.channel)

    @ktrigger.command(name="bounty", description="Trigger Open Bounty.")
    async def ktrigger_bounty(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Open Bounty...", ephemeral=True)
        await self.trigger_open_bounty(interaction.channel)

    @ktrigger.command(name="flag", description="Trigger Flag Blitz.")
    async def ktrigger_flag(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Flag Blitz...", ephemeral=True)
        await self.trigger_flag_blitz(interaction.channel)

    @ktrigger.command(name="blurred", description="Trigger Blurred Vision.")
    async def ktrigger_blurred(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message("❌ You need **Manage Channels** permission.", ephemeral=True)
        await interaction.response.send_message("🎯 Triggering Blurred Vision...", ephemeral=True)
        await self.trigger_blurred_vision(interaction.channel)


async def setup(bot):
    await bot.add_cog(KnowledgeGames(bot))
