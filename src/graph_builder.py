"""Build the video similarity graph.

Graph model (undirected, weighted):
  * node  = one video
  * edge  = two videos that share at least one tag AND whose similarity score
            is at least the user-selected threshold
  * edge weight   (``weight``)   = similarity score, higher = more alike
  * edge distance (``distance``) = 1 / max(similarity, EPSILON), used as the
    cost by Dijkstra, closeness and betweenness (similar videos are "close").

Similarity score (explainable, range 0 to 1):

    similarity = min(1, Jaccard(tags_a, tags_b) + TOPIC_BONUS * [same topic])

    Jaccard(A, B) = |A intersect B| / |A union B|

The topic bonus nudges videos from the same topic closer together, but it can
never create an edge on its own: two videos must share at least one tag.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import networkx as nx
import pandas as pd

TOPIC_BONUS = 0.15
EPSILON = 1e-6
DEFAULT_THRESHOLD = 0.25
EDGE_COLUMNS = ["source", "target", "shared_tags", "jaccard", "same_topic", "similarity", "distance"]

NODE_ATTRIBUTES = (
    "title", "channel_name", "topic", "views", "likes", "comments",
    "engagement_rate", "views_per_day", "published_at",
)


def jaccard_similarity(tags_a: list[str] | set[str], tags_b: list[str] | set[str]) -> float:
    """Jaccard index of two tag collections (0 when both are empty)."""
    set_a, set_b = set(tags_a), set(tags_b)
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def similarity_score(
    tags_a: list[str] | set[str], tags_b: list[str] | set[str], same_topic: bool
) -> float:
    """Jaccard similarity plus the same-topic bonus, capped at 1."""
    return min(1.0, jaccard_similarity(tags_a, tags_b) + (TOPIC_BONUS if same_topic else 0.0))


def similarity_to_distance(similarity: float) -> float:
    """Convert a similarity (weight) into a shortest-path cost: 1 / max(sim, EPSILON)."""
    return 1.0 / max(float(similarity), EPSILON)


def compute_candidate_edges(videos: pd.DataFrame) -> pd.DataFrame:
    """Return every video pair that shares at least one tag, with its similarity.

    Only pairs that share a tag are examined (via an inverted index tag -> videos),
    which keeps the work small even for thousands of videos. The result is
    independent of the threshold, so the dashboard can compute it once and then
    filter it instantly while the user moves the slider.
    """
    ids = videos["video_id"].tolist()
    tags_by_id = dict(zip(videos["video_id"], videos["tags_list"].apply(set)))
    topic_by_id = dict(zip(videos["video_id"], videos["topic"]))

    by_tag: dict[str, list[str]] = defaultdict(list)
    for vid in ids:
        for tag in tags_by_id[vid]:
            by_tag[tag].append(vid)

    pairs: set[tuple[str, str]] = set()
    for members in by_tag.values():
        for a, b in combinations(sorted(members), 2):
            pairs.add((a, b))

    records = []
    for a, b in sorted(pairs):
        shared = sorted(tags_by_id[a] & tags_by_id[b])
        same_topic = topic_by_id[a] == topic_by_id[b]
        jac = jaccard_similarity(tags_by_id[a], tags_by_id[b])
        sim = min(1.0, jac + (TOPIC_BONUS if same_topic else 0.0))
        records.append(
            {
                "source": a,
                "target": b,
                "shared_tags": "; ".join(shared),
                "jaccard": jac,
                "same_topic": same_topic,
                "similarity": sim,
                "distance": similarity_to_distance(sim),
            }
        )
    return pd.DataFrame.from_records(records, columns=EDGE_COLUMNS)


def build_graph(
    videos: pd.DataFrame, candidate_edges: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD
) -> nx.Graph:
    """Create the undirected weighted graph for the given videos and threshold.

    Every video in ``videos`` becomes a node (even if it ends up with no edges).
    An edge is added only when both ends are in ``videos`` and the similarity
    score is at least ``threshold``.
    """
    graph = nx.Graph(threshold=float(threshold))
    for row in videos.itertuples(index=False):
        attrs = {name: getattr(row, name) for name in NODE_ATTRIBUTES if hasattr(row, name)}
        graph.add_node(row.video_id, **attrs)

    if candidate_edges is not None and not candidate_edges.empty:
        keep = candidate_edges[
            candidate_edges["source"].isin(graph) & candidate_edges["target"].isin(graph)
            & (candidate_edges["similarity"] >= threshold)
        ]
        for edge in keep.itertuples(index=False):
            graph.add_edge(
                edge.source,
                edge.target,
                weight=float(edge.similarity),
                distance=float(edge.distance),
                jaccard=float(edge.jaccard),
                same_topic=bool(edge.same_topic),
                shared_tags=edge.shared_tags,
            )
    return graph


def graph_health_messages(graph: nx.Graph) -> list[str]:
    """Plain-English warnings when the graph is empty, sparse or fragmented."""
    messages: list[str] = []
    n, m = graph.number_of_nodes(), graph.number_of_edges()
    if n == 0:
        return ["No videos match the current filters, so there is no graph to show."]
    if m == 0:
        messages.append(
            "No edges at this similarity threshold. Lower the threshold in the sidebar "
            "or loosen the filters to connect videos."
        )
        return messages
    components = nx.number_connected_components(graph)
    isolated = sum(1 for _, degree in graph.degree() if degree == 0)
    if components > 1:
        largest = max(len(c) for c in nx.connected_components(graph))
        messages.append(
            f"The graph is disconnected: {components} connected components "
            f"(the largest has {largest} of {n} videos; {isolated} video(s) have no connections). "
            "Shortest paths exist only inside one component. Lower the threshold to connect more videos."
        )
    density = nx.density(graph)
    if density < 0.01 and n > 20:
        messages.append(
            f"The graph is very sparse (density {density:.3f}). Centrality values will be small "
            "and communities may be tiny. Consider lowering the threshold."
        )
    return messages


def edge_table(graph: nx.Graph) -> pd.DataFrame:
    """The graph's edges as a table with titles, handy for display and CSV export."""
    rows = []
    for a, b, data in graph.edges(data=True):
        rows.append(
            {
                "video_a": a,
                "title_a": graph.nodes[a].get("title", ""),
                "video_b": b,
                "title_b": graph.nodes[b].get("title", ""),
                "similarity": round(data["weight"], 4),
                "distance": round(data["distance"], 4),
                "shared_tags": data.get("shared_tags", ""),
            }
        )
    return pd.DataFrame(rows, columns=[
        "video_a", "title_a", "video_b", "title_b", "similarity", "distance", "shared_tags"])
