# Notebooks and Proof of Concept (PoC)

This directory contains the Jupyter Notebooks (often run on Google Colab) that served as a **Proof of Concept (PoC)** for the project. 

## Purpose

The main objective of these notebooks was to interactively explore, prototype, and validate the mathematical formulas, energetic indicator calculations, and data processing logic before implementing them as production-ready code in the official **backend**. 

Because these scripts act as a PoC, they feature an exploratory and experimental structure.

## Notebooks Overview

Below is a summary of what each notebook validates regarding the business rules:

* **`_PT_e_PNT_Per_Set.ipynb` / `PT_And_PNT_Per_Set_Without_Graph.ipynb`**: Prototyping the calculation for *Technical Losses (PT)* and *Non-Technical Losses (PNT)* grouped by electrical sets, providing versions with and without visual graphs.
* **`SAM_Calculation.ipynb`**: Script used for experimenting and validating the SAM indicator calculation logic.
* **`TAM_Calculation.ipynb`**: Validation of formulas and operations needed to calculate the *Market Adequacy Rate (TAM)*.
* **`DEC.ipynb`**: Processing and prototyping metrics related to energy continuity indicators (like Equivalent Duration of Interruption per Consumer Unit - DEC).
* **`Mapa_de_Criticidade.ipynb`**: Exploratory analyses to generate maps visualizing the criticality levels of the subsets evaluated.
* **`Heatmap.ipynb`**: Data modeling and mathematical approaches to establish a "score" assessing distribution companies and electrical sets concerning anomalies and infrastructure events.

## How to Run

These files are standard `.ipynb` (IPython Notebook) files and can be opened through:
1. Uploading to [Google Colab](https://colab.research.google.com/).
2. Opening them locally in **VS Code** (the *Jupyter* extension is required).
3. Using an interactive **Jupyter Notebook** or **Jupyter Lab** local environment.

---

> **Important Notice:** As a Proof of Concept environment, the definitive, optimized, and version-controlled codebase (which includes ETL pipelines, scheduled Celery tasks, and API endpoints) is centralized in the `backend/` directory.