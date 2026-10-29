# YouTube Video Topic Network and Performance Analytics Using Graph Analytics

**Project report**

| | |
|---|---|
| Student name | `[PLACEHOLDER: your full name]` |
| Roll / registration number | `[PLACEHOLDER]` |
| Course and programme | `[PLACEHOLDER: course name, programme]` |
| Lecturer | `[PLACEHOLDER]` |
| Submission date | `[PLACEHOLDER]` |
| Repository link | `[PLACEHOLDER: https://github.com/YOUR-USERNAME/YOUR-REPOSITORY]` |

> **How to edit this report:** it is a Markdown file. Open it in VS Code (press `Ctrl+Shift+V` for a preview), replace every
> `[PLACEHOLDER ...]`, add your own screenshots, and export to Word or PDF if your department requires it (for example with the
> "Markdown PDF" VS Code extension, or paste into Word). All numbers in section 7 were produced by this project on the included
> **synthetic** dataset - re-run the dashboard to confirm them before you present.

---

## Abstract
Online video catalogues are usually analysed as tables of views and likes, which hides how videos relate to one another.
This project models a collection of YouTube-style videos as a weighted, undirected graph in which videos are nodes and
edges express tag-and-topic similarity (Jaccard similarity of normalised tags plus a small same-topic bonus). Using Python,
pandas, NetworkX, Plotly and Streamlit, an interactive dashboard was built that calculates degree, closeness, betweenness and
eigenvector centrality, PageRank, communities, graph partitions, hierarchical clusters, network properties and Dijkstra
shortest paths, and relates them to performance metrics such as engagement rate and views per day. A synthetic 150-video
dataset with seven topic clusters and twelve deliberate cross-topic "bridge" videos was used so that the project runs offline
without an API key. On this dataset the graph (threshold 0.25) has 1,330 edges and seven communities with modularity 0.84,
and the videos with the highest betweenness are mostly the designed bridges. The report explains the method, its limits, and
why real traffic-source analytics need authorised YouTube Analytics access.

## 1. Introduction
Video platforms host content that viewers discover through search, recommendations and direct links. Understanding which
videos and topics are related helps creators plan series, cross-promote content and find gaps. Graph theory provides a
vocabulary (nodes, edges, paths, centrality, communities) and a toolbox of algorithms for studying relationships.
This project applies that toolbox to a video catalogue in a form that a student can run locally and explain.

## 2. Problem statement
Given metadata for a set of videos (topic, tags, views, likes, comments, publication date), how can we
(1) represent the relationships between videos, (2) identify important videos, groups of related videos and bridges between
groups, (3) find the best chain of related videos between two videos, and (4) examine whether position in the network is
associated with performance - using only free tools and without requiring a YouTube API key?

## 3. Objectives
1. Build a validated, reproducible video dataset (synthetic, clearly labelled).
2. Construct an explainable similarity graph with an adjustable threshold.
3. Implement and visualise the required graph algorithms (centrality, PageRank, communities, Dijkstra, partitioning, clustering).
4. Provide performance analytics by topic, channel, keyword and time.
5. Deliver a documented, tested, Git-ready project that runs in VS Code on Windows.
6. State clearly what public metadata can and cannot show (traffic sources, SEO, search quality).

## 4. Literature and context overview
*(Summarise in your own words; the sources below are official documentation and standard references to start from.)*
* **Graph theory** originates with Euler's analysis of the Konigsberg bridges (1736); modern network science extends it to social, web and information networks. Standard algorithms used here include Dijkstra's shortest-path algorithm (1959).
* **Centrality** measures quantify node importance in different ways: degree (local connectivity), closeness (average proximity), betweenness (control over paths), eigenvector centrality (connection to important nodes).
* **PageRank** (Brin and Page, 1998) ranks web pages by the importance of pages linking to them; here it is used only as a graph measure on the similarity network.
* **Community detection** by modularity maximisation (Newman; Clauset, Newman and Moore for the greedy variant) finds groups with dense internal links. **Graph partitioning** (Kernighan and Lin, 1970) divides a graph while minimising cut edges. **Hierarchical clustering** merges similar items into a tree (dendrogram).
* **Small-world** (Watts and Strogatz, 1998) and **scale-free** (Barabasi and Albert, 1999) networks are models of real-world network structure.
* **Web and video analytics** covers traffic sources, search/SEO, engagement and competitive analysis. Public metadata is available through the YouTube Data API within quota; audience and traffic-source analytics are private to the channel owner and need YouTube Analytics authorisation.

