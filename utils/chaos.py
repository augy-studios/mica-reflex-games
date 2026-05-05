import random
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("mica.chaos")

CHAOS_MODIFIERS = [
    "double_points",
    "cursed_round",
    "fog_of_war",
    "bounty_target",
]

# Probability that a chaos modifier activates for any given game trigger
CHAOS_CHANCE = 0.20


@dataclass
class ChaosState:
    modifier: Optional[str] = None
    target_user_id: Optional[int] = None
    active: bool = False

    def describe(self) -> str:
        descriptions = {
            "double_points": "⚡ **DOUBLE POINTS** — This round counts for double!",
            "cursed_round":  "💀 **CURSED ROUND** — Rules are inverted. Slowest correct answer wins!",
            "fog_of_war":    "🌫️ **FOG OF WAR** — Figure out the rules yourself...",
            "bounty_target": "🎯 **BOUNTY TARGET** — Someone in this server is the secret target. Beat them for double points!",
        }
        return descriptions.get(self.modifier, "")


# Per-guild in-memory chaos state
_guild_chaos: dict[int, ChaosState] = {}


def maybe_activate_chaos(guild_id: int, members: list[int] = None) -> ChaosState:
    """Roll dice for a chaos modifier. Returns ChaosState (may be inactive)."""
    if random.random() > CHAOS_CHANCE:
        state = ChaosState()
    else:
        modifier = random.choice(CHAOS_MODIFIERS)
        target = None
        if modifier == "bounty_target" and members:
            target = random.choice(members)
        state = ChaosState(modifier=modifier, target_user_id=target, active=True)
        logger.info(f"Chaos activated for guild {guild_id}: {modifier}")
    _guild_chaos[guild_id] = state
    return state


def get_chaos(guild_id: int) -> ChaosState:
    return _guild_chaos.get(guild_id, ChaosState())


def clear_chaos(guild_id: int):
    _guild_chaos.pop(guild_id, None)


def apply_chaos_points(guild_id: int, base_points: int, user_id: int) -> int:
    """Apply chaos modifier to points calculation."""
    state = get_chaos(guild_id)
    if not state.active:
        return base_points
    if state.modifier == "double_points":
        return base_points * 2
    if state.modifier == "bounty_target":
        # Caller must pass the original winner; if target was beaten, doubled
        # This is handled in game logic — just pass through here
        return base_points
    return base_points


def is_cursed(guild_id: int) -> bool:
    return get_chaos(guild_id).modifier == "cursed_round"


def is_fog(guild_id: int) -> bool:
    return get_chaos(guild_id).modifier == "fog_of_war"


def get_bounty_target(guild_id: int) -> Optional[int]:
    state = get_chaos(guild_id)
    if state.modifier == "bounty_target":
        return state.target_user_id
    return None
