"""Graph algorithms used by the dashboard.

Every function takes a NetworkX graph built by ``graph_builder.build_graph`` and
returns plain pandas/dataclass results, so they are easy to test and to explain.

Distances: algorithms that need a "cost" between nodes (Dijkstra, closeness,
betweenness) use the edge attribute ``distance = 1 / similarity``. Algorithms
that need a "strength" (PageRank, eigenvector, communities) use ``weight``
(= similarity).
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)

CENTRALITY_COLUMNS = ["degree", "closeness", "betweenness", "eigenvector", "pagerank"]


# --------------------------------------------------------------------------
# Centrality measures
# --------------------------------------------------------------------------
def compute_centralities(graph: nx.Graph) -> tuple[pd.DataFrame, list[str]]:
    """Return a table of five centrality measures plus any explanatory notes.

    * degree       - share of other videos a video is directly linked to
    * closeness    - inverse average distance (cost = ``distance``) to reachable videos
    * betweenness  - share of shortest (lowest-cost) paths passing through the video
    * eigenvector  - links to well-connected videos count more
    * pagerank     - random-surfer importance using similarity as link strength

    Eigenvector centrality can fail to converge on some graphs; in that case a
    fallback is tried and, if that also fails, the column is filled with NaN and
    a note explains why. The other four measures are always returned.
    """
    notes: list[str] = []
    nodes = list(graph.nodes)
    if not nodes:
        return pd.DataFrame(columns=["video_id", *CENTRALITY_COLUMNS]), ["The graph has no nodes."]

    degree = nx.degree_centrality(graph)
    closeness = nx.closeness_centrality(graph, distance="distance")
    betweenness = nx.betweenness_centrality(graph, weight="distance", normalized=True)

    if graph.number_of_edges() == 0:
        eigenvector = {n: float("nan") for n in nodes}
        pagerank = {n: 1.0 / len(nodes) for n in nodes}
        notes.append("There are no edges, so eigenvector centrality is undefined and PageRank is uniform.")
    else:
        eigenvector, eigen_note = _safe_eigenvector(graph)
        if eigen_note:
            notes.append(eigen_note)
        pagerank = nx.pagerank(graph, weight="weight")
        if nx.number_connected_components(graph) > 1:
            notes.append(
                "The graph has several connected components, so eigenvector centrality is "
                "dominated by the best-connected component and closeness only reflects reachable videos."
            )

    table = pd.DataFrame(
        {
            "video_id": nodes,
            "degree": [degree[n] for n in nodes],
            "closeness": [closeness[n] for n in nodes],
            "betweenness": [betweenness[n] for n in nodes],
            "eigenvector": [eigenvector[n] for n in nodes],
            "pagerank": [pagerank[n] for n in nodes],
        }
    )
    return table, notes


def _safe_eigenvector(graph: nx.Graph) -> tuple[dict[str, float], str]:
    """Eigenvector centrality with a documented fallback and a user-facing note."""
    try:
        return nx.eigenvector_centrality(graph, max_iter=2000, tol=1e-08, weight="weight"), ""
    except nx.PowerIterationFailedConvergence:
        logger.warning("Power iteration did not converge; trying the exact (numpy) solver.")
    except nx.NetworkXException as exc:
        logger.warning("Eigenvector centrality failed: %s", exc)

    values = _eigenvector_exact(graph)
    if values is not None:
        return values, (
            "Eigenvector centrality did not converge by power iteration, so an exact solver was used "
            "(videos outside the largest connected group get 0 if the graph is disconnected)."
        )
    return (
        {n: float("nan") for n in graph.nodes},
        "Eigenvector centrality could not be computed for this graph (it did not converge). "
        "The other measures are still valid.",
    )


def _eigenvector_exact(graph: nx.Graph) -> dict[str, float] | None:
    """Exact solver fallback; on a disconnected graph it solves the largest component only."""
    try:
        return nx.eigenvector_centrality_numpy(graph, weight="weight")
    except nx.AmbiguousSolution:
        largest = max(nx.connected_components(graph), key=len)
        try:
            solved = nx.eigenvector_centrality_numpy(graph.subgraph(largest), weight="weight")
        except (nx.NetworkXException, ArithmeticError, np.linalg.LinAlgError) as exc:
            logger.warning("Eigenvector fallback failed on the largest component: %s", exc)
            return None
        return {n: float(solved.get(n, 0.0)) for n in graph.nodes}
    except (nx.NetworkXException, ArithmeticError, np.linalg.LinAlgError) as exc:
        logger.warning("Eigenvector fallback failed: %s", exc)
        return None


# --------------------------------------------------------------------------
# Communities, partitioning and clustering
# --------------------------------------------------------------------------
@dataclass
class CommunityResult:
    """Communities found by greedy modularity maximisation."""

    membership: dict[str, int]
    modularity: float
    sizes: dict[int, int] = field(default_factory=dict)

    @property
    def multi_node_count(self) -> int:
        """Communities that contain at least two videos."""
        return sum(1 for size in self.sizes.values() if size >= 2)


def detect_communities(graph: nx.Graph) -> CommunityResult:
    """Greedy modularity communities (Clauset-Newman-Moore), numbered 1..k by size.

    These are algorithmic groupings of densely connected videos. They often match
    topics but are not guaranteed to be real-world categories.
    """
    if graph.number_of_nodes() == 0:
        return CommunityResult({}, 0.0, {})
    if graph.number_of_edges() == 0:
        membership = {n: i + 1 for i, n in enumerate(sorted(graph.nodes))}
        return CommunityResult(membership, 0.0, {i: 1 for i in membership.values()})

    groups = nx.community.greedy_modularity_communities(graph, weight="weight")
    groups = sorted(groups, key=lambda g: (-len(g), min(g)))
    membership = {node: idx for idx, group in enumerate(groups, start=1) for node in group}
    modularity = float(nx.community.modularity(graph, groups, weight="weight"))
    sizes = {idx: len(group) for idx, group in enumerate(groups, start=1)}
    return CommunityResult(membership, modularity, sizes)


def community_topic_table(graph: nx.Graph, result: CommunityResult) -> pd.DataFrame:
    """For each community: size, dominant topic and how pure that topic is."""
    rows = []
    for community_id, size in result.sizes.items():
        members = [n for n, c in result.membership.items() if c == community_id]
        topics = pd.Series([graph.nodes[n].get("topic", "") for n in members]).value_counts()
        rows.append(
            {
                "community": community_id,
                "videos": size,
                "dominant_topic": topics.index[0],
                "topic_purity_pct": round(100 * topics.iloc[0] / size, 1),
                "topics_present": int(len(topics)),
            }
        )
    return pd.DataFrame(rows, columns=["community", "videos", "dominant_topic", "topic_purity_pct", "topics_present"])


def find_bridge_videos(graph: nx.Graph, membership: dict[str, int], betweenness: pd.Series) -> pd.DataFrame:
    """Videos with neighbours in at least two communities, ranked by betweenness."""
    rows = []
    for node in graph.nodes:
        neighbour_communities = {membership[nb] for nb in graph[node] if nb in membership}
        own = membership.get(node)
        other = neighbour_communities - {own}
        if other:
            rows.append(
                {
                    "video_id": node,
                    "title": graph.nodes[node].get("title", ""),
                    "topic": graph.nodes[node].get("topic", ""),
                    "own_community": own,
                    "other_communities_linked": len(other),
                    "betweenness": float(betweenness.get(node, 0.0)),
                }
            )
    table = pd.DataFrame(rows, columns=["video_id", "title", "topic", "own_community", "other_communities_linked", "betweenness"])
    return table.sort_values(["betweenness", "other_communities_linked"], ascending=False).reset_index(drop=True)


@dataclass
class BisectionResult:
    """Result of splitting the graph into two balanced halves."""

    part_a: set[str]
    part_b: set[str]
    cut_edges: int
    cut_weight: float


def kernighan_lin_partition(graph: nx.Graph, seed: int = 42) -> BisectionResult | None:
    """Classic graph partitioning: split nodes into two balanced halves with few cut edges.

    Kernighan-Lin swaps pairs of nodes to reduce the number (weight) of edges
    that cross between the halves. Returns None when the graph has fewer than 2 nodes.
    """
    if graph.number_of_nodes() < 2:
        return None
    part_a, part_b = nx.community.kernighan_lin_bisection(graph, weight="weight", seed=seed)
    cut = [(u, v, d) for u, v, d in graph.edges(data=True) if (u in part_a) != (v in part_a)]
    return BisectionResult(set(part_a), set(part_b), len(cut), float(sum(d["weight"] for _, _, d in cut)))


@dataclass
class HierarchicalResult:
    """Agglomerative (bottom-up) hierarchical clustering of the videos."""

    linkage_matrix: np.ndarray
    labels: list[str]
    clusters: dict[str, int]


def hierarchical_clustering(
    videos: pd.DataFrame, candidate_edges: pd.DataFrame, n_clusters: int = 7
) -> HierarchicalResult | None:
    """Average-linkage hierarchical clustering on ``1 - similarity`` distances.

    Unlike communities (which only use edges that pass the threshold), this uses
    the similarity of every pair of videos (0 when they share no tag) and builds
    a full merge tree (dendrogram), which can be cut at any number of clusters.
    Returns None for fewer than 3 videos.
    """
    ids = videos["video_id"].tolist()
    n = len(ids)
    if n < 3:
        return None
    index = {vid: i for i, vid in enumerate(ids)}
    similarity = np.zeros((n, n))
    if candidate_edges is not None and not candidate_edges.empty:
        for row in candidate_edges.itertuples(index=False):
            if row.source in index and row.target in index:
                i, j = index[row.source], index[row.target]
                similarity[i, j] = similarity[j, i] = row.similarity
    distance = 1.0 - similarity
    np.fill_diagonal(distance, 0.0)
    merge_tree = linkage(squareform(distance, checks=False), method="average")
    k = max(1, min(int(n_clusters), n))
    labels = fcluster(merge_tree, t=k, criterion="maxclust")
    return HierarchicalResult(merge_tree, ids, {vid: int(lbl) for vid, lbl in zip(ids, labels)})


# --------------------------------------------------------------------------
# Shortest path (Dijkstra)
# --------------------------------------------------------------------------
@dataclass
class PathResult:
    """Outcome of a shortest-path query between two videos."""

    found: bool
    nodes: list[str] = field(default_factory=list)
    total_cost: float = math.inf
    steps: list[dict] = field(default_factory=list)
    message: str = ""


def dijkstra_manual(graph: nx.Graph, source: str, target: str, weight: str = "distance") -> tuple[list[str], float]:
    """Dijkstra's algorithm written out step by step (for teaching and testing).

    Keeps a priority queue of (cost so far, node). The cheapest unvisited node is
    taken first; its neighbours are "relaxed" (updated if a cheaper route is found).
    Raises ``nx.NetworkXNoPath`` when ``target`` cannot be reached.
    """
    if source not in graph or target not in graph:
        raise nx.NodeNotFound("Source or target is not in the graph.")
    best: dict[str, float] = {source: 0.0}
    came_from: dict[str, str] = {}
    visited: set[str] = set()
    queue: list[tuple[float, str]] = [(0.0, source)]
    while queue:
        cost, node = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            break
        for neighbour, data in graph[node].items():
            new_cost = cost + data[weight]
            if neighbour not in best or new_cost < best[neighbour]:
                best[neighbour] = new_cost
                came_from[neighbour] = node
                heapq.heappush(queue, (new_cost, neighbour))
    if target not in visited:
        raise nx.NetworkXNoPath(f"No path between {source} and {target}.")
    path = [target]
    while path[-1] != source:
        path.append(came_from[path[-1]])
    path.reverse()
    return path, best[target]


def shortest_video_path(graph: nx.Graph, source: str, target: str) -> PathResult:
    """Lowest-cost path between two videos using Dijkstra with ``distance`` as cost."""
    if source not in graph or target not in graph:
        return PathResult(False, message="Pick two videos that are in the current (filtered) graph.")
    if source == target:
        return PathResult(True, [source], 0.0, [], "Source and target are the same video (cost 0).")
    try:
        nodes = nx.dijkstra_path(graph, source, target, weight="distance")
    except nx.NetworkXNoPath:
        return PathResult(
            False,
            message="These videos are in different connected components, so no path exists "
            "at this threshold. Lower the similarity threshold to connect them.",
        )
    steps = []
    total = 0.0
    for a, b in zip(nodes, nodes[1:]):
        data = graph[a][b]
        total += data["distance"]
        steps.append(
            {
                "from": graph.nodes[a].get("title", a),
                "to": graph.nodes[b].get("title", b),
                "similarity": round(data["weight"], 3),
                "step_cost": round(data["distance"], 3),
                "shared_tags": data.get("shared_tags", ""),
            }
        )
    return PathResult(True, nodes, total, steps, f"Found a path with {len(nodes) - 1} step(s).")


# --------------------------------------------------------------------------
# Network-level properties
# --------------------------------------------------------------------------
def network_properties(graph: nx.Graph) -> dict[str, float | int | bool]:
    """Basic structural properties of the graph."""
    n, m = graph.number_of_nodes(), graph.number_of_edges()
    if n == 0:
        return {"nodes": 0, "edges": 0, "density": 0.0, "average_degree": 0.0, "components": 0,
                "largest_component": 0, "connected": False, "average_clustering": 0.0}
    components = list(nx.connected_components(graph))
    return {
        "nodes": n,
        "edges": m,
        "density": nx.density(graph),
        "average_degree": 2 * m / n,
        "components": len(components),
        "largest_component": max(len(c) for c in components),
        "connected": len(components) == 1,
        "average_clustering": nx.average_clustering(graph, weight=None),
    }


def degree_distribution(graph: nx.Graph) -> pd.DataFrame:
    """How many videos have each degree (number of direct connections)."""
    degrees = [d for _, d in graph.degree()]
    if not degrees:
        return pd.DataFrame(columns=["degree", "videos"])
    counts = pd.Series(degrees).value_counts().sort_index()
    return pd.DataFrame({"degree": counts.index, "videos": counts.values})


def small_world_indicators(graph: nx.Graph) -> dict[str, float | str | bool]:
    """Compare clustering and path length with a random graph of the same size.

    Small-world networks combine HIGH clustering (like a lattice) with SHORT
    average paths (like a random graph). For the largest connected component we
    estimate the random-graph reference values as:
        C_random ~ <k> / n          L_random ~ ln(n) / ln(<k>)
    and report sigma = (C / C_random) / (L / L_random). Sigma well above 1 is a
    rough hint of small-world structure. This is only an indicator, not proof, and
    the graph here is built from a similarity rule, not from real social links.
    """
    if graph.number_of_edges() == 0:
        return {"valid": False, "note": "No edges, so small-world indicators cannot be computed."}
    largest = max(nx.connected_components(graph), key=len)
    sub = graph.subgraph(largest)
    n = sub.number_of_nodes()
    k = 2 * sub.number_of_edges() / n
    if n < 10 or k <= 1.0:
        return {"valid": False, "note": "The largest component is too small or too sparse for a meaningful comparison."}
    clustering = nx.average_clustering(sub)
    path_length = nx.average_shortest_path_length(sub)  # hop count (unweighted)
    c_random = k / n
    l_random = math.log(n) / math.log(k)
    sigma = (clustering / c_random) / (path_length / l_random) if c_random and path_length else float("nan")
    return {
        "valid": True,
        "nodes_used": n,
        "average_clustering": clustering,
        "average_path_length_hops": path_length,
        "clustering_random_estimate": c_random,
        "path_length_random_estimate": l_random,
        "sigma": sigma,
        "note": "Indicative only: a sigma above 1 suggests small-world-like structure; it is not a formal test.",
    }


def degree_summary(graph: nx.Graph) -> dict[str, float]:
    """Mean, median and max degree - a quick look at whether a few hubs dominate."""
    degrees = np.array([d for _, d in graph.degree()], dtype=float)
    if degrees.size == 0:
        return {"mean": 0.0, "median": 0.0, "max": 0.0, "max_to_mean": 0.0}
    mean = float(degrees.mean())
    return {
        "mean": mean,
        "median": float(np.median(degrees)),
        "max": float(degrees.max()),
        "max_to_mean": float(degrees.max() / mean) if mean else 0.0,
    }
