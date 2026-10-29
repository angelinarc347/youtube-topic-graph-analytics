# Syllabus Mapping

How each syllabus topic appears in the project **YouTube Video Topic Network and Performance Analytics Using Graph Analytics**.

**Legend - how fully the project covers a topic**
* **Implemented** - calculated by code you can run and demonstrate.
* **Illustrated** - shown with simulated or limited public data, with the limitation stated.
* **Explained** - a concept covered in the documentation or dashboard text only (it cannot be computed from public video metadata).

> The demo dataset is synthetic. Where the syllabus asks for real traffic data (search, paid, direct), the project is honest that
> this needs YouTube Analytics access authorised by the channel owner or a dataset that contains those fields.

## A. Graph theory and algorithms

| # | Syllabus topic | Coverage | Where in the project | What to say / show |
|---|---|---|---|---|
| A1 | Origin and basics of graph theory (nodes, edges, graph types, operations) | Implemented + Explained | `src/graph_builder.py` (`build_graph`), README section 7, **Topic network** tab | Nodes = videos, edges = similarity links. Our graph is **undirected and weighted**. Filtering videos and changing the threshold are graph operations (subgraph, edge removal). |
| A2 | Graph properties: degree, density, connected components | Implemented | `network_properties`, `degree_distribution`; **Topic network** metrics row; **Network properties** sub-tab | Degree = number of links. Density = existing edges / possible edges. Components = separate islands; the app warns when the graph splits. |
| A3 | Best path and Dijkstra's algorithm | Implemented | `shortest_video_path`, `dijkstra_manual` (teaching version) in `src/graph_metrics.py`; **Shortest path** tab; tests in `tests/test_graph_metrics.py` | Cost of a step = `1 / similarity`; total cost = sum. The tab shows the path, cost, step table and highlights it on the map. A hand-written Dijkstra is checked against NetworkX. |
| A4 | Social network basics and navigation | Implemented + Explained | **Shortest path** tab, bridge videos table | Moving from one video to another through similar videos is "navigation". Bridge videos are the shortcuts between topic groups. (Our network is a similarity network, not a real social network.) |
| A5 | Small-world networks | Explained + Illustrated | `small_world_indicators`; **Network properties** sub-tab | Small-world = high clustering **and** short paths. The app compares both with a random graph and reports a sigma indicator, labelled "indicative only". It does not claim a finding. |
| A6 | Scale-free networks | Explained + Illustrated | `degree_summary`, degree-distribution chart | Scale-free = a few big hubs, many small nodes. The app shows the degree histogram and max/mean ratio but does **not** test for a power law, so it makes no scale-free claim. |
| A7 | Degree centrality | Implemented | `compute_centralities`; **Centrality & PageRank** sub-tab | Share of other videos a video is directly linked to. |
| A8 | Closeness centrality | Implemented | same | Inverse of the average distance to reachable videos (distance = `1/similarity`). |
| A9 | Betweenness centrality | Implemented | same; bridge-video table | How often a video lies on the cheapest paths between others. High betweenness = likely bridge. |
| A10 | Eigenvector centrality | Implemented | same, with convergence fallback | Links to well-connected videos matter more. If power iteration fails, an exact solver is used and the app explains it. |
| A11 | PageRank | Implemented | same | Importance from links by important videos. Graph-based - **not** YouTube's ranking. |
| A12 | Community detection | Implemented | `detect_communities`; **Communities & bridges** sub-tab | Greedy modularity. Shows modularity and each community's dominant topic and purity. Communities are algorithmic groups, not guaranteed categories. |
| A13 | Graph partitioning | Implemented | `kernighan_lin_partition`; **Partitioning & clustering** sub-tab | Splits the graph into two balanced halves with a minimum number of cut edges; reports edges cut. |
| A14 | Hierarchical clustering | Implemented | `hierarchical_clustering`, `dendrogram_figure`; same sub-tab | Real agglomerative clustering (average linkage on `1 - similarity`) with a dendrogram and a "number of clusters" slider. Kept separate from communities. |

