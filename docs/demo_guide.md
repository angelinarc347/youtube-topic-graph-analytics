# Demonstration Guide (about 6-8 minutes)

**Before you start:** open the project in VS Code, activate `.venv`, run `python -m streamlit run app.py`, and open http://localhost:8501.
Run the app once beforehand so the first load is not slow. Have the README open in another tab in case of questions.

The numbers below are from the included **synthetic** dataset at the default threshold 0.25. They should match what you see.

## 0. Opening (30 seconds)
Say: *"This project models videos as a graph. Each video is a node; two videos are connected when they share tags and topics.
I used synthetic demo data, so there is no API key and nothing here is real YouTube data. I then use graph algorithms to find
important videos, groups, bridges and best paths, and compare them with performance metrics."*

## 1. Overview tab (45 seconds)
* Point at the KPI cards: **150 videos, 1,330 edges, 7 communities, about 14.7 million views, 4.68% average engagement**.
* Point at the blue **demo-data notice**: *"The dashboard always says when data is synthetic."*
* Open **How to use this dashboard** briefly.

## 2. Topic network tab (1.5 minutes)
* Colour by **Topic**: *"Seven clear clusters, one per topic. The few lines between clusters are cross-topic videos."*
* Switch to **Community** colouring: *"The algorithm found the same seven groups without being told the topics."*
* Change **Dot size shows** to **Betweenness**: *"The big dots sitting between clusters are bridge videos."*
* Move the **Minimum similarity** slider in the sidebar to about 0.27, then to 0.6: *"As the threshold rises the graph splits into islands. At 0.6 there are only 90 edges and the app warns that the graph is disconnected."* Put it back to 0.25 (or press **Reset filters**).
* Open **How are edges decided?** and read the formula: Jaccard on tags + 0.15 same-topic bonus; weight = similarity; distance = 1 / similarity.

## 3. Centrality & communities tab (2 minutes)
**Centrality & PageRank sub-tab**
* Open **What do these measures mean?** and explain degree, closeness, betweenness, eigenvector, PageRank in one sentence each.
* Rank by **Betweenness**: *"The top videos - 'Using AI as a study partner', 'Make a small game with Python in one weekend', 'Wearable gadgets...' - are exactly the cross-topic videos I designed as bridges."*
* Rank by **PageRank** and say: *"PageRank here is a graph measure on my similarity network, not YouTube's recommendation algorithm."*

**Communities & bridges sub-tab**
* Show **modularity 0.84** (above about 0.3 means clear structure) and the table with **topic purity 100%**.
* Be honest: *"The purity is perfect because I built the synthetic topics to cluster. Real data would be messier."*
* Show the **bridge videos** table (31 videos link to another community).

**Partitioning & clustering sub-tab**
* Kernighan-Lin: *"Splits into two halves of 75 videos and cuts only 101 of 1,330 edges (7.6%)."*
* Dendrogram: *"This is true hierarchical clustering - a different method from communities. I can cut the tree into any number of clusters."*

**Network properties sub-tab**
* *"Small-world and scale-free are concepts. The app only computes indicators: clustering is high (0.86 vs 0.12 for a random graph) but paths are not shorter than random, so I do not claim small-world. Degrees are fairly even (max/mean 1.24), so I do not claim scale-free."*

## 4. Shortest path tab (1.5 minutes)
* From: **Street food tour: eating our way through a night market** To: **Make a small game with Python in one weekend**.
* Expected: **6 steps, total cost about 19.38**, passing through cooking, baking-science, exam-prep and AI-study videos.
* Say: *"Dijkstra uses distance = 1 / similarity, so the cheapest path follows chains of very similar videos. The red line shows the route on the map and the table shows which tags link each step."*
* Open **Check: the step-by-step Dijkstra gives the same cost**: *"I also wrote Dijkstra by hand with a priority queue and checked it against NetworkX."*
* Optional: select the same video twice, or filter to two topics and raise the threshold, to show the friendly "no path" message.

## 5. Video performance tab (1 minute)
* Rank top videos by **Views**, then by **Engagement rate (%)**: *"The most viewed video is not the most engaging."*
* Topic comparison: *"Entertainment and Gaming have the most views but the lowest engagement (3.7% and 3.5%); Education has the highest engagement (6.3%) with fewer views."*
* Scatter: tick/untick **log scale** and explain outliers. Show the correlation heat-map and read the warning that correlation is not causation.
* Open **Simulated traffic sources**: *"These percentages are simulated for practice. Real traffic-source data needs YouTube Analytics access authorised by the channel owner."*

## 6. Data & methodology tab (30 seconds)
* Show rows read vs kept, the required columns, formulas, and the **Syllabus concepts and data limitations** table.
* Show the download buttons (filtered data with metrics, graph metrics).

## 7. Closing (30 seconds)
*"The project implements Dijkstra, the five centrality measures, PageRank, community detection, partitioning and hierarchical clustering
on a similarity graph, connects them to video performance, has 84 automated tests, and the code is in my GitHub repository (show the link once you have published it). Limitations: synthetic data, tag-only
similarity, and no private YouTube analytics. Future work: optional YouTube Data API loading and text-based similarity."*

## Possible follow-up questions
See section 5 of [code_walkthrough.md](code_walkthrough.md) for short answers.

## Safety checklist before presenting
* [ ] Dashboard starts and shows the demo-data notice.
* [ ] You pressed **Reset filters** so the numbers match this guide.
* [ ] No real API keys, passwords or private data are in the project folder.
* [ ] You can explain: the similarity formula, why distance is 1/similarity, what betweenness means, and that the data is synthetic.
* [ ] You have not described any chart as "real YouTube data".
