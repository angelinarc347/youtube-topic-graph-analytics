"""Plotly figures for the dashboard.

All functions return a ``plotly.graph_objects.Figure`` and never touch Streamlit,
so they can be reused and tested on their own.
"""

from __future__ import annotations

import math
from typing import Mapping

import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.cluster.hierarchy import dendrogram

from src.data_loader import SIMULATED_TRAFFIC_COLUMNS

INK = "#1B2430"
MUTED = "#6B7683"
PRIMARY = "#0F6B6F"
PATH_COLOR = "#E4572E"
EDGE_COLOR = "rgba(120, 130, 142, 0.22)"
FONT = "Segoe UI, Helvetica Neue, Arial, sans-serif"

# Colour-blind-friendly categorical palette (Okabe-Ito plus extra neutrals).
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9",
           "#7A6C5D", "#F0E442", "#4D4D4D", "#B2DF8A", "#6A3D9A", "#A6761D"]


def colour_map(categories: list) -> dict:
    """Stable category -> colour mapping (sorted so colours do not jump around)."""
    ordered = sorted(set(categories), key=str)
    return {cat: PALETTE[i % len(PALETTE)] for i, cat in enumerate(ordered)}


def _style(fig: go.Figure, title: str | None = None, height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, font=dict(size=16, color=INK)) if title else None,
        font=dict(family=FONT, size=13, color=INK),
        height=height,
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", font=dict(size=12)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(120,130,142,0.18)", zeroline=False)
    return fig


def empty_figure(message: str, height: int = 320) -> go.Figure:
    """A blank figure with a centred message (used for empty states)."""
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=15, color=MUTED))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, height=height)


# --------------------------------------------------------------------------
# Network drawing
# --------------------------------------------------------------------------
def compute_layout(graph: nx.Graph, seed: int = 42) -> dict[str, tuple[float, float]]:
    """Force-directed (spring) layout; similar videos end up close together."""
    if graph.number_of_nodes() == 0:
        return {}
    if graph.number_of_nodes() == 1:
        node = next(iter(graph.nodes))
        return {node: (0.0, 0.0)}
    k = 1.6 / math.sqrt(graph.number_of_nodes())
    pos = nx.spring_layout(graph, weight="weight", seed=seed, k=k, iterations=120)
    return {n: (float(x), float(y)) for n, (x, y) in pos.items()}


def strongest_edges(graph: nx.Graph, per_node: int | None) -> list[tuple[str, str]]:
    """Edges to DRAW: each video's ``per_node`` strongest links (None = all edges).

    This only declutters the picture. All metrics still use the full graph.
    """
    if per_node is None:
        return list(graph.edges)
    keep: set[tuple[str, str]] = set()
    for node in graph.nodes:
        ranked = sorted(graph[node].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:per_node]
        for neighbour, _ in ranked:
            keep.add(tuple(sorted((node, neighbour))))
    return list(keep)


