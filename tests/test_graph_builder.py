"""Tests for src/graph_builder.py: similarity rule, edge distance and graph construction."""

from __future__ import annotations

import networkx as nx
import pandas as pd
import pytest

from src.graph_builder import (
    EPSILON,
    TOPIC_BONUS,
    build_graph,
    compute_candidate_edges,
    edge_table,
    graph_health_messages,
    jaccard_similarity,
    similarity_score,
    similarity_to_distance,
)


def make_videos(rows: list[tuple[str, str, list[str]]]) -> pd.DataFrame:
    return pd.DataFrame({
        "video_id": [r[0] for r in rows], "topic": [r[1] for r in rows], "tags_list": [r[2] for r in rows],
        "title": [f"Title {r[0]}" for r in rows], "channel_name": "Chan", "views": 100, "likes": 5,
        "comments": 1, "engagement_rate": 6.0, "views_per_day": 1.0,
        "published_at": pd.Timestamp("2026-01-01"),
    })


def test_jaccard_values():
    assert jaccard_similarity(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert jaccard_similarity(["a"], ["a"]) == 1.0
    assert jaccard_similarity([], []) == 0.0
    assert jaccard_similarity(["a"], ["b"]) == 0.0


def test_similarity_adds_topic_bonus_and_is_capped_at_one():
    base = jaccard_similarity(["a", "b"], ["b", "c"])
    assert similarity_score(["a", "b"], ["b", "c"], same_topic=True) == pytest.approx(base + TOPIC_BONUS)
    assert similarity_score(["a", "b"], ["b", "c"], same_topic=False) == pytest.approx(base)
    assert similarity_score(["a"], ["a"], same_topic=True) == 1.0


def test_distance_is_inverse_of_similarity_with_epsilon_guard():
    assert similarity_to_distance(0.5) == pytest.approx(2.0)
    assert similarity_to_distance(1.0) == pytest.approx(1.0)
    assert similarity_to_distance(0.0) == pytest.approx(1.0 / EPSILON)  # never divides by zero


def test_candidate_edges_need_a_shared_tag():
    videos = make_videos([("A", "X", ["t1", "t2"]), ("B", "X", ["t3"]), ("C", "Y", ["t2"])])
    edges = compute_candidate_edges(videos)
    pairs = {(r.source, r.target) for r in edges.itertuples()}
    assert pairs == {("A", "C")}  # A-B share a topic but no tag, so there is no edge


def test_candidate_edge_attributes_are_consistent():
    videos = make_videos([("A", "X", ["t1", "t2"]), ("B", "X", ["t2", "t3"])])
    edge = compute_candidate_edges(videos).iloc[0]
    assert edge["jaccard"] == pytest.approx(1 / 3)
    assert edge["similarity"] == pytest.approx(1 / 3 + TOPIC_BONUS)
    assert edge["distance"] == pytest.approx(1 / edge["similarity"])
    assert edge["shared_tags"] == "t2"
    assert bool(edge["same_topic"]) is True


def test_build_graph_is_undirected_weighted_and_keeps_all_nodes(sample_videos, sample_edges):
    graph = build_graph(sample_videos, sample_edges, 0.25)
    assert isinstance(graph, nx.Graph) and not graph.is_directed()
    assert graph.number_of_nodes() == len(sample_videos)
    for _, _, data in graph.edges(data=True):
        assert data["weight"] >= 0.25
        assert data["distance"] == pytest.approx(1.0 / data["weight"])


def test_higher_threshold_never_adds_edges(sample_videos, sample_edges):
    counts = [build_graph(sample_videos, sample_edges, t).number_of_edges() for t in (0.1, 0.25, 0.4, 0.6, 0.9)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1]


def test_graph_is_not_a_complete_graph(sample_graph):
    n = sample_graph.number_of_nodes()
    assert nx.density(sample_graph) < 0.5
    assert sample_graph.number_of_edges() < n * (n - 1) / 2


def test_filtering_videos_restricts_nodes(sample_videos, sample_edges):
    subset = sample_videos[sample_videos["topic"] == "Gaming"]
    graph = build_graph(subset, sample_edges, 0.25)
    assert set(graph.nodes) == set(subset["video_id"])
    assert all(graph.nodes[a]["topic"] == "Gaming" for a in graph)


def test_empty_candidate_edges_gives_edgeless_graph():
    videos = make_videos([("A", "X", []), ("B", "X", [])])
    graph = build_graph(videos, compute_candidate_edges(videos), 0.2)
    assert graph.number_of_nodes() == 2 and graph.number_of_edges() == 0


def test_health_messages_for_empty_sparse_and_disconnected_graphs():
    assert "No videos" in graph_health_messages(nx.Graph())[0]
    edgeless = nx.Graph()
    edgeless.add_nodes_from(["a", "b"])
    assert "No edges" in graph_health_messages(edgeless)[0]
    split = nx.Graph([("a", "b"), ("c", "d")])
    assert any("disconnected" in m for m in graph_health_messages(split))
    assert graph_health_messages(nx.complete_graph(4)) == []


def test_edge_table_lists_titles(sample_graph):
    table = edge_table(sample_graph)
    assert len(table) == sample_graph.number_of_edges()
    assert {"title_a", "title_b", "similarity", "distance", "shared_tags"} <= set(table.columns)
