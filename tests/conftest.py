"""Shared fixtures for the test-suite."""

from __future__ import annotations

import networkx as nx
import pandas as pd
import pytest

from src.data_loader import DEFAULT_DATA_PATH, load_videos
from src.graph_builder import DEFAULT_THRESHOLD, build_graph, compute_candidate_edges


@pytest.fixture(scope="session")
def sample_videos() -> pd.DataFrame:
    """The cleaned bundled demo dataset."""
    return load_videos(DEFAULT_DATA_PATH).data


@pytest.fixture(scope="session")
def sample_edges(sample_videos: pd.DataFrame) -> pd.DataFrame:
    return compute_candidate_edges(sample_videos)


@pytest.fixture(scope="session")
def sample_graph(sample_videos: pd.DataFrame, sample_edges: pd.DataFrame) -> nx.Graph:
    return build_graph(sample_videos, sample_edges, DEFAULT_THRESHOLD)


def make_raw_row(**overrides) -> dict:
    """One valid raw CSV row; tests override single fields to break it."""
    row = {
        "video_id": "T001", "title": "Test video", "channel_name": "Test channel",
        "published_at": "2026-01-01", "duration_minutes": 10.0, "views": 1000, "likes": 50,
        "comments": 10, "topic": "Testing", "tags": "alpha;beta",
    }
    row.update(overrides)
    return row


@pytest.fixture()
def raw_frame():
    """Factory: build a raw dataframe from a list of row-override dicts."""
    def factory(*overrides: dict) -> pd.DataFrame:
        rows = []
        for i, extra in enumerate(overrides or ({},)):
            base = make_raw_row(video_id=f"T{i + 1:03d}")
            base.update(extra)
            rows.append(base)
        return pd.DataFrame(rows)
    return factory


@pytest.fixture()
def weighted_graph() -> nx.Graph:
    """A small graph where the direct A-B edge is costlier than going through C."""
    graph = nx.Graph()
    for node in "ABCDE":
        graph.add_node(node, title=f"Video {node}", topic="T")
    edges = [("A", "B", 5.0), ("A", "C", 1.0), ("C", "B", 1.0), ("B", "D", 2.0)]
    for a, b, cost in edges:
        graph.add_edge(a, b, distance=cost, weight=1.0 / cost, shared_tags="x")
    return graph  # node E is isolated on purpose
