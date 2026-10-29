"""Load, validate and enrich the YouTube-style video dataset.

The loader never silently drops information: every repair it makes (for example
removing a row with a negative view count) is returned to the caller as a
human-readable warning so the dashboard can show it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "youtube_videos.csv"

REQUIRED_COLUMNS: tuple[str, ...] = (
    "video_id",
    "title",
    "channel_name",
    "published_at",
    "duration_minutes",
    "views",
    "likes",
    "comments",
    "topic",
    "tags",
)
OPTIONAL_COLUMNS: tuple[str, ...] = ("description", "video_url")
SIMULATED_TRAFFIC_COLUMNS: tuple[str, ...] = (
    "sim_search_pct",
    "sim_suggested_pct",
    "sim_direct_pct",
    "sim_external_pct",
)
COUNT_COLUMNS: tuple[str, ...] = ("views", "likes", "comments")

# Metrics such as "views per day" need a reference ("today") date. A fixed date
# keeps the demo reproducible. Change it here or pass `reference_date=` to
# `load_videos` to measure ages from another day.
DEFAULT_REFERENCE_DATE = pd.Timestamp("2026-10-28")
# A video published today would have age 0 days; dividing by zero is avoided by
# never using an age smaller than this many days.
MIN_AGE_DAYS = 1

DataSource = Union[str, Path, IO[bytes], IO[str]]


class DataValidationError(ValueError):
    """Raised when the dataset cannot be used at all (not just repaired)."""


@dataclass
class LoadResult:
    """Cleaned data plus everything the user should know about how it was cleaned."""

    data: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    rows_read: int = 0

    @property
    def rows_kept(self) -> int:
        return len(self.data)


def normalize_tags(raw: object) -> list[str]:
    """Turn ``"AI; Python ;ai"`` into ``["ai", "python"]``.

    Tags are lower-cased, trimmed, de-duplicated (keeping first occurrence) and
    empty/missing values become an empty list.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)) or raw is pd.NA:
        return []
    seen: dict[str, None] = {}
    for part in str(raw).split(";"):
        tag = " ".join(part.strip().lower().split())
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


def compute_derived_metrics(
    df: pd.DataFrame, reference_date: pd.Timestamp = DEFAULT_REFERENCE_DATE
) -> pd.DataFrame:
    """Add engagement, rate and age based columns without any divide-by-zero.

    * ``engagement_rate = (likes + comments) / views * 100`` (0 when views = 0)
    * ``like_rate`` and ``comment_rate`` use the same safe division
    * ``age_days`` = days between publication and ``reference_date`` (at least 1)
    * ``views_per_day = views / age_days``
    """
    out = df.copy()
    views = out["views"].astype(float)
    safe_views = views.where(views > 0, np.nan)
    out["engagement_rate"] = ((out["likes"] + out["comments"]) / safe_views * 100).fillna(0.0)
    out["like_rate"] = (out["likes"] / safe_views * 100).fillna(0.0)
    out["comment_rate"] = (out["comments"] / safe_views * 100).fillna(0.0)
    age = (pd.Timestamp(reference_date) - out["published_at"]).dt.days
    out["age_days"] = age.clip(lower=MIN_AGE_DAYS).astype(int)
    out["views_per_day"] = out["views"] / out["age_days"]
    return out


