"""Streamlit dashboard: YouTube Video Topic Network and Performance Analytics.

Run from the project folder with:
    python -m streamlit run app.py
"""

from __future__ import annotations

import hashlib
import io
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import networkx as nx
import pandas as pd
import streamlit as st

from src import content
from src.data_loader import (
    DEFAULT_DATA_PATH,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    SIMULATED_TRAFFIC_COLUMNS,
    DataValidationError,
    LoadResult,
    has_simulated_traffic,
    load_videos,
)
from src.graph_builder import (
    DEFAULT_THRESHOLD,
    build_graph,
    compute_candidate_edges,
    edge_table,
    graph_health_messages,
)
from src.graph_metrics import (
    CENTRALITY_COLUMNS,
    CommunityResult,
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
from src.performance_analytics import (
    TOP_METRICS,
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
    bar_chart,
    compute_layout,
    correlation_heatmap,
    degree_distribution_figure,
    dendrogram_figure,
    network_figure,
    path_cost_bar,
    timeline_figure,
    topic_bars,
    traffic_stacked_bar,
    views_vs_engagement,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dashboard")

st.set_page_config(page_title="YouTube topic network analytics", page_icon=None, layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #DDE3E9; border-radius: 8px; padding: 10px 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Cached helpers (so moving a slider does not recompute everything)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the dataset...")
def load_default_csv(path_text: str, modified: float) -> LoadResult:
    """Load the bundled CSV. ``modified`` makes the cache refresh if the file changes."""
    return load_videos(Path(path_text))


@st.cache_data(show_spinner="Reading your CSV file...")
def load_uploaded_csv(raw: bytes) -> LoadResult:
    return load_videos(io.BytesIO(raw))


@st.cache_data(show_spinner=False)
def cached_candidate_edges(data_key: str, _videos: pd.DataFrame) -> pd.DataFrame:
    return compute_candidate_edges(_videos)


@st.cache_data(show_spinner="Calculating graph metrics...")
def cached_analysis(key: tuple, _graph: nx.Graph) -> tuple[pd.DataFrame, list[str], CommunityResult]:
    centralities, notes = compute_centralities(_graph)
    return centralities, notes, detect_communities(_graph)


@st.cache_data(show_spinner=False)
def cached_layout(key: tuple, _graph: nx.Graph) -> dict[str, tuple[float, float]]:
    return compute_layout(_graph)


@contextmanager
def section_guard(name: str) -> Iterator[None]:
    """Show a friendly error (and log the details) instead of a raw traceback."""
    try:
        yield
    except Exception:  # noqa: BLE001 - reported to the user and logged with the traceback
        logger.exception("Problem while building section: %s", name)
        st.error(
            f"Something went wrong while building **{name}**. Try loosening the filters or "
            "lowering the similarity threshold. Details were written to the terminal log."
        )


def show_chart(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key)


def show_table(df: pd.DataFrame, **kwargs) -> None:
    st.dataframe(df, width="stretch", hide_index=True, **kwargs)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
st.title("YouTube topic network and performance analytics")
st.caption("Explore how videos connect through shared topics and tags, which videos bridge topic groups, "
           "and how graph structure relates to performance.")

st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader(
    "Use your own CSV (optional)", type=["csv"],
    help="Must contain the required columns listed in the Data & methodology tab. "
         "Leave empty to use the included synthetic demo dataset.",
)

try:
    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        load_result = load_uploaded_csv(raw_bytes)
        data_key = "upload:" + hashlib.md5(raw_bytes).hexdigest()
        source_label = f"Uploaded file: {uploaded.name}"
        is_demo = False
    else:
        modified = DEFAULT_DATA_PATH.stat().st_mtime if DEFAULT_DATA_PATH.exists() else 0.0
        load_result = load_default_csv(str(DEFAULT_DATA_PATH), modified)
        data_key = f"default:{modified}"
        source_label = "Included demo CSV (synthetic)"
        is_demo = True
except DataValidationError as error:
    st.error(f"The dataset could not be loaded. {error}")
    st.info("Fix the CSV and upload it again, or remove the uploaded file to use the included demo data.")
    st.stop()

all_videos = load_result.data
all_edges = cached_candidate_edges(data_key, all_videos)

# --------------------------------------------------------------------------
# Sidebar filters (stored in session_state so "Reset filters" works)
# --------------------------------------------------------------------------
min_date = all_videos["published_at"].min().date()
max_date = all_videos["published_at"].max().date()
defaults = {
    "f_topics": sorted(all_videos["topic"].unique()),
    "f_channels": sorted(all_videos["channel_name"].unique()),
    "f_dates": (min_date, max_date),
    "f_min_views": 0,
    "f_threshold": DEFAULT_THRESHOLD,
}
st.session_state["_defaults"] = defaults


def reset_filters() -> None:
    for key, value in st.session_state["_defaults"].items():
        st.session_state[key] = value


if st.session_state.get("_data_key") != data_key:
    reset_filters()  # a different dataset has different topics/channels/dates
    st.session_state["_data_key"] = data_key

st.sidebar.header("Filters")
st.sidebar.multiselect("Topics", defaults["f_topics"], key="f_topics")
st.sidebar.multiselect("Channels", defaults["f_channels"], key="f_channels")
st.sidebar.date_input("Publication date range", min_value=min_date, max_value=max_date, key="f_dates")
st.sidebar.number_input("Minimum views", min_value=0, step=1000, key="f_min_views")
st.sidebar.header("Graph")
st.sidebar.slider(
    "Minimum similarity for an edge", min_value=0.05, max_value=0.90, step=0.01, key="f_threshold",
    help="Two videos are connected only if their similarity score is at least this value. "
         "Higher values give fewer, stronger links.",
)
st.sidebar.button("Reset filters", on_click=reset_filters)

date_choice = st.session_state["f_dates"]
if isinstance(date_choice, (tuple, list)) and len(date_choice) == 2:
    date_range = (pd.Timestamp(date_choice[0]), pd.Timestamp(date_choice[1]))
else:
    date_range = (pd.Timestamp(min_date), pd.Timestamp(max_date))
    st.sidebar.info("Pick both a start and an end date. Showing the full date range for now.")

threshold = float(st.session_state["f_threshold"])
videos = apply_filters(
    all_videos,
    topics=list(st.session_state["f_topics"]),
    channels=list(st.session_state["f_channels"]),
    date_range=date_range,
    min_views=int(st.session_state["f_min_views"]),
)

st.sidebar.divider()
st.sidebar.subheader("Dataset status")
st.sidebar.write(f"**Source:** {source_label}")
st.sidebar.write(f"**Videos:** {len(videos)} shown of {len(all_videos)} loaded")
st.sidebar.write("**Data type:** " + ("synthetic demo data" if is_demo else "your own data"))
if load_result.warnings:
    st.sidebar.warning(f"{len(load_result.warnings)} data warning(s) - see Data & methodology.")

if videos.empty:
    st.warning("No videos match the current filters. Widen the filters or press **Reset filters** in the sidebar.")
    st.stop()

# --------------------------------------------------------------------------
# Graph and analysis
# --------------------------------------------------------------------------
graph = build_graph(videos, all_edges, threshold)
analysis_key = (data_key, round(threshold, 4), tuple(videos["video_id"]))
centralities, centrality_notes, communities = cached_analysis(analysis_key, graph)
positions = cached_layout(analysis_key, graph)
membership = communities.membership
metrics_export = export_table(videos, centralities, membership)
health_messages = graph_health_messages(graph)
titles = dict(zip(videos["video_id"], videos["title"]))

st.sidebar.download_button(
    "Download filtered data and metrics (CSV)", csv_bytes(metrics_export),
    file_name="filtered_videos_with_metrics.csv", mime="text/csv", key="dl_sidebar",
)

tab_overview, tab_perf, tab_network, tab_central, tab_path, tab_data = st.tabs(
    ["Overview", "Video performance", "Topic network", "Centrality & communities", "Shortest path", "Data & methodology"]
)

# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------
with tab_overview:
    with section_guard("Overview"):
        st.info(content.DEMO_DATA_NOTICE if is_demo else content.UPLOADED_DATA_NOTICE)
        kpi = overview_kpis(videos, graph.number_of_edges(), communities.multi_node_count)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Videos", f"{kpi['videos']:,}")
        c2.metric("Graph edges", f"{kpi['edges']:,}")
        c3.metric("Communities", f"{kpi['communities']:,}",
                  help="Groups with at least two videos found by greedy modularity.")
        c4.metric("Total views", f"{kpi['total_views']:,}")
        c5.metric("Avg engagement rate", f"{kpi['avg_engagement']:.2f}%",
                  help="(likes + comments) / views x 100, averaged over the videos shown.")
        for message in health_messages:
            st.warning(message)
        with st.expander("How to use this dashboard", expanded=True):
            st.markdown(content.HOW_TO_USE)
        left, right = st.columns(2)
        with left:
            show_chart(topic_bars(summarise_by(videos, "topic"), "total_views", "Total views by topic", "Total views"),
                       "ov_topic_views")
        with right:
            st.markdown("**Top 5 videos by views**")
            show_table(top_videos(videos, "views", 5)[["title", "channel_name", "topic", "views", "engagement_rate"]],
                       column_config={"engagement_rate": st.column_config.NumberColumn("engagement %", format="%.2f"),
                                      "views": st.column_config.NumberColumn(format="%d")})

# --------------------------------------------------------------------------
# Video performance
# --------------------------------------------------------------------------
with tab_perf:
    with section_guard("Video performance"):
        st.subheader("Top videos")
        pc1, pc2 = st.columns([2, 1])
        metric_label = pc1.selectbox("Rank by", list(TOP_METRICS), key="perf_metric")
        top_n = pc2.slider("How many videos", 5, 20, 10, key="perf_n")
        metric_col = TOP_METRICS[metric_label]
        ranked = top_videos(videos, metric_col, top_n)
        ranked["video"] = ranked["title"].str.slice(0, 48)
        show_chart(bar_chart(ranked, metric_col, "video", f"Top {top_n} videos by {metric_label.lower()}",
                             horizontal=True, height=max(320, 28 * top_n + 90),
                             labels={metric_col: metric_label, "video": ""}), "perf_top_bar")
        show_table(ranked.drop(columns=["video"]),
                   column_config={"engagement_rate": st.column_config.NumberColumn("engagement %", format="%.2f"),
                                  "views_per_day": st.column_config.NumberColumn("views/day", format="%.1f")})

        st.subheader("Topic comparison")
        topic_summary = summarise_by(videos, "topic")
        t1, t2 = st.columns(2)
        with t1:
            show_chart(topic_bars(topic_summary, "videos", "Number of videos", "Videos"), "topic_count")
            show_chart(topic_bars(topic_summary, "avg_views", "Average views", "Average views"), "topic_avg_views")
        with t2:
            show_chart(topic_bars(topic_summary, "total_views", "Total views", "Total views"), "topic_total_views")
            show_chart(topic_bars(topic_summary, "avg_engagement_rate", "Average engagement rate (%)", "Engagement %"),
                       "topic_engagement")

        st.subheader("Channel comparison")
        channel_options = {"Total views": "total_views", "Average views": "avg_views",
                           "Average engagement rate (%)": "avg_engagement_rate", "Number of videos": "videos"}
        channel_label = st.selectbox("Compare channels by", list(channel_options), key="channel_metric")
        show_chart(topic_bars(summarise_by(videos, "channel_name"), channel_options[channel_label],
                              f"Channels: {channel_label.lower()}", channel_label), "channel_bar")

        st.subheader("Views vs engagement")
        log_x = st.checkbox("Use a log scale for views", value=True, key="log_views",
                            help="A few very popular videos can squash the rest. A log scale keeps every video readable.")
        show_chart(views_vs_engagement(videos, log_x), "scatter_views_eng")

        st.subheader("Publication timeline")
        show_chart(timeline_figure(monthly_timeline(videos)), "timeline")

        st.subheader("Correlation between metrics")
        show_chart(correlation_heatmap(correlation_matrix(videos)), "corr_heat")
        st.caption(content.CORRELATION_WARNING)

        st.subheader("Keyword (tag) analysis")
        keywords = keyword_analysis(videos)
        if keywords.empty:
            st.info("No tag is used by at least two videos in the current selection.")
        else:
            k1, k2 = st.columns([1, 1])
            with k1:
                show_chart(bar_chart(keywords.head(15), "videos", "keyword", "Most-used keywords", horizontal=True,
                                     height=460, labels={"videos": "Videos using the tag", "keyword": ""}), "kw_bar")
            with k2:
                show_table(keywords.head(25), column_config={
                    "avg_views": st.column_config.NumberColumn("avg views", format="%d"),
                    "avg_engagement_rate": st.column_config.NumberColumn("avg engagement %", format="%.2f")})

        with st.expander("Simulated traffic sources (demo values - not real analytics)"):
            if has_simulated_traffic(videos):
                st.warning("These percentages are **simulated** for teaching. Real traffic-source data comes from "
                           "YouTube Analytics and needs the channel owner's authorisation.")
                show_chart(traffic_stacked_bar(simulated_traffic_by_topic(videos)), "traffic_bar")
            else:
                st.info("This dataset has no simulated traffic columns, so this section is empty. "
                        "Real traffic-source data would need YouTube Analytics access.")

# --------------------------------------------------------------------------
# Topic network
# --------------------------------------------------------------------------
with tab_network:
    with section_guard("Topic network"):
        st.markdown("Each dot is a video. A line means two videos are similar enough to meet the threshold. "
                    "Videos that share many tags are pulled close together.")
        n1, n2, n3 = st.columns(3)
        colour_by = n1.radio("Colour dots by", ["Topic", "Community"], horizontal=True, key="net_colour")
        size_label = n2.selectbox("Dot size shows", ["Same size", "Degree", "PageRank", "Betweenness", "Closeness",
                                                      "Eigenvector"], key="net_size")
        edge_choice = n3.select_slider("Lines drawn per video", options=[2, 3, 4, 6, 8, "All"], value=4, key="net_edges",
                                       help="Only changes the picture. All metrics use every edge.")
        centrality_lookup = centralities.set_index("video_id")
        size_map = None
        if size_label != "Same size":
            size_map = centrality_lookup[size_label.lower()].fillna(0.0).to_dict()
        community_names = {}
        topic_table = community_topic_table(graph, communities)
        for row in topic_table.itertuples(index=False):
            community_names[row.community] = f"{row.community} ({row.dominant_topic})"
        if colour_by == "Topic":
            groups = {n: graph.nodes[n]["topic"] for n in graph}
            figure = network_figure(graph, positions, groups, "Topic", size_map,
                                    None if edge_choice == "All" else int(edge_choice))
        else:
            figure = network_figure(graph, positions, membership, "Community", size_map,
                                    None if edge_choice == "All" else int(edge_choice), group_names=community_names)
        show_chart(figure, "network_main")
        for message in health_messages:
            st.warning(message)

        props = network_properties(graph)
        p1, p2, p3, p4, p5, p6 = st.columns(6)
        p1.metric("Nodes", props["nodes"])
        p2.metric("Edges", props["edges"])
        p3.metric("Density", f"{props['density']:.3f}", help="Share of all possible edges that exist.")
        p4.metric("Average degree", f"{props['average_degree']:.1f}", help="Average number of connections per video.")
        p5.metric("Components", props["components"], help="Separate islands of connected videos.")
        p6.metric("Avg clustering", f"{props['average_clustering']:.2f}",
                  help="How often two neighbours of a video are also linked to each other.")
        with st.expander("How are edges decided?"):
            st.markdown(content.SIMILARITY_FORMULA)
        with st.expander("Edge list (strongest first)"):
            edges_df = edge_table(graph).sort_values("similarity", ascending=False)
            show_table(edges_df.head(200))
            st.download_button("Download all edges (CSV)", csv_bytes(edges_df), "graph_edges.csv", "text/csv",
                               key="dl_edges")

# --------------------------------------------------------------------------
# Centrality & communities
# --------------------------------------------------------------------------
with tab_central:
    with section_guard("Centrality & communities"):
        sub_cent, sub_comm, sub_part, sub_props = st.tabs(
            ["Centrality & PageRank", "Communities & bridges", "Partitioning & clustering", "Network properties"]
        )

        with sub_cent:
            for note in centrality_notes:
                st.info(note)
            with st.expander("What do these measures mean?"):
                for _, (label, text) in content.CENTRALITY_HELP.items():
                    st.markdown(f"**{label}** - {text}")
            measure = st.selectbox("Rank videos by", CENTRALITY_COLUMNS, index=4,
                                   format_func=lambda m: content.CENTRALITY_HELP[m][0], key="cent_measure")
            joined = centralities.merge(videos[["video_id", "title", "channel_name", "topic"]], on="video_id")
            joined["community"] = joined["video_id"].map(membership)
            ranked_c = joined.sort_values(measure, ascending=False)
            chart_df = ranked_c.head(12).assign(video=lambda d: d["title"].str.slice(0, 48))
            show_chart(bar_chart(chart_df, measure, "video", f"Top 12 videos by {content.CENTRALITY_HELP[measure][0].lower()}",
                                 color="topic", horizontal=True, height=460, labels={"video": ""}), "cent_bar")
            table_cols = ["video_id", "title", "topic", "community", *CENTRALITY_COLUMNS]
            show_table(ranked_c[table_cols].head(25).round(4))
            st.download_button("Download graph metrics (CSV)", csv_bytes(joined[table_cols].round(6)),
                               "graph_metrics.csv", "text/csv", key="dl_metrics")

        with sub_comm:
            st.markdown(content.COMMUNITY_HELP)
            m1, m2, m3 = st.columns(3)
            m1.metric("Communities (2+ videos)", communities.multi_node_count)
            m2.metric("Modularity", f"{communities.modularity:.3f}")
            m3.metric("Videos not in any group", sum(1 for s in communities.sizes.values() if s == 1))
            st.markdown("**Community summary**")
            show_table(topic_table)
            st.caption("Topic purity = share of a community's videos that belong to its most common topic. "
                       "On the synthetic data the topics were built to cluster, so purity is high; real data is messier.")
            st.markdown("**Bridge videos** - linked to videos in other communities, ranked by betweenness")
            bridges = find_bridge_videos(graph, membership, centrality_lookup["betweenness"])
            if bridges.empty:
                st.info("No video links two communities at this threshold. Lower the threshold to see bridges.")
            else:
                show_table(bridges.head(12), column_config={
                    "betweenness": st.column_config.NumberColumn(format="%.3f")})
            st.markdown("**Average performance by community**")
            show_table(community_performance(videos, membership).round(2))

        with sub_part:
            st.markdown(content.PARTITION_HELP)
            bisection = kernighan_lin_partition(graph)
            if bisection is None:
                st.info("At least two videos are needed to split the graph.")
            else:
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Half A", len(bisection.part_a))
                b2.metric("Half B", len(bisection.part_b))
                b3.metric("Edges cut", bisection.cut_edges)
                share = bisection.cut_edges / graph.number_of_edges() if graph.number_of_edges() else 0.0
                b4.metric("Share of edges cut", f"{share:.1%}")
                halves = {n: ("Half A" if n in bisection.part_a else "Half B") for n in graph}
                show_chart(network_figure(graph, positions, halves, "Partition", None, 3, height=480), "kl_network")
            st.markdown(content.HIERARCHICAL_HELP)
            max_clusters = max(2, min(12, len(videos)))
            k_clusters = st.slider("Number of clusters to cut the tree into", 2, max_clusters, min(7, max_clusters),
                                   key="hier_k")
            hierarchical = hierarchical_clustering(videos, all_edges, k_clusters)
            if hierarchical is None:
                st.info("Hierarchical clustering needs at least three videos.")
            else:
                show_chart(dendrogram_figure(hierarchical.linkage_matrix), "dendrogram")
                crosstab = pd.crosstab(videos["topic"], videos["video_id"].map(hierarchical.clusters))
                crosstab.columns = [f"Cluster {c}" for c in crosstab.columns]
                st.markdown("**How the clusters line up with topics** (number of videos)")
                st.dataframe(crosstab, width="stretch")

        with sub_props:
            st.markdown(content.SMALL_WORLD_HELP)
            show_chart(degree_distribution_figure(degree_distribution(graph)), "degree_dist")
            ds = degree_summary(graph)
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Mean degree", f"{ds['mean']:.1f}")
            d2.metric("Median degree", f"{ds['median']:.0f}")
            d3.metric("Max degree", f"{ds['max']:.0f}")
            d4.metric("Max / mean", f"{ds['max_to_mean']:.2f}",
                      help="A scale-free network has hubs far above the mean (a large ratio). A ratio near 1 means "
                           "degrees are fairly even. The dashboard does not test for a power law.")
            indicators = small_world_indicators(graph)
            if indicators.get("valid"):
                s1, s2, s3 = st.columns(3)
                s1.metric("Clustering vs random", f"{indicators['average_clustering']:.2f} vs "
                                                  f"{indicators['clustering_random_estimate']:.2f}")
                s2.metric("Path length vs random", f"{indicators['average_path_length_hops']:.2f} vs "
                                                   f"{indicators['path_length_random_estimate']:.2f}")
                s3.metric("Small-world sigma", f"{indicators['sigma']:.2f}")
                st.caption(str(indicators["note"]))
            else:
                st.info(str(indicators.get("note", "Indicators unavailable.")))
            st.markdown("**Does graph structure relate to performance?** (Spearman rank correlation)")
            relation = structure_vs_performance(videos, centralities)
            if relation.empty:
                st.info("At least five videos are needed for this comparison.")
            else:
                show_chart(correlation_heatmap(relation.round(2), "Centrality vs performance"), "struct_perf")
                st.caption(content.CORRELATION_WARNING + " In synthetic data these values mostly reflect how the data was generated.")

# --------------------------------------------------------------------------
# Shortest path
# --------------------------------------------------------------------------
with tab_path:
    with section_guard("Shortest path"):
        st.markdown(content.DIJKSTRA_HELP)
        options = sorted(graph.nodes)
        if len(options) < 2:
            st.info("Select at least two videos with the filters to find a path.")
        else:
            first_topic, last_topic = sorted(videos["topic"].unique())[0], sorted(videos["topic"].unique())[-1]
            default_source = videos.loc[videos["topic"] == first_topic, "video_id"].iloc[0]
            default_target = videos.loc[videos["topic"] == last_topic, "video_id"].iloc[-1]
            if default_source == default_target:
                default_target = options[-1] if options[-1] != default_source else options[0]
            for key, fallback in (("path_src", default_source), ("path_dst", default_target)):
                if st.session_state.get(key) not in options:
                    st.session_state[key] = fallback
            label = lambda vid: f"{titles[vid]} ({vid})"  # noqa: E731
            sc1, sc2 = st.columns(2)
            source = sc1.selectbox("From video", options, format_func=label, key="path_src")
            target = sc2.selectbox("To video", options, format_func=label, key="path_dst")
            result = shortest_video_path(graph, source, target)
            if not result.found:
                st.warning(result.message)
            else:
                r1, r2, r3 = st.columns(3)
                r1.metric("Steps (edges)", len(result.nodes) - 1)
                r2.metric("Total cost", f"{result.total_cost:.2f}", help="Sum of 1 / similarity over every step.")
                if result.steps:
                    average_similarity = sum(s["similarity"] for s in result.steps) / len(result.steps)
                else:
                    average_similarity = 1.0
                r3.metric("Average similarity per step", f"{average_similarity:.2f}")
                st.success(result.message)
                path_groups = {n: graph.nodes[n]["topic"] for n in graph}
                show_chart(network_figure(graph, positions, path_groups, "Topic", None, 2,
                                          highlight_path=result.nodes, height=520), "path_network")
                if result.steps:
                    st.markdown("**Path step by step**")
                    show_table(pd.DataFrame(result.steps))
                    show_chart(path_cost_bar(result.steps), "path_cost")
                manual_nodes, manual_cost = dijkstra_manual(graph, source, target)
                agrees = manual_nodes == result.nodes or abs(manual_cost - result.total_cost) < 1e-9
                with st.expander("Check: the step-by-step Dijkstra gives the same cost"):
                    st.write(f"Teaching implementation (`dijkstra_manual`): cost **{manual_cost:.4f}** over "
                             f"**{len(manual_nodes) - 1}** step(s). NetworkX: cost **{result.total_cost:.4f}**. "
                             + ("They agree." if agrees else "They differ - please report this as a bug."))

# --------------------------------------------------------------------------
# Data & methodology
# --------------------------------------------------------------------------
with tab_data:
    with section_guard("Data & methodology"):
        st.subheader("Dataset status")
        s1, s2, s3 = st.columns(3)
        s1.metric("Rows read", load_result.rows_read)
        s2.metric("Rows kept after cleaning", load_result.rows_kept)
        s3.metric("Rows after your filters", len(videos))
        st.write(f"**Source:** {source_label}")
        if load_result.warnings:
            for warning in load_result.warnings:
                st.warning(warning)
        else:
            st.success("No data problems were found when the file was loaded.")

        st.subheader("Required columns")
        schema = pd.DataFrame({
            "column": [*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS, *SIMULATED_TRAFFIC_COLUMNS],
            "required": ["yes"] * len(REQUIRED_COLUMNS) + ["no"] * (len(OPTIONAL_COLUMNS) + len(SIMULATED_TRAFFIC_COLUMNS)),
            "meaning": [
                "Unique id for each video", "Video title", "Channel name", "Publication date (YYYY-MM-DD)",
                "Length in minutes", "View count (0 or more)", "Like count (0 or more)", "Comment count (0 or more)",
                "Main topic label", "Keywords separated by semicolons, e.g. ai;python;tutorial",
                "Short description (optional)", "Video link (optional; blank in the demo data)",
                "SIMULATED % of views from search (demo only)", "SIMULATED % from suggested videos (demo only)",
                "SIMULATED % from direct visits (demo only)", "SIMULATED % from external sites (demo only)",
            ],
        })
        show_table(schema)

        st.subheader("Preview of the filtered data")
        preview = videos.drop(columns=["tags_list"]).head(50)
        show_table(preview)
        st.download_button("Download filtered data and metrics (CSV)", csv_bytes(metrics_export),
                           "filtered_videos_with_metrics.csv", "text/csv", key="dl_data_tab")

        st.subheader("Formulas")
        st.markdown(content.SIMILARITY_FORMULA)
        st.markdown(
            "**Performance metrics**\n\n"
            "* `engagement_rate = (likes + comments) / views x 100` (0 when views = 0)\n"
            "* `like_rate = likes / views x 100`, `comment_rate = comments / views x 100`\n"
            "* `views_per_day = views / max(age in days, 1)`; age is counted from the publication date to the "
            "reference date **2026-10-28** (set in `src/data_loader.py`)."
        )

        st.subheader("Syllabus concepts and data limitations")
        st.markdown(content.SYLLABUS_LIMITS)

        st.subheader("Live YouTube data (not included)")
        st.markdown(
            "The dashboard works fully offline with the included CSV and needs **no API key**. A live-data feature using the "
            "official YouTube Data API is listed as future work in the README: it would need your own API key kept in an "
            "environment variable or Streamlit secrets (never committed to Git), and it is limited by API quota. "
            "Public metadata from the API is different from private YouTube Analytics data, which needs the channel owner's authorisation."
        )
