"""Tests for src/performance_analytics.py and the Plotly helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from src.graph_metrics import compute_centralities, detect_communities
from src.performance_analytics import (
    apply_filters,
    community_performance,
    correlation_matrix,
    export_table,
    keyword_analysis,
    monthly_timeline,
    overview_kpis,
    simulated_traffic_by_topic,
    structure_vs_performance,
    summarise_by,
    top_videos,
)
from src.visualizations import (
    colour_map,
    compute_layout,
    correlation_heatmap,
    dendrogram_figure,
    empty_figure,
    network_figure,
    strongest_edges,
    timeline_figure,
    topic_bars,
    traffic_stacked_bar,
    views_vs_engagement,
)
from src.graph_metrics import hierarchical_clustering


def test_top_videos_sorted_and_limited(sample_videos):
    top = top_videos(sample_videos, "views", 5)
    assert len(top) == 5 and top["views"].is_monotonic_decreasing
    assert top.iloc[0]["views"] == sample_videos["views"].max()
    with pytest.raises(KeyError):
        top_videos(sample_videos, "not_a_column")


def test_summarise_by_topic_adds_up(sample_videos):
    summary = summarise_by(sample_videos, "topic")
    assert summary["videos"].sum() == len(sample_videos)
    assert summary["total_views"].sum() == sample_videos["views"].sum()
    assert summarise_by(sample_videos.head(0), "topic").empty


def test_apply_filters_combines_conditions(sample_videos):
    filtered = apply_filters(
        sample_videos, topics=["Gaming"], channels=None,
        date_range=(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")), min_views=20000,
    )
    assert (filtered["topic"] == "Gaming").all()
    assert filtered["published_at"].between("2025-01-01", "2025-12-31 23:59:59").all()
    assert (filtered["views"] >= 20000).all()
    assert apply_filters(sample_videos, topics=[]).empty


def test_apply_filters_includes_the_end_date(sample_videos):
    last_day = sample_videos["published_at"].max().normalize()
    result = apply_filters(sample_videos, date_range=(last_day, last_day))
    assert len(result) >= 1


def test_overview_kpis(sample_videos):
    kpis = overview_kpis(sample_videos, edge_count=10, community_count=3)
    assert kpis["videos"] == len(sample_videos) and kpis["edges"] == 10 and kpis["communities"] == 3
    assert kpis["total_views"] == int(sample_videos["views"].sum())
    assert overview_kpis(sample_videos.head(0), 0, 0)["avg_engagement"] == 0.0


def test_keyword_analysis_counts_tags(sample_videos):
    keywords = keyword_analysis(sample_videos, min_videos=3)
    assert (keywords["videos"] >= 3).all()
    manual = sum("workout" in tags for tags in sample_videos["tags_list"])
    assert keywords.set_index("keyword").loc["workout", "videos"] == manual


def test_timeline_and_correlation(sample_videos):
    timeline = monthly_timeline(sample_videos)
    assert timeline["videos"].sum() == len(sample_videos)
    corr = correlation_matrix(sample_videos)
    assert corr.shape == (5, 5) and corr.loc["views", "views"] == pytest.approx(1.0)
    assert correlation_matrix(sample_videos.head(2)).empty


def test_simulated_traffic_is_weighted_and_sums_to_100(sample_videos):
    traffic = simulated_traffic_by_topic(sample_videos)
    assert len(traffic) == sample_videos["topic"].nunique()
    assert traffic.drop(columns="topic").sum(axis=1).between(99.5, 100.5).all()
    assert simulated_traffic_by_topic(sample_videos.drop(columns=["sim_search_pct"])).empty


def test_structure_vs_performance_shape(sample_videos, sample_graph):
    centralities, _ = compute_centralities(sample_graph)
    relation = structure_vs_performance(sample_videos, centralities)
    assert relation.shape == (5, 3)
    assert relation.abs().max().max() <= 1.0
    assert structure_vs_performance(sample_videos, centralities.head(0)).empty


def test_community_performance_and_export(sample_videos, sample_graph):
    communities = detect_communities(sample_graph)
    performance = community_performance(sample_videos, communities.membership)
    assert performance["videos"].sum() == len(sample_videos)
    centralities, _ = compute_centralities(sample_graph)
    exported = export_table(sample_videos, centralities, communities.membership)
    assert "tags_list" not in exported.columns
    assert {"pagerank", "community", "engagement_rate"} <= set(exported.columns)
    assert len(exported) == len(sample_videos)


# --- visualisation helpers ------------------------------------------------
def test_colour_map_is_stable_and_complete():
    assert colour_map(["b", "a", "b"]) == colour_map(["a", "b"])
    assert len(set(colour_map(list("abcdefg")).values())) == 7


def test_strongest_edges_limits_per_node(sample_graph):
    limited = strongest_edges(sample_graph, 2)
    assert len(limited) < sample_graph.number_of_edges()
    assert len(strongest_edges(sample_graph, None)) == sample_graph.number_of_edges()


def test_network_figure_builds_with_path_and_sizes(sample_graph):
    positions = compute_layout(sample_graph)
    assert set(positions) == set(sample_graph.nodes)
    nodes = sorted(sample_graph.nodes)
    groups = {n: sample_graph.nodes[n]["topic"] for n in sample_graph}
    sizes = {n: float(sample_graph.degree(n)) for n in sample_graph}
    figure = network_figure(sample_graph, positions, groups, "Topic", sizes, 3, highlight_path=nodes[:3])
    names = [trace.name for trace in figure.data if trace.name]
    assert "Shortest path" in names and any(name.startswith("Topic:") for name in names)


def test_figures_handle_empty_input():
    import networkx as nx

    empty_graph = nx.Graph()
    assert network_figure(empty_graph, {}, {}, "Topic").layout.annotations
    assert empty_figure("x").layout.annotations
    assert views_vs_engagement(pd.DataFrame()).layout.annotations
    assert timeline_figure(pd.DataFrame()).layout.annotations
    assert topic_bars(pd.DataFrame(), "videos", "t", "l").layout.annotations
    assert correlation_heatmap(pd.DataFrame()).layout.annotations
    assert traffic_stacked_bar(pd.DataFrame()).layout.annotations


def test_dendrogram_figure_builds(sample_videos, sample_edges):
    result = hierarchical_clustering(sample_videos, sample_edges, 7)
    assert len(dendrogram_figure(result.linkage_matrix, p=20).data) > 5
