# Code Walkthrough for Beginners

This guide explains the project in plain language so you can understand it and present it. You do not need to memorise
the code - you need to be able to explain **what each file does and why**.

## 1. The big idea in one paragraph
We have a table of videos. We decide that two videos are "related" when they use the same keywords (tags). We draw each video
as a dot and each relationship as a line. That picture is a **graph**. Once we have a graph we can ask graph questions:
*Which dot has the most lines? Which dot connects two groups? What is the best chain of dots from video A to video B?
Which dots form natural groups?* Finally we compare those answers with ordinary performance numbers (views, engagement).

## 2. The journey of the data (follow one video through the system)
1. **`data/youtube_videos.csv`** - one row per video: title, channel, topic, tags, views, likes, comments...
2. **`src/data_loader.py`** - reads the CSV, checks it is valid (no duplicate ids, no negative views...), cleans the tags
   (`"AI; Python ;ai"` becomes `["ai", "python"]`) and calculates engagement rate and views per day.
3. **`src/performance_analytics.py` (`apply_filters`)** - keeps only the videos you selected in the sidebar.
4. **`src/graph_builder.py`** - compares every pair of videos that share a tag, gives each pair a **similarity score**, and keeps the pairs above the threshold as **edges** of a NetworkX graph.
5. **`src/graph_metrics.py`** - runs the algorithms on that graph (centrality, PageRank, communities, shortest path...).
6. **`src/visualizations.py`** - turns tables and graphs into interactive Plotly charts.
7. **`app.py`** - the Streamlit page that wires everything together: sidebar, tabs, buttons, downloads.

## 3. File by file

### `app.py` - the dashboard
* Streamlit re-runs this whole file from top to bottom every time you click or move a slider. That is why the code is a long script of "read the sidebar, then draw the tabs".
* `@st.cache_data` functions remember results so heavy calculations (centrality, layout) are not repeated when nothing relevant changed.
* `st.session_state` stores the filter values; the **Reset filters** button simply writes the default values back.
* `section_guard(...)` wraps each tab: if something unexpected fails, you see a friendly red message instead of a Python traceback, and the technical details go to the terminal log.

### `src/data_loader.py` - get clean, safe data
* `validate_and_clean` is the gatekeeper. *Fatal* problems (missing column, duplicate id, empty file) stop with a clear message. *Repairable* problems (a row with a negative view count) are removed **and reported** as warnings.
* `compute_derived_metrics` creates `engagement_rate`, `like_rate`, `comment_rate`, `views_per_day`. It never divides by zero: zero views gives 0, and a video's age is at least 1 day.
* `normalize_tags` makes tags comparable (lower-case, trimmed, no duplicates).

### `src/graph_builder.py` - decide who is connected
* **Jaccard similarity** = shared tags / all different tags. Example: A has {ai, python, tutorial}, B has {python, tutorial, gadgets}. Shared = 2 (python, tutorial); all different = 4 -> 2/4 = 0.5.
* We add 0.15 if the two videos have the same topic ("topic bonus"), capped at 1.
* `compute_candidate_edges` builds a list of all pairs that share a tag (using a tag -> videos index so it does not need to compare everything with everything). This list does not depend on the threshold.
* `build_graph` applies the threshold slider: keep an edge only if `similarity >= threshold`. Each edge stores a **weight** (the similarity) and a **distance** (`1 / similarity`).
* Why two numbers? "Weight" answers *how strong is the link?* (bigger = better). "Distance" answers *how costly is it to travel along the link?* (smaller = better). Shortest-path algorithms need costs, so we convert.

