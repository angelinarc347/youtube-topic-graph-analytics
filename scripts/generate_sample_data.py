"""Generate the SYNTHETIC demo dataset ``data/youtube_videos.csv``.

Everything produced here is invented: channel names, titles, counts and the
"sim_*" traffic-source columns. None of it comes from YouTube. The generator is
deterministic (fixed random seed), so running it again recreates the same file.

Usage (from the project root):
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

from pathlib import Path

import re

import numpy as np
import pandas as pd

SEED = 42
REFERENCE_DATE = pd.Timestamp("2026-10-28")
START_DATE = pd.Timestamp("2024-01-05")
END_DATE = pd.Timestamp("2026-10-15")
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "youtube_videos.csv"

# --------------------------------------------------------------------------
# Topic definitions: tag vocabulary, channels, title patterns, typical metrics
# --------------------------------------------------------------------------
TOPICS: dict[str, dict] = {
    "Technology & AI": {
        "count": 20,
        "tags": ["ai", "machine learning", "python", "neural networks", "data science",
                 "programming", "cloud computing", "cybersecurity", "automation",
                 "robotics", "open source", "gadgets"],
        "channels": ["CircuitCraft Lab", "Neural Notes"],
        "patterns": ["{t} explained for beginners", "How {t} is changing everyday work",
                     "Hands-on project: {t} from scratch", "{t}: myths vs reality",
                     "Weekly tech roundup: {t} edition", "Build it yourself: {t} workshop"],
        "views_median": 52000, "like_rate": (2.8, 5.5), "comment_rate": (0.15, 0.45),
        "duration": (8, 28), "traffic": (46, 24, 18, 12),
    },
    "Gaming": {
        "count": 20,
        "tags": ["gaming", "walkthrough", "esports", "indie games", "speedrun",
                 "game review", "multiplayer", "strategy", "retro games",
                 "streaming setup", "game design", "controller tips"],
        "channels": ["PixelQuest Hub", "Respawn Daily"],
        "patterns": ["{t}: full session highlights", "Ranking the best {t} moments",
                     "{t} deep dive and honest verdict", "I tried {t} for a whole week",
                     "{t} masterclass: what pros do differently", "Live recap: {t} night"],
        "views_median": 98000, "like_rate": (2.0, 4.2), "comment_rate": (0.10, 0.35),
        "duration": (14, 55), "traffic": (18, 52, 14, 16),
    },
    "Education": {
        "count": 20,
        "tags": ["study tips", "mathematics", "physics", "exam prep", "online learning",
                 "productivity", "science", "history", "language learning", "lecture",
                 "note taking", "career advice"],
        "channels": ["Campus Clarity", "StudyForge"],
        "patterns": ["{t} made simple", "The only {t} guide you need",
                     "{t} in 20 minutes: lecture and examples", "Common {t} mistakes students make",
                     "Revision sprint: {t}", "{t} for busy people"],
        "views_median": 41000, "like_rate": (4.0, 7.5), "comment_rate": (0.30, 0.80),
        "duration": (10, 45), "traffic": (58, 18, 14, 10),
    },
    "Cooking": {
        "count": 20,
        "tags": ["recipes", "baking", "vegetarian", "meal prep", "street food",
                 "desserts", "kitchen tips", "spices", "healthy eating",
                 "breakfast", "quick meals", "regional cuisine"],
        "channels": ["Saffron & Salt", "Crumb Theory"],
        "patterns": ["{t}: step by step in my kitchen", "Five easy ideas for {t}",
                     "Perfecting {t} at home", "{t} on a budget", "Grandma-style {t} (tested)",
                     "{t} you can finish in 30 minutes"],
        "views_median": 67000, "like_rate": (3.5, 6.5), "comment_rate": (0.20, 0.55),
        "duration": (6, 22), "traffic": (52, 22, 12, 14),
    },
    "Travel": {
        "count": 20,
        "tags": ["travel vlog", "budget travel", "hiking", "city guide", "road trip",
                 "solo travel", "photography", "beaches", "itinerary", "backpacking",
                 "culture", "local food"],
        "channels": ["Wayfarer Weekly", "Trailhead Tales"],
        "patterns": ["{t}: our honest experience", "A first-timer's guide to {t}",
                     "{t} for under a tight budget", "Hidden gems: {t} edition",
                     "{t} diary - what nobody tells you", "Planning {t}: itinerary and costs"],
        "views_median": 59000, "like_rate": (3.0, 5.8), "comment_rate": (0.18, 0.50),
        "duration": (10, 32), "traffic": (36, 30, 14, 20),
    },
    "Fitness": {
        "count": 20,
        "tags": ["workout", "yoga", "strength training", "running", "nutrition",
                 "home workout", "mobility", "weight loss", "recovery",
                 "mindfulness", "stretching", "gym basics"],
        "channels": ["IronPulse Fitness", "Mindful Motion"],
        "patterns": ["{t}: a 20 minute routine", "Beginner's plan for {t}",
                     "{t} mistakes to stop making", "30 days of {t}: what changed",
                     "Follow-along {t} session", "{t} explained by a coach"],
        "views_median": 48000, "like_rate": (3.2, 6.0), "comment_rate": (0.15, 0.50),
        "duration": (8, 36), "traffic": (34, 36, 16, 14),
    },
    "Entertainment": {
        "count": 18,
        "tags": ["movie review", "music", "comedy", "behind the scenes", "reaction",
                 "trailers", "stand-up", "short films", "podcast", "pop culture",
                 "streaming shows", "fan theories"],
        "channels": ["Reel Takes", "Laugh Track Lab"],
        "patterns": ["{t}: unfiltered thoughts", "Ranking every {t} moment",
                     "{t} - the full breakdown", "We watched {t} so you do not have to",
                     "Late night {t} special", "{t}: what the critics missed"],
        "views_median": 120000, "like_rate": (2.4, 5.0), "comment_rate": (0.12, 0.40),
        "duration": (5, 40), "traffic": (14, 54, 16, 16),
    },
}

GENERIC_TAGS = ["beginners", "tips", "tutorial", "2026", "review", "vlog", "challenge", "explained"]

# Hand-written cross-topic videos. They deliberately mix tags from two topics so
# that they act as bridges between communities in the graph.
BRIDGES: list[dict] = [
    {"title": "Street food tour: eating our way through a night market", "channel": "Wayfarer Weekly",
     "topic": "Travel", "tags": ["street food", "travel vlog", "local food", "culture", "city guide", "recipes"]},
    {"title": "Meal prep for a week of hard training", "channel": "IronPulse Fitness",
     "topic": "Fitness", "tags": ["meal prep", "nutrition", "workout", "healthy eating", "strength training", "quick meals"]},
    {"title": "Using AI as a study partner: does it help?", "channel": "Neural Notes",
     "topic": "Technology & AI", "tags": ["ai", "study tips", "online learning", "productivity", "machine learning", "exam prep"]},
    {"title": "Turning blockbuster games into movies: what works", "channel": "Reel Takes",
     "topic": "Entertainment", "tags": ["movie review", "gaming", "pop culture", "trailers", "game review", "fan theories"]},
    {"title": "Make a small game with Python in one weekend", "channel": "CircuitCraft Lab",
     "topic": "Technology & AI", "tags": ["python", "programming", "game design", "indie games", "tutorial", "open source"]},
    {"title": "Filming locations you can actually visit", "channel": "Trailhead Tales",
     "topic": "Travel", "tags": ["travel vlog", "movie review", "photography", "city guide", "behind the scenes", "culture"]},
    {"title": "Hiking as a full-body workout", "channel": "Trailhead Tales",
     "topic": "Travel", "tags": ["hiking", "workout", "backpacking", "recovery", "strength training", "beginners"]},
    {"title": "History through the lens of popular films", "channel": "Campus Clarity",
     "topic": "Education", "tags": ["history", "movie review", "lecture", "pop culture", "science", "explained"]},
    {"title": "Wearable gadgets: do they improve your training?", "channel": "CircuitCraft Lab",
     "topic": "Technology & AI", "tags": ["gadgets", "running", "data science", "workout", "automation", "review"]},
    {"title": "The chemistry of baking: why recipes work", "channel": "StudyForge",
     "topic": "Education", "tags": ["science", "baking", "recipes", "kitchen tips", "lecture", "explained"]},
    {"title": "Setting up a streaming rig on a student budget", "channel": "Respawn Daily",
     "topic": "Gaming", "tags": ["streaming setup", "gadgets", "gaming", "budget travel", "tutorial", "tips"]},
    {"title": "Learning a language by cooking regional dishes", "channel": "Saffron & Salt",
     "topic": "Cooking", "tags": ["language learning", "regional cuisine", "recipes", "culture", "study tips", "spices"]},
]

# Rough traffic-share profile per video is drawn around the topic mean, with noise.
SIM_COLUMNS = ["sim_search_pct", "sim_suggested_pct", "sim_direct_pct", "sim_external_pct"]


def _pretty(tag: str) -> str:
    """Title-case a tag for use inside a video title ("ai" becomes "AI")."""
    return re.sub(r"\bAi\b", "AI", tag.title())


def _weighted_sample(rng: np.random.Generator, vocab: list[str], k: int) -> list[str]:
    """Sample k distinct tags with Zipf-like weights so some tags become hubs."""
    weights = 1.0 / (np.arange(len(vocab)) + 1.0) ** 0.7
    weights /= weights.sum()
    idx = rng.choice(len(vocab), size=k, replace=False, p=weights)
    return [vocab[i] for i in idx]


def _metrics(rng: np.random.Generator, spec: dict, published: pd.Timestamp, channel_boost: float) -> dict:
    """Invent plausible counts. Older videos have had longer to collect views."""
    age_days = max((REFERENCE_DATE - published).days, 1)
    age_factor = 0.25 + 0.75 * min(age_days / 540.0, 1.0)
    views = rng.lognormal(mean=np.log(spec["views_median"]), sigma=0.7) * channel_boost * age_factor
    if rng.random() < 0.05:  # a few "viral" outliers
        views *= rng.uniform(4, 9)
    views = int(max(views, 300))
    like_rate = rng.uniform(*spec["like_rate"]) / 100
    comment_rate = rng.uniform(*spec["comment_rate"]) / 100
    return {
        "views": views,
        "likes": int(views * like_rate),
        "comments": int(views * comment_rate),
        "duration_minutes": round(float(rng.uniform(*spec["duration"])), 1),
    }


def _traffic(rng: np.random.Generator, base: tuple[int, int, int, int]) -> list[float]:
    """Four percentages that add up to exactly 100 (SIMULATED, not real data)."""
    draw = rng.dirichlet(np.array(base, dtype=float) * 12)
    pct = np.round(draw * 100, 1)
    pct[-1] = round(100 - pct[:-1].sum(), 1)
    return [float(x) for x in pct]


def build_dataset() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    used_titles: set[str] = set()
    channel_boost = {c: float(rng.uniform(0.7, 1.5)) for spec in TOPICS.values() for c in spec["channels"]}

    def random_date() -> pd.Timestamp:
        span = (END_DATE - START_DATE).days
        return START_DATE + pd.Timedelta(days=int(rng.integers(0, span + 1)))

    def unique_title(title: str) -> str:
        candidate, part = title, 2
        while candidate in used_titles:
            candidate = f"{title} (Part {part})"
            part += 1
        used_titles.add(candidate)
        return candidate

    for topic, spec in TOPICS.items():
        for _ in range(spec["count"]):
            n_topic_tags = int(rng.integers(3, 6))
            tags = _weighted_sample(rng, spec["tags"], n_topic_tags)
            n_generic = int(rng.choice([0, 1, 2], p=[0.45, 0.4, 0.15]))
            if n_generic:
                tags += list(rng.choice(GENERIC_TAGS, size=n_generic, replace=False))
            channel = str(rng.choice(spec["channels"]))
            pattern = str(rng.choice(spec["patterns"]))
            title = unique_title(pattern.format(t=_pretty(tags[0])))
            published = random_date()
            row = {"title": title, "channel_name": channel, "topic": topic, "tags": tags,
                   "published_at": published}
            row.update(_metrics(rng, spec, published, channel_boost[channel]))
            row.update(dict(zip(SIM_COLUMNS, _traffic(rng, spec["traffic"]))))
            rows.append(row)

    for bridge in BRIDGES:
        spec = TOPICS[bridge["topic"]]
        published = random_date()
        row = {"title": unique_title(bridge["title"]), "channel_name": bridge["channel"],
               "topic": bridge["topic"], "tags": list(bridge["tags"]), "published_at": published}
        row.update(_metrics(rng, spec, published, channel_boost.get(bridge["channel"], 1.0)))
        row.update(dict(zip(SIM_COLUMNS, _traffic(rng, spec["traffic"]))))
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("published_at", kind="stable").reset_index(drop=True)
    df.insert(0, "video_id", [f"DEMO{i:03d}" for i in range(1, len(df) + 1)])
    df["published_at"] = df["published_at"].dt.strftime("%Y-%m-%d")
    df["tags"] = df["tags"].apply(lambda t: ";".join(t))
    df["description"] = [
        f"Demo description (synthetic data): a {r.topic.lower()} video about "
        f"{r.tags.split(';')[0]} and {r.tags.split(';')[1] if ';' in r.tags else 'related ideas'}."
        for r in df.itertuples()
    ]
    df["video_url"] = ""  # intentionally blank: these videos do not exist on YouTube
    columns = ["video_id", "title", "channel_name", "published_at", "duration_minutes",
               "views", "likes", "comments", "topic", "tags", "description", "video_url", *SIM_COLUMNS]
    return df[columns]


def main() -> None:
    df = build_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} synthetic videos to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