def network_figure(
    graph: nx.Graph,
    positions: Mapping[str, tuple[float, float]],
    groups: Mapping[str, object],
    group_label: str = "Group",
    sizes: Mapping[str, float] | None = None,
    draw_edges_per_node: int | None = 4,
    highlight_path: list[str] | None = None,
    group_names: Mapping[object, str] | None = None,
    height: int = 620,
) -> go.Figure:
    """Interactive network: node colour = group, node size = chosen metric.

    ``highlight_path`` draws that sequence of videos on top in a contrasting colour.
    """
    if graph.number_of_nodes() == 0:
        return empty_figure("No videos match the current filters.", height)

    fig = go.Figure()
    xs: list[float | None] = []
    ys: list[float | None] = []
    for a, b in strongest_edges(graph, draw_edges_per_node):
        xs += [positions[a][0], positions[b][0], None]
        ys += [positions[a][1], positions[b][1], None]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
                             line=dict(width=0.8, color=EDGE_COLOR)))

    if highlight_path and len(highlight_path) > 1:
        px_, py_ = [], []
        for a, b in zip(highlight_path, highlight_path[1:]):
            px_ += [positions[a][0], positions[b][0], None]
            py_ += [positions[a][1], positions[b][1], None]
        fig.add_trace(go.Scatter(x=px_, y=py_, mode="lines", hoverinfo="skip", name="Shortest path",
                                 line=dict(width=4, color=PATH_COLOR)))

    palette = colour_map(list(groups.values()))
    size_values = {n: (sizes[n] if sizes and n in sizes else 1.0) for n in graph.nodes}
    max_size = max(size_values.values()) or 1.0

    def marker_size(node: str) -> float:
        return 8 + 22 * math.sqrt(max(size_values[node], 0.0) / max_size) if sizes else 12

    path_set = set(highlight_path or [])
    for group in sorted(set(groups.values()), key=str):
        members = [n for n in graph.nodes if groups.get(n) == group]
        label = (group_names or {}).get(group, str(group))
        fig.add_trace(
            go.Scatter(
                x=[positions[n][0] for n in members],
                y=[positions[n][1] for n in members],
                mode="markers",
                name=f"{group_label}: {label}",
                marker=dict(
                    size=[marker_size(n) for n in members],
                    color=palette[group],
                    line=dict(width=[3 if n in path_set else 0.8 for n in members],
                              color=[PATH_COLOR if n in path_set else "white" for n in members]),
                    opacity=0.95,
                ),
                text=[_hover_text(graph, n, sizes) for n in members],
                hoverinfo="text",
            )
        )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.02, x=0, font=dict(size=11)))
    return _style(fig, height=height)


def _hover_text(graph: nx.Graph, node: str, sizes: Mapping[str, float] | None) -> str:
    attrs = graph.nodes[node]
    parts = [
        f"<b>{attrs.get('title', node)}</b>",
        f"{node} | {attrs.get('channel_name', '')}",
        f"Topic: {attrs.get('topic', '')}",
        f"Views: {attrs.get('views', 0):,} | Engagement: {attrs.get('engagement_rate', 0):.2f}%",
        f"Connections: {graph.degree(node)}",
    ]
    if sizes and node in sizes:
        parts.append(f"Size metric: {sizes[node]:.4f}")
    return "<br>".join(parts)


# --------------------------------------------------------------------------
# Performance and analytics charts
# --------------------------------------------------------------------------
def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None,
              horizontal: bool = False, height: int = 380, labels: dict | None = None) -> go.Figure:
    """Simple sorted bar chart with a consistent style."""
    if df.empty:
        return empty_figure("No data for the current filters.", height)
    data = df.copy()
    if horizontal:
        data = data.sort_values(x if x != "title" else y, ascending=True)
    fig = px.bar(data, x=x, y=y, color=color, orientation="h" if horizontal else "v",
                 color_discrete_map=colour_map(data[color].tolist()) if color else None,
                 color_discrete_sequence=[PRIMARY], labels=labels or {})
    if not color:
        fig.update_traces(marker_color=PRIMARY)
    return _style(fig, title, height)


def topic_bars(summary: pd.DataFrame, metric: str, title: str, label: str) -> go.Figure:
    """Bar chart of one summary metric for each topic or channel (first column)."""
    if summary.empty or len(summary.columns) == 0:
        return empty_figure("No data for the current filters.", 340)
    category = summary.columns[0]
    data = summary.sort_values(metric, ascending=False)
    fig = px.bar(data, x=category, y=metric, labels={metric: label, category: ""},
                 color=category, color_discrete_map=colour_map(summary[category].tolist()))
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=-30)
    return _style(fig, title, 340)


def views_vs_engagement(videos: pd.DataFrame, log_x: bool = True) -> go.Figure:
    """Scatter of views against engagement rate, coloured by topic."""
    if videos.empty:
        return empty_figure("No data for the current filters.")
    fig = px.scatter(
        videos, x="views", y="engagement_rate", color="topic",
        color_discrete_map=colour_map(videos["topic"].tolist()),
        hover_name="title",
        hover_data={"channel_name": True, "views": ":,", "engagement_rate": ":.2f", "topic": False},
        log_x=log_x,
        labels={"views": "Views" + (" (log scale)" if log_x else ""),
                "engagement_rate": "Engagement rate (%)", "topic": "Topic"},
    )
    fig.update_traces(marker=dict(size=9, opacity=0.8, line=dict(width=0.5, color="white")))
    return _style(fig, "Views vs engagement rate", 440)


