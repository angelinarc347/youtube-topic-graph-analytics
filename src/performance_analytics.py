"""Video performance analytics (views, engagement, topics, channels, keywords)."""

from __future__ import annotations

import pandas as pd

from src.data_loader import SIMULATED_TRAFFIC_COLUMNS

TOP_METRICS: dict[str, str] = {
    "Views": "views",
    "Likes": "likes",
    "Comments": "comments",
    "Engagement rate (%)": "engagement_rate",
    "Views per day": "views_per_day",
}
CORRELATION_COLUMNS = ["views", "likes", "comments", "duration_minutes", "engagement_rate"]
STRUCTURE_COLUMNS = ["degree", "closeness", "betweenness", "eigenvector", "pagerank"]
PERFORMANCE_COLUMNS = ["views", "engagement_rate", "views_per_day"]


def overview_kpis(videos: pd.DataFrame, edge_count: int, community_count: int) -> dict[str, float | int]:
    """Headline numbers for the KPI cards."""
    if videos.empty:
        return {"videos": 0, "edges": edge_count, "communities": community_count,
                "total_views": 0, "avg_engagement": 0.0}
    return {
        "videos": int(len(videos)),
        "edges": int(edge_count),
        "communities": int(community_count),
        "total_views": int(videos["views"].sum()),
        "avg_engagement": float(videos["engagement_rate"].mean()),
    }


def top_videos(videos: pd.DataFrame, metric: str, n: int = 10) -> pd.DataFrame:
    """The ``n`` best videos by one metric column (ties broken by views)."""
    if metric not in videos.columns:
        raise KeyError(f"Unknown metric column: {metric}")
    cols = ["video_id", "title", "channel_name", "topic", "views", "likes", "comments",
            "engagement_rate", "views_per_day"]
    ranked = videos.sort_values([metric, "views"], ascending=False).head(n)
    return ranked[cols].reset_index(drop=True)


def summarise_by(videos: pd.DataFrame, column: str) -> pd.DataFrame:
    """Video count, total/average views and mean engagement for each value of ``column``."""
    if videos.empty:
        return pd.DataFrame(columns=[column, "videos", "total_views", "avg_views",
                                     "avg_engagement_rate", "avg_views_per_day"])
    grouped = videos.groupby(column).agg(
        videos=("video_id", "count"),
        total_views=("views", "sum"),
        avg_views=("views", "mean"),
        avg_engagement_rate=("engagement_rate", "mean"),
        avg_views_per_day=("views_per_day", "mean"),
    )
    return grouped.sort_values("total_views", ascending=False).reset_index()


def monthly_timeline(videos: pd.DataFrame) -> pd.DataFrame:
    """Videos published and total views per calendar month."""
    if videos.empty:
        return pd.DataFrame(columns=["month", "videos", "total_views"])
    months = videos["published_at"].dt.to_period("M").dt.to_timestamp()
    out = (
        videos.assign(month=months)
        .groupby("month")
        .agg(videos=("video_id", "count"), total_views=("views", "sum"))
        .reset_index()
    )
    return out


def correlation_matrix(videos: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of the main numeric columns (empty if fewer than 3 videos)."""
    if len(videos) < 3:
        return pd.DataFrame()
    return videos[CORRELATION_COLUMNS].corr(method="pearson")


def keyword_analysis(videos: pd.DataFrame, min_videos: int = 2) -> pd.DataFrame:
    """Tag (keyword) frequency and the average performance of videos that use it.

    Only tags used by at least ``min_videos`` videos are kept, so one-off tags do
    not look more important than they are.
    """
    if videos.empty:
        return pd.DataFrame(columns=["keyword", "videos", "avg_views", "avg_engagement_rate", "topics"])
    exploded = videos[["video_id", "topic", "views", "engagement_rate", "tags_list"]].explode("tags_list")
    exploded = exploded.dropna(subset=["tags_list"]).rename(columns={"tags_list": "keyword"})
    if exploded.empty:
        return pd.DataFrame(columns=["keyword", "videos", "avg_views", "avg_engagement_rate", "topics"])
    table = exploded.groupby("keyword").agg(
        videos=("video_id", "nunique"),
        avg_views=("views", "mean"),
        avg_engagement_rate=("engagement_rate", "mean"),
        topics=("topic", "nunique"),
    )
    table = table[table["videos"] >= min_videos]
    return table.sort_values(["videos", "avg_views"], ascending=False).reset_index()


def simulated_traffic_by_topic(videos: pd.DataFrame) -> pd.DataFrame:
    """View-weighted average of the SIMULATED traffic-source shares for each topic.

    These columns are invented demo values, not real YouTube Analytics data.
    """
    if videos.empty or not all(c in videos.columns for c in SIMULATED_TRAFFIC_COLUMNS):
        return pd.DataFrame()
    rows = []
    for topic, group in videos.groupby("topic"):
        weights = group["views"].astype(float)
        total = weights.sum()
        row: dict[str, float | str] = {"topic": topic}
        for col in SIMULATED_TRAFFIC_COLUMNS:
            values = group[col].fillna(0.0)
            row[col] = float((values * weights).sum() / total) if total > 0 else float(values.mean())
        rows.append(row)
    return pd.DataFrame(rows)


def structure_vs_performance(videos: pd.DataFrame, centralities: pd.DataFrame) -> pd.DataFrame:
    """Spearman rank correlation between graph centrality and performance metrics.

    Spearman uses ranks, so a few viral outliers do not dominate the result.
    Rows are centrality measures, columns are performance metrics.
    """
    if centralities.empty:
        return pd.DataFrame()
    merged = videos.merge(centralities, on="video_id", how="inner")
    if len(merged) < 5:
        return pd.DataFrame()
    result = merged[STRUCTURE_COLUMNS + PERFORMANCE_COLUMNS].corr(method="spearman")
    return result.loc[STRUCTURE_COLUMNS, PERFORMANCE_COLUMNS]


def community_performance(videos: pd.DataFrame, membership: dict[str, int]) -> pd.DataFrame:
    """Average performance of each detected community."""
    if videos.empty or not membership:
        return pd.DataFrame()
    labelled = videos.assign(community=videos["video_id"].map(membership)).dropna(subset=["community"])
    labelled = labelled.assign(community=labelled["community"].astype(int))
    summary = summarise_by(labelled, "community").sort_values("community").reset_index(drop=True)
    return summary


def apply_filters(
    videos: pd.DataFrame,
    topics: list[str] | None = None,
    channels: list[str] | None = None,
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    min_views: int = 0,
) -> pd.DataFrame:
    """Filter videos by topic, channel, publication date range and minimum views."""
    mask = pd.Series(True, index=videos.index)
    if topics is not None:
        mask &= videos["topic"].isin(topics)
    if channels is not None:
        mask &= videos["channel_name"].isin(channels)
    if date_range is not None:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        mask &= videos["published_at"].between(start, end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    if min_views > 0:
        mask &= videos["views"] >= min_views
    return videos.loc[mask].reset_index(drop=True)


def export_table(videos: pd.DataFrame, centralities: pd.DataFrame | None, membership: dict[str, int]) -> pd.DataFrame:
    """Filtered videos plus graph metrics, ready for CSV download (tags as text)."""
    out = videos.drop(columns=["tags_list"], errors="ignore").copy()
    if centralities is not None and not centralities.empty:
        out = out.merge(centralities, on="video_id", how="left")
    if membership:
        out["community"] = out["video_id"].map(membership)
    return out