### `src/graph_metrics.py` - the algorithms
| Function | What it does | Everyday analogy |
|---|---|---|
| `compute_centralities` | Five importance scores per video | Who is popular, who is central, who is a connector, who knows important people, who gets the most traffic |
| `detect_communities` | Finds groups that are denser inside than outside | Friend groups in a school |
| `find_bridge_videos` | Videos linked to a different community | A student who belongs to two friend groups |
| `kernighan_lin_partition` | Splits the graph into two equal halves with the fewest cut links | Splitting a class into two teams while separating as few friends as possible |
| `hierarchical_clustering` | Repeatedly merges the two most similar groups into a tree | Building a family tree of similarity |
| `shortest_video_path` | Dijkstra with `distance` as cost | A GPS finding the cheapest route; a link costs less when the videos are more similar |
| `dijkstra_manual` | The same algorithm written step by step with a priority queue | Shows exactly how Dijkstra works; used to double-check NetworkX |
| `network_properties`, `degree_distribution`, `small_world_indicators` | Describe the whole network | Measuring the shape of a city's road map |

**Dijkstra in four lines:** (1) give the start node cost 0 and everyone else infinity; (2) take the cheapest unfinished node;
(3) for each neighbour, check if going through this node is cheaper than the best cost known so far, and if so update it;
(4) repeat until the target node is finished. The answer is the path of the lowest total cost.

### `src/performance_analytics.py` - numbers about performance
Plain pandas: `groupby` for topic and channel summaries, `explode` to count tags, `corr` for correlations.
`structure_vs_performance` uses **Spearman** (rank-based) correlation so a few viral videos do not distort the result.

### `src/visualizations.py` - charts
Each function receives data and returns a Plotly figure. `network_figure` draws lines as one trace (fast) and dots as one trace per colour group (so the legend works). `strongest_edges` is only for drawing - it hides weaker lines to reduce clutter, but all calculations still use every edge.

### `src/content.py` - text
Explanations and the "How to use" instructions live here, so the logic files stay clean and you can edit wording without touching the code.

### `scripts/generate_sample_data.py` - the synthetic dataset
Uses a fixed random seed so everyone gets the same file. It creates 7 topic clusters with their own tag vocabularies, adds a few generic tags
shared by all topics, and hand-writes 12 cross-topic **bridge** videos. Counts are random numbers shaped to look plausible. **Nothing in it is real YouTube data.**

### `tests/` - proof that it works
Each test is a small question with a known answer, e.g. "does a video with 1,000 views, 50 likes and 10 comments have a 6.0% engagement rate?", "does Dijkstra choose the two-step route (cost 2) over the direct edge (cost 5)?", "do two cliques joined by one edge become two communities?". Run them with `python -m pytest`.

## 4. Design decisions you can justify
* **Similarity graph, not views as weights** - views measure popularity, not relatedness.
* **Threshold slider** - lets you show how structure changes: low = dense hairball; high = separate islands.
* **Plotly instead of PyVis** - fewer fragile dependencies, works reliably inside Streamlit.
* **Pinned versions** - the same versions that were tested, so installs behave the same on your laptop.
* **Honest labels** - synthetic data, simulated traffic, "indicators" for small-world, and "not YouTube's algorithm" for PageRank.
* **Hierarchical clustering implemented separately** - so we never call a community partition "hierarchical".

## 5. Questions a lecturer might ask (with short answers)
* **Why is the graph undirected?** Similarity is symmetric: if A resembles B, B resembles A. A directed graph would be right for "recommended next" data, which we do not have.
* **What does a high betweenness mean here?** The video lies on many cheapest paths between other videos, so it connects topic groups.
* **Is PageRank YouTube's ranking?** No. It is a graph algorithm applied to our similarity network.
* **Why do communities match topics so well?** Because the synthetic data was built from topic clusters. Real data would be messier.
* **Why does the graph split at high thresholds?** Fewer pairs pass the threshold, so weakly linked groups lose their connecting edges.
* **Can this use real YouTube data?** Yes, public metadata can be collected via the official YouTube Data API into the same CSV format. Private analytics (traffic sources, watch time) need the channel owner's authorisation.
* **How do you know the code is correct?** 84 automated tests, including a check that our own Dijkstra matches NetworkX.