`[PLACEHOLDER: add 2-3 paragraphs in your own words and any lecture references your lecturer expects.]`

## 5. Methodology
### 5.1 Data
`data/youtube_videos.csv`: 150 synthetic videos, 14 fictional channels, 7 topics, publication dates 2024-01-08 to 2026-10-13.
Generated by `scripts/generate_sample_data.py` with a fixed random seed. Twelve hand-written videos mix tags from two topics
to act as bridges. Counts were generated independently of the graph, so any relationship between structure and performance
in this dataset is not evidence about real YouTube behaviour. Optional `sim_*` traffic-source columns are **simulated**.

Cleaning (`src/data_loader.py`): required-column check, duplicate-id check, removal (with warnings) of rows with blank fields,
invalid dates, or non-numeric/negative counts; tags are lower-cased, trimmed and de-duplicated.

### 5.2 Derived metrics
* engagement rate = (likes + comments) / views x 100 (0 if views = 0)
* like rate and comment rate = likes or comments / views x 100
* views per day = views / max(age in days, 1), age measured to the reference date 2026-10-28

### 5.3 Graph construction
Undirected weighted graph; node = video. For two videos A and B that share at least one tag:

`similarity(A, B) = min(1, Jaccard(tags A, tags B) + 0.15 if same topic)`

An edge exists if `similarity >= threshold` (default 0.25). Edge **weight** = similarity; edge **distance** = 1 / max(similarity, 1e-6).
Views are deliberately *not* used as weights: they measure popularity rather than relatedness.

### 5.4 Algorithms
| Algorithm | Cost/weight used | Library call |
|---|---|---|
| Degree, closeness, betweenness | distance (closeness, betweenness) | `nx.degree_centrality`, `nx.closeness_centrality`, `nx.betweenness_centrality` |
| Eigenvector centrality | weight; exact-solver fallback | `nx.eigenvector_centrality` / `_numpy` |
| PageRank | weight | `nx.pagerank` |
| Communities | weight | `nx.community.greedy_modularity_communities` |
| Partitioning | weight | `nx.community.kernighan_lin_bisection` |
| Hierarchical clustering | 1 - similarity | `scipy.cluster.hierarchy.linkage` (average) |
| Shortest path | distance | `nx.dijkstra_path` (verified against hand-written `dijkstra_manual`) |

## 6. System architecture and implementation
Layers: **data** (`data_loader`) -> **graph** (`graph_builder`) -> **analysis** (`graph_metrics`, `performance_analytics`) ->
**presentation** (`visualizations`, `content`, `app.py`). Each layer is a separate module with type hints and docstrings, which
makes the code testable without starting the web app. The Streamlit app caches expensive steps (candidate edges, centralities,
layout) so moving a slider stays fast. Errors are caught per dashboard section and reported in plain language; details are
written to the terminal log. See `README.md` (architecture diagram) and `docs/code_walkthrough.md`.

## 7. Results (included synthetic dataset, threshold 0.25)
*The numbers below were calculated by this project's code. Re-run the dashboard to confirm them; yours should match.*

### 7.1 Network structure
| Property | Value |
|---|---|
| Nodes / edges | 150 / 1,330 |
| Density | 0.119 |
| Average degree | 17.7 |
| Connected components | 1 (fully connected at this threshold; at 0.27 it already splits into 2 components) |
| Average clustering coefficient | 0.859 |
| Communities (greedy modularity) | 7, sizes 23, 23, 22, 21, 21, 21, 19; modularity 0.842 |
| Topic purity of communities | 100% (expected: topics were built to cluster) |
| Videos linked to another community ("bridge videos") | 31 |
| Kernighan-Lin bisection | 75 / 75 nodes, 101 of 1,330 edges cut (7.6%) |

### 7.2 Important videos
* **Highest betweenness (bridges):** "Using AI as a study partner: does it help?" (0.291), "Make a small game with Python in one weekend" (0.244), "Live recap: Indie Games night (Part 2)" (0.234), "Wearable gadgets: do they improve your training?" (0.199). Three of the top four are deliberately designed bridge videos.
* **Highest PageRank:** values lie in a narrow band (about 0.0086 to 0.0088 at the top) because the topic cliques are similar in size - PageRank is high for well-linked videos inside each cluster rather than singling out one winner.

### 7.3 Shortest path example
From "Street food tour: eating our way through a night market" (Travel) to "Make a small game with Python in one weekend" (Technology & AI):
6 steps, total cost 19.38, passing through cooking, baking-science, exam-prep and AI-study videos - showing that content from very different topics is linked
through chains of shared tags.

