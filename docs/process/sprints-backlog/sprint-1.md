# Sprint 1 Backlog


| Rank | Priority | User Story | Related Requirements | Estimate (Story Points) | Sprint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Spike | High | As a geospatial data ingestion system, I want to process .gdb.zip files asynchronously and efficiently, so that I can provide cleaned and georeferenced data in the database for analysis and visualization. | [`RF1-DATA-INGEST`](../requirements.md#rf1-data-ingest---regulatory-data-ingestion), [`RF2-ANALYTICS-CRIT`](../requirements.md#rf2-analytics-crit---criticality-and-loss-calculation-and-visualization) | 10 | 1 |
| 1 | High | As a Tecsys sales/technical consultant, I want to view a ranking table that calculates the Criticality Index (percentage deviation of DEC and FEC based on ANEEL limits) for each electrical set, so that I can quickly identify and prioritize which regions have the worst structural efficiency. | [`RF1-DATA-INGEST`](../requirements.md#rf1-data-ingest---regulatory-data-ingestion), [`RF2-ANALYTICS-CRIT`](../requirements.md#rf2-analytics-crit---criticality-and-loss-calculation-and-visualization) | 18 | 1 | 
| 2 | High | As a member of the sales/technical team, I want to view a bar chart ordered by the electrical sets with the highest SAM score, so that I can quickly know which regions have the highest priority for sensor deployment. | [`RF2-ANALYTICS-SAM`](../requirements.md#rf2-analytics-sam---sensing-potential-index-sam) | 10 | 1 |  
| 3 | High | As a member of the sales/technical team, I want to view a stacked bar chart comparing the absolute volume (in MWh) of Technical Losses (PT) and Non-Technical Losses (PNT) for each electrical set, in order to show the magnitude of the grid's structural failures. | [`RF2-ANALYTICS-PERD`](../requirements.md#rf2-analytics-perd---comparative-loss-analysis) | 10 | 1 |
| 4 | High | As a Tecsys sales/technical consultant, I want to view a ranking with the 10 electrical sets with the greatest medium-voltage extension (TAM), to demonstrate the points with the highest operational vulnerability. | [`RF1-DATA-INGEST`](../requirements.md#rf1-data-ingest---regulatory-data-ingestion), [`RF2-ANALYTICS-TAM`](../requirements.md#rf2-analytics-tam---physical-sizing-tam) | 12 | 1 | 
| 5 | Medium | As a Tecsys sales/technical consultant, I want to view a georeferenced heatmap indicating the most critical circuits based on the Criticality Index, in order to justify investments in smart sensors. | [`RF4-MAPS-HEATMAP`](../requirements.md#rf4-maps-heatmap---heatmaps-and-polygons) | 8 | 2 | 


## Sprint Goals


| **Estimated Team Capacity per Sprint:** | 58 Story Points |
|-----------------------------------------|-----------------|
| **Sprint Goal:**                        | User Stories rank 1, rank 2, rank 3, rank 4 (total of *50 Story Points*) |
| **Sprint Forecast (extras, no delivery commitment):** | User Story rank 5 (*8 Story Points*) |


---
#### [SPIKE] — Asynchronous processing of .gdb.zip files <a id="spike"></a>

>📄 **Full Documentation:** [Spike-01](/docs/user-stories/spike-01.md)

---
#### [01 - USER STORY] — Criticality Index Calculation and Ranking Table <a id="us1"></a>

>📄 **Full Documentation:** [User Story 01](/docs/user-stories/user-story-01.md)

---


#### [02 - USER STORY] — Bar Chart of Sensing Potential Index (SAM) <a id="us2"></a>

>📄 **Full Documentation:** [User Story 02](/docs/user-stories/user-story-02.md)

---


#### [03 - USER STORY] — Comparative Analysis of Technical Losses (PT) and Non-Technical Losses (PNT) <a id="us3"></a>

>📄 **Full Documentation:** [User Story 03](/docs/user-stories/user-story-03.md)

---


#### [04 - USER STORY] — Top 10 Sets Ranking by TAM (Medium-Voltage Extension) <a id="us4"></a>

>📄 **Full Documentation:** [User Story 04](/docs/user-stories/user-story-04.md)

---


#### [05 - USER STORY] — Utility Criticality Index Heatmap <a id="us5"></a>

>📄 **Full Documentation:** [User Story 05](/docs/user-stories/user-story-05.md)

---