# Mica ⚡

A Discord bot for reflex games. Mica spontaneously triggers a suite of reflex, knowledge, and timing games across your server — with chaos modifiers that keep things unpredictable. Designed for public multi-guild deployment.

---

## Features

### Core Mechanic Games

| Game | Description |
| --- | --- |
| **Drop Zone** | A package drops. First to react with ✅ claims it. |
| **Ghost Hunt** | A ghost 👻 spawns. First to react with ⚡ banishes it. Streaks tracked. |
| **Burst Round** | A 60-second free-for-all — type the secret word to win. |
| **Copycat** | Copy a random string/emoji sequence exactly. Wrong answer = 30s lockout. |

### Knowledge-Speed Hybrids

| Game | Description |
| --- | --- |
| **Bait and Hook** | A convincingly wrong "fact" is posted. First correct rebuttal wins. Wrong answers dock points. |
| **Open Bounty** | A trivia question stays live until answered. First correct answer wins; new question immediately replaces it. |
| **Flag Blitz** | A flag is posted. First to name the country wins. Difficulty scales with collective server accuracy. |
| **Blurred Vision** | A question is obscured and progressively revealed every 15s. Fewer reveals used = more points. |

### Reflex & Timing

| Game | Description |
| --- | --- |
| **Don't Touch It** | A bomb 💣 with a random fuse. Last to react before explosion wins. Early reactors lose points. |
| **Sniper Window** | React with 🎯 within an exact 3-second window. Tests precision, not just speed. |
| **Echo Chamber** | A word is posted. Wait for 2 others to type it first — the 4th person wins. |
| **Freeze Tag** | Bot posts FREEZE. Anyone who types in the next 10 seconds loses a point. |

### Multiplayer Duels

| Game | Description |
| --- | --- |
| **Quickdraw** | 1v1 duel. First to type `BANG` on `DRAW!` wins. Best of 3. |
| **Copycat Duel** | Race to copy increasingly complex emoji sequences. 5 rounds. |
| **Trivia Clash** | 5 rapid-fire trivia questions. Crowd can watch; only challengers answer. |

### Chaos Modifiers (activate randomly ~20% of the time)

| Modifier | Effect |
| --- | --- |
| **Double Points** | Next event awards 2× points. No warning until it fires. |
| **Cursed Round** | Rules invert — slowest correct answer wins. |
| **Fog of War** | Game type not announced. Members deduce rules mid-round. |
| **Bounty Target** | A secret target is chosen. Beating them specifically awards double points. |

### Leaderboards

- `/lb alltime` — permanent hall of fame
- `/lb weekly` — rolling 7-day window
- `/lb duels` — win/loss ratio board
- `/lb streaks` — current hot streaks
- `/lb cursed` — most points lost to penalties (Cursed Crown)
- `/lb score` — your personal stats

---

## Setup

### Prerequisites
- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))

### Installation

```bash
git clone https://github.com/your-username/mica-bot.git
cd mica-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and paste your bot token
```

### Running (tmux recommended)

```bash
tmux new-session -s mica
source venv/bin/activate
python bot.py
# Detach: Ctrl+B, D
# Reattach: tmux attach -t mica
```

### Discord Bot Permissions

When generating your invite URL, enable the following:
- **Bot Scopes:** `bot`, `applications.commands`
- **Bot Permissions:** `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, `View Channel`
- **Privileged Gateway Intents:** `Message Content Intent`, `Server Members Intent`

---

## Configuration (per server)

All configuration is done via slash commands. You need **Manage Server** or **Administrator** permission.

```bash
/games status           — View all games and their enabled/channel status
/games enable           — Enable a game
/games disable          — Disable a game
/games setchannel       — Set which channel a game triggers in
/games clearchannel     — Remove custom channel (falls back to first available)
/games enableall        — Enable all games
/games disableall       — Disable all games
```

All games are **disabled by default** on a new server. Enable them individually or use `/games enableall`.

---

## Admin Manual Triggers (for testing)

```bash
/trigger dropzone       — Trigger Drop Zone now
/trigger ghosthunt      — Trigger Ghost Hunt now
/trigger burst          — Trigger Burst Round now
/trigger copycat        — Trigger Copycat now

/ktrigger bait          — Trigger Bait and Hook now
/ktrigger bounty        — Trigger Open Bounty now
/ktrigger flag          — Trigger Flag Blitz now
/ktrigger blurred       — Trigger Blurred Vision now

/rtrigger bomb          — Trigger Don't Touch It now
/rtrigger sniper        — Trigger Sniper Window now
/rtrigger echo          — Trigger Echo Chamber now
/rtrigger freeze        — Trigger Freeze Tag now
```

---

## Duel Commands (any member)

```bash
/quickdraw @user        — Challenge to Quickdraw
/copycatduel @user      — Challenge to Copycat Duel
/triviaclash @user      — Challenge to Trivia Clash
```

---

## Other Commands

```bash
/chaos                  — Learn about chaos modifiers
/activechaos            — See if a modifier is currently live
```

---

## External APIs Used

All APIs are free and open, no keys required:

| API | Used For |
| --- | --- |
| [Open Trivia DB](https://opentdb.com) | Trivia questions (Open Bounty, Trivia Clash, Bait & Hook, Blurred Vision) |
| [REST Countries](https://restcountries.com) | Flag emoji + country names (Flag Blitz) |

Mica gracefully falls back to hardcoded data if these APIs are unavailable.

---

## Project Structure

```bash
mica-bot/
├── bot.py                  # Entry point
├── database.py             # SQLite schema + all DB helpers
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── cogs/
│   ├── admin.py            # /games commands
│   ├── leaderboard.py      # /lb commands
│   ├── core_games.py       # Drop Zone, Ghost Hunt, Burst Round, Copycat
│   ├── knowledge_games.py  # Bait & Hook, Open Bounty, Flag Blitz, Blurred Vision
│   ├── reflex_games.py     # Don't Touch It, Sniper Window, Echo Chamber, Freeze Tag
│   ├── duel_games.py       # Quickdraw, Copycat Duel, Trivia Clash
│   ├── chaos.py            # /chaos and /activechaos
│   └── events.py           # on_message router, on_guild_join welcome
└── utils/
    ├── scheduler.py        # SQLite-backed random game scheduler
    ├── chaos.py            # Chaos modifier state + logic
    └── api_helpers.py      # External API calls + fallbacks
```

---

## Database

Uses SQLite (`mica.db`, auto-created on first run). WAL mode enabled for concurrent reads. No external DB required.

Tables: `guilds`, `game_settings`, `scores`, `streaks`, `penalties`, `duel_records`, `open_bounties`, `active_games`, `scheduled_events`, `flag_blitz_stats`, `copycat_lockouts`

---

## Scheduling

Games trigger at randomised intervals per guild using a SQLite-backed scheduler (polling every 10 seconds). No `apscheduler` or `celery` required.

Default interval ranges (adjustable in `utils/scheduler.py`):

| Game | Min | Max |
| --- | --- | --- |
| Drop Zone | 2 min | 10 min |
| Ghost Hunt | 3 min | 15 min |
| Burst Round | 5 min | 20 min |
| Freeze Tag | 2 min | 10 min |
| Flag Blitz | 5 min | 15 min |
| Blurred Vision | 10 min | 30 min |
| Open Bounty | 10 min | 60 min |
| ...and more | varies | varies |

---

## License

MIT
