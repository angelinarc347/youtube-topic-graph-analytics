"""Tests for src/graph_metrics.py: centrality, Dijkstra, communities and network properties."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src import graph_metrics
from src.graph_metrics import (
    CENTRALITY_COLUMNS,
    community_topic_table,
    compute_centralities,
    degree_distribution,
    degree_summary,
    detect_communities,
    dijkstra_manual,
    find_bridge_videos,
    hierarchical_clustering,
    kernighan_lin_partition,
    network_properties,
    shortest_video_path,
    small_world_indicators,
)


def weighted(edges: list[tuple[str, str, float]]) -> nx.Graph:
    graph = nx.Graph()
    for a, b, similarity in edges:
        graph.add_edge(a, b, weight=similarity, distance=1.0 / similarity, shared_tags="x")
    for node in graph:
        graph.nodes[node].setdefault("title", f"Video {node}")
        graph.nodes[node].setdefault("topic", "T")
    return graph


def two_cliques() -> nx.Graph:
    """Two 5-node cliques (X*, Y*) joined by one weak bridge edge X0-Y0."""
    edges = [(f"X{i}", f"X{j}", 0.8) for i in range(5) for j in range(i + 1, 5)]
    edges += [(f"Y{i}", f"Y{j}", 0.8) for i in range(5) for j in range(i + 1, 5)]
    edges.append(("X0", "Y0", 0.3))
    graph = weighted(edges)
    for node in graph:
        graph.nodes[node]["topic"] = node[0]
    return graph


# --- Dijkstra -------------------------------------------------------------
def test_dijkstra_prefers_cheaper_two_step_route(weighted_graph):
    result = shortest_video_path(weighted_graph, "A", "B")
    assert result.found
    assert result.nodes == ["A", "C", "B"]
    assert result.total_cost == pytest.approx(2.0)  # 1 + 1, cheaper than the direct edge (5)
    assert [s["step_cost"] for s in result.steps] == [1.0, 1.0]


def test_dijkstra_reports_no_path_for_isolated_video(weighted_graph):
    result = shortest_video_path(weighted_graph, "A", "E")
    assert not result.found and "different connected components" in result.message
    assert math.isinf(result.total_cost)


def test_dijkstra_same_video_and_unknown_video(weighted_graph):
    same = shortest_video_path(weighted_graph, "A", "A")
    assert same.found and same.total_cost == 0.0 and same.nodes == ["A"]
    assert not shortest_video_path(weighted_graph, "A", "ZZZ").found


def test_manual_dijkstra_matches_networkx_on_weighted_graph(weighted_graph):
    nodes, cost = dijkstra_manual(weighted_graph, "A", "D")
    assert nodes == nx.dijkstra_path(weighted_graph, "A", "D", weight="distance")
    assert cost == pytest.approx(nx.dijkstra_path_length(weighted_graph, "A", "D", weight="distance"))
    with pytest.raises(nx.NetworkXNoPath):
        dijkstra_manual(weighted_graph, "A", "E")
    with pytest.raises(nx.NodeNotFound):
        dijkstra_manual(weighted_graph, "A", "missing")


def test_manual_dijkstra_matches_networkx_on_sample_data(sample_graph):
    nodes = sorted(sample_graph.nodes)
    for source, target in [(nodes[0], nodes[-1]), (nodes[10], nodes[100]), (nodes[40], nodes[41])]:
        _, manual_cost = dijkstra_manual(sample_graph, source, target)
        library_cost = nx.dijkstra_path_length(sample_graph, source, target, weight="distance")
        assert manual_cost == pytest.approx(library_cost)


def test_path_cost_equals_sum_of_step_costs(sample_graph):
    nodes = sorted(sample_graph.nodes)
    result = shortest_video_path(sample_graph, nodes[0], nodes[-1])
    assert result.found
    assert result.total_cost == pytest.approx(sum(s["step_cost"] for s in result.steps), abs=0.01 * len(result.steps))


# --- Centrality -----------------------------------------------------------
def test_star_graph_centrality_ranks_the_hub_first():
    star = weighted([("hub", f"leaf{i}", 0.5) for i in range(6)])
    table, notes = compute_centralities(star)
    hub = table.set_index("video_id").loc["hub"]
    assert hub["degree"] == pytest.approx(1.0)
    assert hub["betweenness"] > 0.9
    for column in CENTRALITY_COLUMNS:
        assert table.set_index("video_id")[column].idxmax() == "hub"
    assert notes == []


def test_centrality_table_has_expected_shape_and_pagerank_sums_to_one(sample_graph):
    table, _ = compute_centralities(sample_graph)
    assert list(table.columns) == ["video_id", *CENTRALITY_COLUMNS]
    assert len(table) == sample_graph.number_of_nodes()
    assert table["pagerank"].sum() == pytest.approx(1.0)
    assert table[CENTRALITY_COLUMNS].notna().all().all()
    assert (table["degree"].between(0, 1)).all()


def test_centralities_on_edgeless_and_empty_graphs_do_not_crash():
    edgeless = nx.Graph()
    edgeless.add_nodes_from(["a", "b", "c"])
    table, notes = compute_centralities(edgeless)
    assert len(table) == 3 and table["pagerank"].sum() == pytest.approx(1.0)
    assert table["eigenvector"].isna().all() and notes
    empty_table, empty_notes = compute_centralities(nx.Graph())
    assert empty_table.empty and empty_notes


def test_eigenvector_falls_back_to_numpy_solver(monkeypatch, weighted_graph):
    def fail(*args, **kwargs):
        raise nx.PowerIterationFailedConvergence(100)

    monkeypatch.setattr(graph_metrics.nx, "eigenvector_centrality", fail)
    table, notes = compute_centralities(weighted_graph)
    assert table["eigenvector"].notna().all()
    assert any("exact solver" in n for n in notes)


def test_eigenvector_failure_gives_nan_column_and_message(monkeypatch, weighted_graph):
    def fail(*args, **kwargs):
        raise nx.PowerIterationFailedConvergence(100)

    monkeypatch.setattr(graph_metrics.nx, "eigenvector_centrality", fail)
    monkeypatch.setattr(graph_metrics.nx, "eigenvector_centrality_numpy", fail)
    table, notes = compute_centralities(weighted_graph)
    assert table["eigenvector"].isna().all()
    assert table["pagerank"].notna().all()  # the other measures survive
    assert any("could not be computed" in n for n in notes)


def test_disconnected_graph_adds_an_explanatory_note(weighted_graph):
    _, notes = compute_centralities(weighted_graph.subgraph(["A", "C", "D"]).copy())
    # A-C and D are disconnected in this subgraph
    assert any("several connected components" in n for n in notes)


# --- Communities ----------------------------------------------------------
def test_two_cliques_form_two_communities():
    graph = two_cliques()
    result = detect_communities(graph)
    assert result.multi_node_count == 2
    assert set(result.membership) == set(graph.nodes)
    assert len({result.membership[f"X{i}"] for i in range(5)}) == 1
    assert result.membership["X1"] != result.membership["Y1"]
    assert result.modularity > 0.3
    assert sorted(result.sizes.values(), reverse=True) == [5, 5]


def test_communities_on_edgeless_and_empty_graph():
    edgeless = nx.Graph()
    edgeless.add_nodes_from(["a", "b"])
    result = detect_communities(edgeless)
    assert result.multi_node_count == 0 and set(result.membership) == {"a", "b"}
    assert detect_communities(nx.Graph()).membership == {}


def test_sample_communities_match_topics_closely(sample_graph):
    result = detect_communities(sample_graph)
    table = community_topic_table(sample_graph, result)
    assert result.multi_node_count >= 5
    assert table["topic_purity_pct"].mean() > 80  # synthetic topics were built to cluster


def test_bridge_videos_link_different_communities():
    graph = two_cliques()
    result = detect_communities(graph)
    betweenness = pd.Series(nx.betweenness_centrality(graph, weight="distance"))
    bridges = find_bridge_videos(graph, result.membership, betweenness)
    assert set(bridges["video_id"]) == {"X0", "Y0"}


def test_sample_bridge_videos_exist(sample_graph):
    result = detect_communities(sample_graph)
    centralities, _ = compute_centralities(sample_graph)
    bridges = find_bridge_videos(sample_graph, result.membership, centralities.set_index("video_id")["betweenness"])
    assert len(bridges) >= 5
    assert bridges["betweenness"].is_monotonic_decreasing


def test_kernighan_lin_cuts_only_the_bridge_edge():
    result = kernighan_lin_partition(two_cliques())
    assert result is not None
    assert result.cut_edges == 1
    assert len(result.part_a) == len(result.part_b) == 5
    assert kernighan_lin_partition(nx.Graph()) is None


def test_hierarchical_clustering_returns_requested_number_of_clusters(sample_videos, sample_edges):
    result = hierarchical_clustering(sample_videos, sample_edges, n_clusters=5)
    assert result is not None
    assert len(set(result.clusters.values())) == 5
    assert set(result.clusters) == set(sample_videos["video_id"])
    assert result.linkage_matrix.shape == (len(sample_videos) - 1, 4)


def test_hierarchical_clustering_needs_three_videos(sample_videos, sample_edges):
    assert hierarchical_clustering(sample_videos.head(2), sample_edges) is None


# --- Network properties ---------------------------------------------------
def test_network_properties_of_a_triangle_and_empty_graph():
    props = network_properties(nx.complete_graph(3))
    assert props["density"] == pytest.approx(1.0)
    assert props["average_degree"] == pytest.approx(2.0)
    assert props["components"] == 1 and props["connected"] is True
    assert props["average_clustering"] == pytest.approx(1.0)
    assert network_properties(nx.Graph())["nodes"] == 0


def test_network_properties_count_components(weighted_graph):
    props = network_properties(weighted_graph)
    assert props["components"] == 2 and props["largest_component"] == 4 and props["connected"] is False


def test_degree_distribution_counts_all_nodes(sample_graph):
    distribution = degree_distribution(sample_graph)
    assert distribution["videos"].sum() == sample_graph.number_of_nodes()
    assert degree_distribution(nx.Graph()).empty


def test_degree_summary_and_empty_graph():
    summary = degree_summary(nx.path_graph(4))
    assert summary["max"] == 2 and summary["mean"] == pytest.approx(1.5)
    assert degree_summary(nx.Graph())["max_to_mean"] == 0.0


def test_small_world_indicators_are_finite_or_explained(sample_graph):
    indicators = small_world_indicators(sample_graph)
    assert indicators["valid"] is True
    assert np.isfinite(indicators["sigma"])
    assert "not a formal test" in indicators["note"]
    assert small_world_indicators(nx.Graph())["valid"] is False
    assert small_world_indicators(nx.path_graph(4))["valid"] is False  # too small to compare
