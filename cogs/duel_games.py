import asyncio
import random
import time
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.api_helpers import generate_random_string, fetch_trivia
from utils.chaos import maybe_activate_chaos, get_chaos, clear_chaos

logger = logging.getLogger("mica.duel_games")

ACTIVE_DUELS: dict[int, dict] = {}  # guild_id → duel state


class DuelGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _in_duel(self, guild_id: int, user_id: int) -> bool:
        duel = ACTIVE_DUELS.get(guild_id)
        if not duel:
            return False
        return user_id in (duel.get("challenger"), duel.get("defender"))

    # ── QUICKDRAW ──────────────────────────────────────────────────────────

    @app_commands.command(name="quickdraw", description="Challenge someone to a Quickdraw duel!")
    @app_commands.describe(opponent="The member to challenge.")
    async def quickdraw(self, interaction: discord.Interaction, opponent: discord.Member):
        guild_id = interaction.guild_id
        challenger = interaction.user

        if opponent.bot:
            return await interaction.response.send_message("❌ You can't duel a bot.", ephemeral=True)
        if opponent.id == challenger.id:
            return await interaction.response.send_message("❌ You can't duel yourself.", ephemeral=True)
        if guild_id in ACTIVE_DUELS:
            return await interaction.response.send_message("❌ A duel is already in progress!", ephemeral=True)

        setting = self.bot.db.get_game_setting(guild_id, "quickdraw")
        if not setting or not setting["enabled"]:
            return await interaction.response.send_message("❌ Quickdraw is disabled in this server.", ephemeral=True)

        channel = interaction.channel
        await interaction.response.send_message(
            f"🤠 {challenger.mention} challenges {opponent.mention} to a **Quickdraw duel!**\n"
            f"{opponent.mention}, type `accept` within 30 seconds to accept."
        )

        def accept_check(m: discord.Message):
            return (
                m.author.id == opponent.id
                and m.channel.id == channel.id
                and m.content.strip().lower() == "accept"
            )

        try:
            await self.bot.wait_for("message", timeout=30, check=accept_check)
        except asyncio.TimeoutError:
            return await channel.send(f"⌛ {opponent.mention} didn't respond. Duel cancelled.")

        ACTIVE_DUELS[guild_id] = {
            "challenger": challenger.id,
            "defender": opponent.id,
            "type": "quickdraw",
        }

        chaos = maybe_activate_chaos(guild_id, [challenger.id, opponent.id])

        scores = {challenger.id: 0, opponent.id: 0}
        rounds = 3
        for r in range(1, rounds + 1):
            await channel.send(f"**Round {r}/{rounds}** — Get ready...")
            await asyncio.sleep(random.uniform(2, 5))
            draw_msg = await channel.send("🔫 **DRAW!** Type `BANG` first!")
            round_start = time.time()

            def bang_check(m: discord.Message):
                return (
                    m.channel.id == channel.id
                    and m.author.id in (challenger.id, opponent.id)
                    and m.content.strip().upper() == "BANG"
                )

            try:
                msg = await self.bot.wait_for("message", timeout=10, check=bang_check)
                elapsed = time.time() - round_start
                winner_id = msg.author.id
                scores[winner_id] += 1
                winner_member = channel.guild.get_member(winner_id)
                await channel.send(
                    f"🔫 {winner_member.mention} drew in **{elapsed:.3f}s**! "
                    f"Score: {channel.guild.get_member(challenger.id).display_name} {scores[challenger.id]} — "
                    f"{scores[opponent.id]} {channel.guild.get_member(opponent.id).display_name}"
                )
            except asyncio.TimeoutError:
                await channel.send("⌛ Nobody drew in time! Round skipped.")
            await asyncio.sleep(2)

        # Final result
        if scores[challenger.id] > scores[opponent.id]:
            duel_winner, duel_loser = challenger.id, opponent.id
        elif scores[opponent.id] > scores[challenger.id]:
            duel_winner, duel_loser = opponent.id, challenger.id
        else:
            duel_winner = duel_loser = None

        pts = 5 if (chaos.active and chaos.modifier == "double_points") else 3

        if duel_winner:
            self.bot.db.add_points(guild_id, duel_winner, "quickdraw", pts)
            self.bot.db.record_duel_win(guild_id, duel_winner)
            self.bot.db.record_duel_loss(guild_id, duel_loser)
            winner_member = channel.guild.get_member(duel_winner)
            await channel.send(
                f"🏆 **{winner_member.mention} wins the duel {scores[challenger.id]}-{scores[opponent.id]}!** (+{pts} pts)"
            )
        else:
            await channel.send("🤝 It's a **draw!** No points awarded.")

        ACTIVE_DUELS.pop(guild_id, None)
        clear_chaos(guild_id)

    # ── COPYCAT DUEL ───────────────────────────────────────────────────────

    @app_commands.command(name="copycatduel", description="Challenge someone to a Copycat Duel!")
    @app_commands.describe(opponent="The member to challenge.")
    async def copycatduel(self, interaction: discord.Interaction, opponent: discord.Member):
        guild_id = interaction.guild_id
        challenger = interaction.user

        if opponent.bot or opponent.id == challenger.id:
            return await interaction.response.send_message("❌ Invalid opponent.", ephemeral=True)
        if guild_id in ACTIVE_DUELS:
            return await interaction.response.send_message("❌ A duel is already active!", ephemeral=True)

        setting = self.bot.db.get_game_setting(guild_id, "copycat_duel")
        if not setting or not setting["enabled"]:
            return await interaction.response.send_message("❌ Copycat Duel is disabled.", ephemeral=True)

        channel = interaction.channel
        await interaction.response.send_message(
            f"🐱 {challenger.mention} challenges {opponent.mention} to a **Copycat Duel!**\n"
            f"{opponent.mention}, type `accept` within 30 seconds."
        )

        def accept_check(m):
            return m.author.id == opponent.id and m.channel.id == channel.id and m.content.strip().lower() == "accept"

        try:
            await self.bot.wait_for("message", timeout=30, check=accept_check)
        except asyncio.TimeoutError:
            return await channel.send("⌛ Challenge timed out.")

        ACTIVE_DUELS[guild_id] = {"challenger": challenger.id, "defender": opponent.id, "type": "copycat_duel"}
        chaos = maybe_activate_chaos(guild_id, [challenger.id, opponent.id])

        scores = {challenger.id: 0, opponent.id: 0}
        for r in range(1, 6):
            use_emoji = r > 2  # Harder later rounds
            length = 4 + r
            sequence = generate_random_string(length, use_emoji=use_emoji)
            embed = discord.Embed(
                title=f"🐱 Round {r}/5",
                description=f"Copy this sequence:\n```{sequence}```",
                color=discord.Color.teal()
            )
            await channel.send(embed=embed)

            responded: set[int] = set()
            round_winner = None

            def msg_check(m):
                return (
                    m.channel.id == channel.id
                    and m.author.id in (challenger.id, opponent.id)
                    and m.author.id not in responded
                )

            round_end = asyncio.get_event_loop().time() + 20
            while len(responded) < 2 and not round_winner:
                remaining = round_end - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    msg = await self.bot.wait_for("message", timeout=remaining, check=msg_check)
                    responded.add(msg.author.id)
                    if msg.content.strip() == sequence:
                        round_winner = msg.author.id
                        scores[round_winner] += 1
                        w = channel.guild.get_member(round_winner)
                        await channel.send(f"✅ {w.mention} nailed round {r}!")
                        break
                    else:
                        await msg.add_reaction("❌")
                except asyncio.TimeoutError:
                    break

            if not round_winner:
                await channel.send(f"⏱️ Nobody copied round {r} correctly. No point awarded.")
            await asyncio.sleep(2)

        if scores[challenger.id] > scores[opponent.id]:
            duel_winner, duel_loser = challenger.id, opponent.id
        elif scores[opponent.id] > scores[challenger.id]:
            duel_winner, duel_loser = opponent.id, challenger.id
        else:
            duel_winner = duel_loser = None

        pts = 5 if (chaos.active and chaos.modifier == "double_points") else 3
        if duel_winner:
            self.bot.db.add_points(guild_id, duel_winner, "copycat_duel", pts)
            self.bot.db.record_duel_win(guild_id, duel_winner)
            self.bot.db.record_duel_loss(guild_id, duel_loser)
            w = channel.guild.get_member(duel_winner)
            await channel.send(
                f"🏆 **{w.mention} wins the Copycat Duel {scores[challenger.id]}-{scores[opponent.id]}!** (+{pts} pts)"
            )
        else:
            await channel.send("🤝 It's a **tie!**")

        ACTIVE_DUELS.pop(guild_id, None)
        clear_chaos(guild_id)

    # ── TRIVIA CLASH ───────────────────────────────────────────────────────

    @app_commands.command(name="triviaclash", description="Challenge someone to a Trivia Clash!")
    @app_commands.describe(opponent="The member to challenge.")
    async def triviaclash(self, interaction: discord.Interaction, opponent: discord.Member):
        guild_id = interaction.guild_id
        challenger = interaction.user

        if opponent.bot or opponent.id == challenger.id:
            return await interaction.response.send_message("❌ Invalid opponent.", ephemeral=True)
        if guild_id in ACTIVE_DUELS:
            return await interaction.response.send_message("❌ A duel is already active!", ephemeral=True)

        setting = self.bot.db.get_game_setting(guild_id, "trivia_clash")
        if not setting or not setting["enabled"]:
            return await interaction.response.send_message("❌ Trivia Clash is disabled.", ephemeral=True)

        channel = interaction.channel
        await interaction.response.send_message(
            f"🧠 {challenger.mention} challenges {opponent.mention} to a **Trivia Clash!**\n"
            f"{opponent.mention}, type `accept` within 30 seconds."
        )

        def accept_check(m):
            return m.author.id == opponent.id and m.channel.id == channel.id and m.content.strip().lower() == "accept"

        try:
            await self.bot.wait_for("message", timeout=30, check=accept_check)
        except asyncio.TimeoutError:
            return await channel.send("⌛ Challenge timed out.")

        ACTIVE_DUELS[guild_id] = {"challenger": challenger.id, "defender": opponent.id, "type": "trivia_clash"}
        chaos = maybe_activate_chaos(guild_id, [challenger.id, opponent.id])

        questions = await fetch_trivia(5)
        scores = {challenger.id: 0, opponent.id: 0}

        for i, q in enumerate(questions):
            question_text = q["question"]
            correct = q["correct_answer"].strip().lower()
            all_answers = [q["correct_answer"]] + q["incorrect_answers"]
            random.shuffle(all_answers)
            options_text = "\n".join(f"**{chr(65+j)}.** {a}" for j, a in enumerate(all_answers))
            correct_letter = chr(65 + all_answers.index(q["correct_answer"]))

            embed = discord.Embed(
                title=f"🧠 Question {i+1}/5",
                description=f"**{question_text}**\n\n{options_text}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Type the letter (A/B/C/D) or full answer. Crowd can watch but not answer!")
            await channel.send(embed=embed)

            responded: dict[int, str] = {}

            def q_check(m):
                return (
                    m.channel.id == channel.id
                    and m.author.id in (challenger.id, opponent.id)
                    and m.author.id not in responded
                )

            q_end = asyncio.get_event_loop().time() + 15
            while len(responded) < 2:
                remaining = q_end - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    msg = await self.bot.wait_for("message", timeout=remaining, check=q_check)
                    responded[msg.author.id] = msg.content.strip()
                except asyncio.TimeoutError:
                    break

            result_lines = []
            for uid, ans in responded.items():
                member = channel.guild.get_member(uid)
                ans_clean = ans.strip().upper()
                if ans_clean == correct_letter or correct in ans.strip().lower():
                    scores[uid] += 1
                    result_lines.append(f"✅ {member.mention} — correct!")
                else:
                    result_lines.append(f"❌ {member.mention} — wrong.")

            await channel.send(
                f"**Answer:** {correct_letter}. {q['correct_answer']}\n" +
                "\n".join(result_lines) +
                f"\nScore: {channel.guild.get_member(challenger.id).display_name} **{scores[challenger.id]}** — "
                f"**{scores[opponent.id]}** {channel.guild.get_member(opponent.id).display_name}"
            )
            await asyncio.sleep(3)

        if scores[challenger.id] > scores[opponent.id]:
            duel_winner, duel_loser = challenger.id, opponent.id
        elif scores[opponent.id] > scores[challenger.id]:
            duel_winner, duel_loser = opponent.id, challenger.id
        else:
            duel_winner = duel_loser = None

        pts = 5 if (chaos.active and chaos.modifier == "double_points") else 4
        if duel_winner:
            self.bot.db.add_points(guild_id, duel_winner, "trivia_clash", pts)
            self.bot.db.record_duel_win(guild_id, duel_winner)
            self.bot.db.record_duel_loss(guild_id, duel_loser)
            w = channel.guild.get_member(duel_winner)
            await channel.send(
                f"🏆 **{w.mention} wins the Trivia Clash {scores[challenger.id]}-{scores[opponent.id]}!** (+{pts} pts)"
            )
        else:
            await channel.send(f"🤝 **It's a tie {scores[challenger.id]}-{scores[opponent.id]}!**")

        ACTIVE_DUELS.pop(guild_id, None)
        clear_chaos(guild_id)


async def setup(bot):
    await bot.add_cog(DuelGames(bot))
