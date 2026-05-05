"""
External API helpers — all open / free, no keys required.

Sources:
  - Open Trivia DB (opentdb.com) — trivia questions
  - REST Countries (restcountries.com) — flag emoji + country data
  - Numbers API (numbersapi.com) — numeric facts for Bait & Hook
"""

import asyncio
import html
import logging
import random
import re
import aiohttp

logger = logging.getLogger("mica.api")

TRIVIA_URL  = "https://opentdb.com/api.php"
COUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,flags,cca2,region"
NUMBERS_URL = "http://numbersapi.com/random/trivia?json"


async def fetch_trivia(amount: int = 1, difficulty: str = None) -> list[dict]:
    """
    Returns list of dicts:
      { question, correct_answer, incorrect_answers, category, difficulty }
    Falls back to hardcoded list on API error.
    """
    params = {"amount": amount, "type": "multiple"}
    if difficulty:
        params["difficulty"] = difficulty
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TRIVIA_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
                if data.get("response_code") == 0:
                    results = []
                    for item in data["results"]:
                        results.append({
                            "question": html.unescape(item["question"]),
                            "correct_answer": html.unescape(item["correct_answer"]),
                            "incorrect_answers": [html.unescape(a) for a in item["incorrect_answers"]],
                            "category": item.get("category", "General"),
                            "difficulty": item.get("difficulty", "medium"),
                        })
                    return results
    except Exception as e:
        logger.warning(f"Trivia API error: {e}")
    return _fallback_trivia(amount)


async def fetch_countries() -> list[dict]:
    """
    Returns list of dicts: { name, flag_emoji, code, region }
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COUNTRIES_URL, timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
                countries = []
                for c in data:
                    name = c.get("name", {}).get("common", "")
                    flag = c.get("flags", {}).get("emoji", "🏳️")
                    code = c.get("cca2", "")
                    region = c.get("region", "")
                    if name and flag:
                        countries.append({
                            "name": name,
                            "flag": flag,
                            "code": code,
                            "region": region,
                        })
                return countries
    except Exception as e:
        logger.warning(f"Countries API error: {e}")
        return _fallback_countries()


async def fetch_bait_fact() -> dict:
    """
    Returns a dict: { statement, is_wrong, correct_form }
    For Bait and Hook — a plausibly wrong "fact" and the correction.
    Uses trivia questions inverted.
    """
    try:
        items = await fetch_trivia(1)
        item = items[0]
        wrong = random.choice(item["incorrect_answers"])
        return {
            "statement": item["question"].replace("?", "") + f" — {wrong}.",
            "correct_answer": item["correct_answer"],
            "wrong_claim": wrong,
        }
    except Exception as e:
        logger.warning(f"Bait fact error: {e}")
        return {
            "statement": "The Great Wall of China is visible from the Moon.",
            "correct_answer": "It is not visible from the Moon with the naked eye.",
            "wrong_claim": "It is visible from the Moon",
        }


def _fallback_trivia(amount: int) -> list[dict]:
    pool = [
        {
            "question": "What is the capital of Australia?",
            "correct_answer": "Canberra",
            "incorrect_answers": ["Sydney", "Melbourne", "Brisbane"],
            "category": "Geography", "difficulty": "medium",
        },
        {
            "question": "How many sides does a hexagon have?",
            "correct_answer": "6",
            "incorrect_answers": ["5", "7", "8"],
            "category": "Mathematics", "difficulty": "easy",
        },
        {
            "question": "What element has the chemical symbol 'Au'?",
            "correct_answer": "Gold",
            "incorrect_answers": ["Silver", "Argon", "Aluminium"],
            "category": "Science", "difficulty": "medium",
        },
        {
            "question": "Who painted the Mona Lisa?",
            "correct_answer": "Leonardo da Vinci",
            "incorrect_answers": ["Michelangelo", "Raphael", "Donatello"],
            "category": "Art", "difficulty": "easy",
        },
    ]
    return random.sample(pool, min(amount, len(pool)))


def _fallback_countries() -> list[dict]:
    return [
        {"name": "Singapore", "flag": "🇸🇬", "code": "SG", "region": "Asia"},
        {"name": "Japan",     "flag": "🇯🇵", "code": "JP", "region": "Asia"},
        {"name": "France",    "flag": "🇫🇷", "code": "FR", "region": "Europe"},
        {"name": "Brazil",    "flag": "🇧🇷", "code": "BR", "region": "Americas"},
        {"name": "Canada",    "flag": "🇨🇦", "code": "CA", "region": "Americas"},
        {"name": "Nigeria",   "flag": "🇳🇬", "code": "NG", "region": "Africa"},
    ]


def pick_flag_by_difficulty(countries: list[dict], accuracy: float) -> dict:
    """
    Selects a country appropriate to the server's collective accuracy.
    Low accuracy → common countries; high accuracy → rarer ones.
    """
    common = ["US", "GB", "JP", "FR", "DE", "BR", "CA", "AU", "IN", "CN",
              "SG", "KR", "MX", "IT", "ES", "RU", "ZA", "AR", "NG", "EG"]
    if accuracy < 0.4:
        pool = [c for c in countries if c["code"] in common]
    elif accuracy < 0.7:
        pool = countries  # full pool, medium difficulty
    else:
        pool = [c for c in countries if c["code"] not in common]
    return random.choice(pool or countries)


def generate_random_string(length: int = 8, use_emoji: bool = False) -> str:
    """Generate a random string or emoji sequence for Copycat."""
    if use_emoji:
        pool = ["😀", "🎮", "🔥", "💎", "🌊", "⚡", "🎯", "🦊", "🌙", "🍀",
                "🎲", "🔮", "🎪", "🦋", "🌺", "🎸", "🏆", "🎭", "🦁", "🌈"]
        k = random.randint(4, 7)
        return " ".join(random.choices(pool, k=k))
    else:
        import string
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))


SECRET_WORDS = [
    "reflex", "blazing", "nimble", "zephyr", "quartz", "puzzle", "voltage",
    "cobalt", "vector", "prism", "cipher", "zenith", "glitch", "turbo",
    "flux", "mirage", "nexus", "ozone", "ripple", "static",
]


def pick_secret_word() -> str:
    return random.choice(SECRET_WORDS)
