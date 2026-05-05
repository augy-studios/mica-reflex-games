# Mica 🎮

A Discord bot packed with fast-paced minigames, knowledge challenges, multiplayer duels, and unpredictable chaos modifiers. Designed to keep multi-timezone servers engaged around the clock.

Built with [discord.py](https://discordpy.readthedocs.io/) and slash commands. Per-guild configuration stored in JSON — no database required.

---

## Features

### Core Mechanic Games

| Game | Description |
| --- | --- |
| **Drop Zone** | Bot drops a random emoji package. First to react ✅ claims it. |
| **Ghost Hunt** | A ghost 👻 spawns. First to react ⚡ banishes it. |
| **Burst Round** | 60-second race to type a secret word. |
| **Copycat** | Copy an emoji string exactly. Wrong = 30s lockout. |

### Knowledge-Speed Hybrids

| Game | Description |
| --- | --- |
| **Bait and Hook** | Rebut a convincingly wrong "fact". Wrong answers dock points. |
| **Open Bounty** | Persistent trivia question — no timer, first correct wins. Auto-replaces. |
| **Flag Blitz** | Name the country from its flag. Difficulty scales with server accuracy. |
| **Blurred Vision** | Progressive text clues reveal an image subject. Fewer reveals = more points. |

### Reflex & Timing

| Game | Description |
| --- | --- |
| **Don't Touch It** | Bomb with a fuse timer. Last to react before it explodes wins. |
| **Sniper Window** | React within an exact 3-second window. Too early or too late loses. |
| **Echo Chamber** | Wait for 3 others to type the word first. 4th person wins. |
| **Freeze Tag** | Don't type for 10 seconds after FREEZE. Anyone who does loses a point. |

### Multiplayer Duels

| Game | Description |
| --- | --- |
| **Quickdraw** | 3-2-1-DRAW, type `BANG`. Best of 3. |
| **Copycat Duel** | Race to copy increasingly complex emoji sequences. 5 rounds. |
| **Trivia Clash** | 5 rapid-fire questions. Crowd watches, only challenger and defender answer. |

### Chaos Modifiers (random, 20% chance per event)

| Modifier | Effect |
| --- | --- |
| ⚡ Double Points | Next event awards 2× points. No warning until it triggers. |
| 💀 Cursed Round | Rules invert — slowest correct answer wins. |
| 🌫️ Fog of War | No game announcement. Members figure out the rules mid-round. |
| 🎯 Bounty Target | A secret target is chosen. Beat them to earn double points. |

### Leaderboards

- **All-Time** — permanent hall of fame
- **Weekly** — rolling 7-day window, resets automatically
- **Duel Record** — win/loss ratio for 1v1 games
- **Hot Streak** — longest winning streak across any game
- **Cursed Crown** — most penalty points lost

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/reflex-games.git
cd reflex-games
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Set your bot token:
```env
DISCORD_TOKEN=your_bot_token_here
```

### 4. Discord Developer Portal

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Create a new application → Bot
3. Enable the following **Privileged Gateway Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
   - ✅ Presence Intent
4. Copy the token into your `.env`
5. Invite the bot with these scopes: `bot`, `applications.commands`
6. Required permissions: `Send Messages`, `Read Messages/View Channels`, `Add Reactions`, `Embed Links`, `Read Message History`

### 5. Run with tmux

```bash
chmod +x run.sh
./run.sh start
```

Other commands:
```bash
./run.sh stop       # Stop the bot
./run.sh restart    # Restart the bot
./run.sh logs       # Tail the log file
tmux attach -t reflex-games   # Attach to the session
```

---

## Per-Server Configuration

All configuration is per-guild. Nothing is shared between servers.

### Enable/Disable Games

```bash
/reflex enable game:<GameName>       — Enable a specific game
/reflex disable game:<GameName>      — Disable a specific game
/reflex enable_all                   — Enable all games
/reflex disable_all                  — Disable all games
/reflex status                       — View current settings
```

### Set Dedicated Channels

Each game can have its own channel. If not set, events post wherever they're triggered.

```bash
/reflex setchannel game:<GameName> channel:#channel
/reflex clearchannel game:<GameName>
```

### Admin Roles

By default, only members with **Manage Server** can configure the bot. You can grant additional roles:

```bash
/reflex addrole role:@Role
/reflex removerole role:@Role
```

---

## Game Commands

### Manually Trigger Games (Admin or any user for duels)

```bash
/dropzone start
/ghosthunt start
/burst start
/copycat start
/baitandhook start
/bounty start
/flagblitz start
/blurredvision start
/donttouchit start
/sniperwindow start
/echochamber start
/freezetag start
```

### Duel Commands (Any user)

```bash
/quickdraw challenge opponent:@User
/copycatduel challenge opponent:@User
/triviaclash challenge opponent:@User
```

### Chaos Modifiers (Admin)

```bash
/modifier status          — See active modifier
/modifier trigger         — Force-activate a modifier
/modifier clear           — Remove active modifier
/modifier list            — See all modifiers
```

### Leaderboards

```bash
/leaderboard              — All-time points (default)
/leaderboard board:Weekly Points
/leaderboard board:Duel Record
/leaderboard board:Hot Streak
/leaderboard board:Cursed Crown
/stats                    — Your personal stats
/stats member:@User       — Another member's stats
```

---

## File Structure

```bash
reflex-games/
├── bot.py                  # Bot entry point
├── requirements.txt
├── run.sh                  # tmux launcher
├── .env.example
├── .gitignore
├── cogs/
│   ├── admin.py            # /reflex management commands
│   ├── leaderboard.py      # /leaderboard and /stats
│   ├── core_mechanic.py    # Drop Zone, Ghost Hunt, Burst Round, Copycat
│   ├── knowledge_speed.py  # Bait and Hook, Open Bounty, Flag Blitz, Blurred Vision
│   ├── reflex_timing.py    # Don't Touch It, Sniper Window, Echo Chamber, Freeze Tag
│   ├── duels.py            # Quickdraw, Copycat Duel, Trivia Clash
│   └── modifiers.py        # Chaos modifier admin commands
├── utils/
│   ├── config.py           # Per-guild game config (enable/disable, channels)
│   ├── scores.py           # Leaderboard and score management
│   ├── modifiers.py        # Chaos modifier engine
│   └── helpers.py          # Shared embed builder, permission checks
└── data/                   # Generated at runtime (gitignored)
    ├── guilds/             # Per-guild config JSON
    └── scores/             # Per-guild score JSON
```

---

## Extending the Bot

**Adding a new game:**
1. Add its key to `ALL_GAMES` and `GAME_DISPLAY` in `utils/config.py`
2. Create or extend a cog in `cogs/`
3. Use `is_game_enabled()` at the top of your command
4. Use `resolve_channel()` to post to the correct channel
5. Call `roll_modifier()` at event start; `apply_points()` when awarding; `consume_modifier()` after
6. Load the cog in `COGS` in `bot.py`

**Persistence:**
Data is stored as JSON in `data/`. For high-traffic servers, swapping `utils/scores.py` for a SQLite or Supabase backend is straightforward — the public API surface stays the same.

---

## Logs

The bot logs to both stdout and `reflex.log` in the project root. Use `./run.sh logs` or `tail -f reflex.log` to monitor.

---

## License

MIT