## B. Web analytics, traffic, SEO and competitive intelligence

| # | Syllabus topic | Coverage | Where in the project | What to say / show |
|---|---|---|---|---|
| B1 | Web analytics introduction | Explained + Implemented | **Overview** and **Video performance** tabs | Web/video analytics = measuring what content does and why. Our KPIs: videos, edges, communities, total views, average engagement rate. |
| B2 | Choosing tools; tool pilot, SLA, vendor selection | Explained | This table; README section 14 | Not computable from data. Talking points: choose by questions asked (needs), data access/ownership, cost, export options; pilot a tool on a small channel set first; an SLA states uptime, support response and data-retention commitments. The project itself uses free, open-source tools (Streamlit, NetworkX, pandas) and states why in the README. |
| B3 | Great metrics and actionable tactics | Implemented + Explained | `src/performance_analytics.py`; **Video performance** tab | Good metrics are comparable, rate-based and tied to a decision: **engagement rate**, **views per day**, **like rate**, **comment rate** (not just raw views). Example action: topics with high engagement but low views are candidates for more promotion. |
| B4 | Traffic sources and outcomes | Illustrated (simulated) | `sim_*` columns, `traffic_stacked_bar`; expander in **Video performance** | Search / suggested / direct / external shares per topic. **Simulated for practice only.** Real values require YouTube Analytics access authorised by the channel owner. |
| B5 | Search quality, SEO, indexing | Illustrated + Explained | **Keyword (tag) analysis** section; `keyword_analysis` | Tags and titles are the keywords a platform can index. The app shows which keywords are used most and how those videos perform. Impressions and click-through rate (true search-quality signals) are not public. |
| B6 | Paid search and direct traffic | Explained | `sim_direct_pct`; `docs/project_report.md` | Direct traffic = viewers arriving without a referrer (typing a link, bookmark). Paid traffic comes from advertising accounts and is private. Only a simulated direct share is shown. |
| B7 | Testing ideas | Explained | Report section "Future enhancements" | Examples: A/B test two thumbnails or titles on similar videos, measuring engagement rate over equal time windows; use topic communities to pick comparable videos. |
| B8 | Competitive intelligence | Illustrated | Channel comparison chart; topic comparison charts | Compare channels and topics by views and engagement using public-style metadata. Competitors' private analytics cannot be accessed. |
| B9 | Website traffic analysis | Illustrated | Timeline chart; views-vs-engagement scatter | Publication timeline and views per day show how traffic builds over time. |
| B10 | Search / keyword analysis | Implemented | `keyword_analysis`; keyword table and chart | Frequency, average views and average engagement per tag; tags that link many topics are potential bridges. |
| B11 | Video performance | Implemented | **Video performance** tab; `structure_vs_performance` | Top videos by five metrics; topic and channel comparison; correlation heat-map; Spearman correlation between graph centrality and performance. |

## C. Mapping to files

| File | Syllabus topics supported |
|---|---|
| `src/data_loader.py` | B3 (metric definitions), data quality |
| `src/graph_builder.py` | A1, A2, A4 |
| `src/graph_metrics.py` | A2-A14 |
| `src/performance_analytics.py` | B1, B3, B5, B8-B11 |
| `src/visualizations.py` | all charts |
| `src/content.py` | plain-English explanations of A5-A14 and limits of B4-B8 |
| `tests/` | verification of A3, A7-A14 and B3 |

## D. Syllabus concepts and data limitations (summary)
* **Needs authorised YouTube Analytics access (or a dataset containing these fields):** true traffic sources, impressions, click-through rate, watch time, audience retention, revenue, and private channel analytics.
* **Available as public metadata through the official YouTube Data API (not used by default here):** titles, tags, publication dates, public view/like/comment counts - within quota limits.
* **This project's demo data:** fully synthetic; `sim_*` columns are invented and must never be presented as real statistics.