### 7.4 Performance
| Topic | Videos | Total views | Avg views | Avg engagement rate (%) |
|---|---|---|---|---|
| Entertainment | 19 | 3,258,810 | 171,516 | 3.7 |
| Gaming | 21 | 2,831,500 | 134,833 | 3.5 |
| Travel | 23 | 2,283,271 | 99,273 | 4.8 |
| Technology & AI | 23 | 2,118,930 | 92,127 | 4.4 |
| Cooking | 21 | 1,602,760 | 76,322 | 5.1 |
| Education | 22 | 1,396,064 | 63,458 | 6.3 |
| Fitness | 21 | 1,218,677 | 58,033 | 4.8 |

Topics with the most views (Entertainment, Gaming) have the lowest engagement rates, while Education has the highest engagement but fewer views.
The most-viewed video is the synthetic outlier "Filming locations you can actually visit" (1,276,275 views).

### 7.5 Structure vs performance
Spearman rank correlations between centrality and performance are weak (absolute values mostly below 0.25; the largest is closeness vs
engagement rate at 0.43). On this synthetic data that is expected, because views and engagement were generated independently of graph position.
Correlation does not imply causation.

### 7.6 Small-world indicators (indicative only)
Average clustering 0.859 vs about 0.118 for a random graph of the same size; average path length 4.47 hops vs about 1.74 estimated for a random graph; sigma 2.83.
High clustering is clear; the longer-than-random path length shows this graph is not a textbook small-world example. No scale-free claim is made (degree max/mean ratio is only 1.24).

### 7.7 Screenshots
`[PLACEHOLDER: Figure 1 - Overview tab with KPI cards]`
`[PLACEHOLDER: Figure 2 - Topic network coloured by topic]`
`[PLACEHOLDER: Figure 3 - Network coloured by community]`
`[PLACEHOLDER: Figure 4 - Centrality ranking (betweenness)]`
`[PLACEHOLDER: Figure 5 - Shortest path highlighted]`
`[PLACEHOLDER: Figure 6 - Topic comparison charts]`
*(Take screenshots from your own running dashboard and insert them here. Do not use images that were not produced by your own run.)*

## 8. Testing
`python -m pytest` runs 84 tests covering data validation, metric formulas, graph construction, centrality, Dijkstra,
communities, partitioning, clustering, analytics helpers, figure building and headless app smoke tests.
Recorded result at packaging time: **84 passed** (Linux, Python 3.12.3). `[PLACEHOLDER: paste your own result from Windows.]`

## 9. Limitations
* Synthetic data; real catalogues are noisier and communities will not map so neatly to topics.
* Similarity uses tags/topics only.
* Results depend on the threshold; the graph fragments at high thresholds.
* No live YouTube data, traffic sources, impressions, click-through rate, watch time or retention; those require authorised YouTube Analytics access.
* Small-world and scale-free discussion is indicative, not a statistical test.
* Designed for hundreds, not millions, of videos.

## 10. Conclusion
A similarity graph turns a list of videos into a structure that can be measured. On the demo data, communities recover the
seven topics, betweenness highlights the videos that connect topics, and Dijkstra finds explainable chains of related
videos. The project shows how syllabus topics - graph theory, shortest paths, centrality, PageRank, communities, and web/video analytics -
fit into one working, testable application, while being open about what public data cannot reveal.

## 11. Future enhancements
Optional YouTube Data API loader (with a key stored outside Git); text-similarity edges from titles and descriptions; directed
"recommended video" graphs; Louvain communities with a resolution control; A/B-style comparisons of comparable videos chosen from the same community;
deployment to Streamlit Community Cloud.

## References
1. Streamlit documentation - https://docs.streamlit.io/
2. NetworkX documentation - https://networkx.org/documentation/stable/
3. pandas documentation - https://pandas.pydata.org/docs/
4. Plotly Python documentation - https://plotly.com/python/
5. SciPy hierarchical clustering - https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html
6. YouTube Data API v3 - https://developers.google.com/youtube/v3
7. YouTube Analytics API - https://developers.google.com/youtube/analytics
8. Brin, S. and Page, L. (1998). The anatomy of a large-scale hypertextual web search engine.
9. Watts, D. and Strogatz, S. (1998). Collective dynamics of 'small-world' networks. Nature.
10. Barabasi, A.-L. and Albert, R. (1999). Emergence of scaling in random networks. Science.
11. Clauset, A., Newman, M. and Moore, C. (2004). Finding community structure in very large networks.
12. Kernighan, B. and Lin, S. (1970). An efficient heuristic procedure for partitioning graphs.