def validate_and_clean(
    raw: pd.DataFrame, reference_date: pd.Timestamp = DEFAULT_REFERENCE_DATE
) -> LoadResult:
    """Validate a raw dataframe and return a cleaned, enriched copy.

    Fatal problems raise :class:`DataValidationError`:
      * missing required columns, an empty file, or duplicate ``video_id`` values.

    Repairable problems become warnings and the affected rows are dropped:
      * blank id/title/channel/topic, invalid dates, or non-numeric/negative counts.
    Missing tags are allowed (the video simply has no tag edges).
    """
    if raw is None or raw.empty:
        raise DataValidationError("The dataset is empty. Add at least one video row.")

    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            "Missing required column(s): " + ", ".join(missing)
            + ". Required columns are: " + ", ".join(REQUIRED_COLUMNS) + "."
        )

    warnings: list[str] = []
    rows_read = len(df)

    for col in ("video_id", "title", "channel_name", "topic"):
        df[col] = df[col].astype("string").str.strip()

    # Fatal: duplicate ids would make graph nodes ambiguous.
    non_blank_ids = df["video_id"].dropna()
    non_blank_ids = non_blank_ids[non_blank_ids != ""]
    duplicated = sorted(non_blank_ids[non_blank_ids.duplicated()].unique())
    if duplicated:
        shown = ", ".join(duplicated[:5]) + (" ..." if len(duplicated) > 5 else "")
        raise DataValidationError(f"Duplicate video_id values found: {shown}. Every id must be unique.")

    def drop_rows(frame: pd.DataFrame, mask: pd.Series, reason: str) -> pd.DataFrame:
        count = int(mask.sum())
        if count:
            warnings.append(f"Removed {count} row(s) with {reason}.")
            logger.warning("Removed %d row(s): %s", count, reason)
            return frame.loc[~mask].copy()
        return frame

    for col, label in (
        ("video_id", "a blank video_id"),
        ("title", "a blank title"),
        ("channel_name", "a blank channel_name"),
        ("topic", "a blank topic"),
    ):
        df = drop_rows(df, df[col].isna() | (df[col] == ""), label)

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df = drop_rows(df, df["published_at"].isna(), "an invalid or missing published_at date")

    for col in (*COUNT_COLUMNS, "duration_minutes"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad_numeric = df[list(COUNT_COLUMNS)].isna().any(axis=1) | df["duration_minutes"].isna()
    df = drop_rows(df, bad_numeric, "non-numeric views, likes, comments or duration_minutes")
    negative = (df[list(COUNT_COLUMNS)] < 0).any(axis=1) | (df["duration_minutes"] < 0)
    df = drop_rows(df, negative, "negative counts or duration")

    if df.empty:
        raise DataValidationError(
            "No valid rows remain after cleaning. Check the warnings above and your CSV."
        )

    for col in COUNT_COLUMNS:
        df[col] = df[col].round().astype("int64")
    df["duration_minutes"] = df["duration_minutes"].astype(float)

    # Plain Python strings keep downstream code (networkx, plotly) simple.
    for col in ("video_id", "title", "channel_name", "topic"):
        df[col] = df[col].astype(str)

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df["tags_list"] = df["tags"].apply(normalize_tags)
    no_tags = int((df["tags_list"].str.len() == 0).sum())
    if no_tags:
        warnings.append(
            f"{no_tags} video(s) have no tags, so they cannot be connected to other videos."
        )

    odd_engagement = int(((df["likes"] + df["comments"]) > df["views"]).sum())
    if odd_engagement:
        warnings.append(
            f"{odd_engagement} video(s) have likes + comments larger than views "
            "(engagement above 100%). They were kept - please double-check the source data."
        )

    for col in SIMULATED_TRAFFIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("video_id").reset_index(drop=True)
    df = compute_derived_metrics(df, reference_date)
    return LoadResult(data=df, warnings=warnings, rows_read=rows_read)


def load_videos(
    source: DataSource = DEFAULT_DATA_PATH,
    reference_date: pd.Timestamp = DEFAULT_REFERENCE_DATE,
) -> LoadResult:
    """Read a CSV from a path or an uploaded file object, then validate it."""
    try:
        raw = pd.read_csv(source)
    except FileNotFoundError as exc:
        raise DataValidationError(
            f"Could not find the data file: {source}. Make sure you run the app from the "
            "project folder and that data/youtube_videos.csv exists."
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError("The CSV file is empty.") from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"The CSV file could not be parsed: {exc}") from exc
    return validate_and_clean(raw, reference_date)


def has_simulated_traffic(df: pd.DataFrame) -> bool:
    """True when the demo (simulated) traffic-source columns exist and hold numbers."""
    if not all(c in df.columns for c in SIMULATED_TRAFFIC_COLUMNS):
        return False
    return not df[list(SIMULATED_TRAFFIC_COLUMNS)].isna().all().any()