def timeline_figure(timeline: pd.DataFrame) -> go.Figure:
    """Videos published per month (bars) with total views (line, right axis)."""
    if timeline.empty:
        return empty_figure("No data for the current filters.")
    fig = go.Figure()
    fig.add_bar(x=timeline["month"], y=timeline["videos"], name="Videos published", marker_color=PRIMARY, opacity=0.75)
    fig.add_scatter(x=timeline["month"], y=timeline["total_views"], name="Total views", yaxis="y2",
                    mode="lines+markers", line=dict(color=PATH_COLOR, width=2))
    fig.update_layout(yaxis=dict(title="Videos published"),
                      yaxis2=dict(title="Total views", overlaying="y", side="right", showgrid=False),
                      legend=dict(orientation="h", y=1.12, x=0))
    return _style(fig, "Publication timeline", 380)


def correlation_heatmap(corr: pd.DataFrame, title: str = "Correlation between metrics") -> go.Figure:
    """Annotated heatmap of a correlation matrix."""
    if corr.empty:
        return empty_figure("Need at least a few videos to calculate correlations.")
    fig = px.imshow(corr.round(2), text_auto=True, zmin=-1, zmax=1, color_continuous_scale="RdBu_r", aspect="auto")
    fig.update_coloraxes(colorbar=dict(title="r"))
    return _style(fig, title, 380)


def degree_distribution_figure(distribution: pd.DataFrame) -> go.Figure:
    """Bar chart: how many videos have each number of connections."""
    if distribution.empty:
        return empty_figure("No graph to summarise.")
    fig = px.bar(distribution, x="degree", y="videos", labels={"degree": "Connections (degree)", "videos": "Number of videos"})
    fig.update_traces(marker_color=PRIMARY)
    return _style(fig, "Degree distribution", 320)


def traffic_stacked_bar(traffic: pd.DataFrame) -> go.Figure:
    """Stacked bar of SIMULATED traffic-source shares per topic."""
    if traffic.empty:
        return empty_figure("No simulated traffic columns in this dataset.")
    names = {"sim_search_pct": "Search", "sim_suggested_pct": "Suggested videos",
             "sim_direct_pct": "Direct", "sim_external_pct": "External sites"}
    fig = go.Figure()
    for i, col in enumerate(SIMULATED_TRAFFIC_COLUMNS):
        fig.add_bar(x=traffic["topic"], y=traffic[col], name=names[col], marker_color=PALETTE[i])
    fig.update_layout(barmode="stack", yaxis_title="Share of views (%)")
    fig.update_xaxes(tickangle=-30)
    return _style(fig, "SIMULATED traffic-source mix by topic (demo values, not real analytics)", 400)


def dendrogram_figure(linkage_matrix: np.ndarray, p: int = 30) -> go.Figure:
    """Truncated dendrogram: the last ``p`` merges of hierarchical clustering."""
    tree = dendrogram(linkage_matrix, truncate_mode="lastp", p=p, no_plot=True)
    fig = go.Figure()
    for xs, ys in zip(tree["icoord"], tree["dcoord"]):
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color=PRIMARY, width=1.6),
                        hoverinfo="skip", showlegend=False)
    fig.update_xaxes(showticklabels=False, title=f"Clusters of videos (last {p} merges shown)")
    fig.update_yaxes(title="Merge distance (1 - similarity)")
    return _style(fig, "Hierarchical clustering dendrogram", 380)


def path_cost_bar(steps: list[dict]) -> go.Figure:
    """Cost of every step on a shortest path."""
    if not steps:
        return empty_figure("No steps to show.", 260)
    frame = pd.DataFrame(steps)
    frame["step"] = [f"Step {i + 1}" for i in range(len(frame))]
    fig = px.bar(frame, x="step", y="step_cost", hover_data=["from", "to", "similarity"],
                 labels={"step_cost": "Step cost (1 / similarity)", "step": ""})
    fig.update_traces(marker_color=PATH_COLOR)
    return _style(fig, "Cost of each step on the path", 280)
