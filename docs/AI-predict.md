# Continuity Indicator Forecasting AI (DEC and FEC)

This document describes the architecture, operation, and objectives of the Artificial Intelligence developed for the predictive analysis of quality indicators in the Brazilian electricity sector, focusing on ANEEL data.

## 1. Project Overview
The AI consists of a **continuous time-series** model designed to forecast the performance of electricity distributors. The main objective is to provide a decision support tool that anticipates the behavior of interruption indices.

The system operates with a forecast horizon of up to **1 year (12 months)**, enabling a medium-term strategic view.

### Indicator Definitions
* **DEC (Equivalent Interruption Duration per Consumer Unit):** Indicates the average time, in hours, that each consumer was without electricity during a specific period.
* **FEC (Equivalent Interruption Frequency per Consumer Unit):** Indicates the average number of interruptions experienced per consumer during the period.

## 2. Scope and Features
The application allows for granular analysis through filtering by utility company, treating each distributor as an isolated data context.

* **Custom Selection:** The user defines the target distributor (e.g., **ENEL RJ**, **EQUATORIAL**, **UNHEPAL**).
* **Data Processing:** The AI automatically filters ANEEL datasets, extracting the specific historical data for the selected company.
* **Calculation and Inference:** Based on the chosen distributor's historical series, the model projects DEC and FEC values for the subsequent months.

## 3. Technical Methodology

### Data Architecture

The model adopts a **hierarchical time-series** approach, allowing training across all distributors at once. Consequently, when generating graphs, it only needs to classify which distributor is currently being utilized.

### Data Collection and Filtering
Data is processed according to the following workflow:
1. **User Input:** Selection of the Distributor.
2. **Extraction:** Querying the database (e.g., MongoDB/CSV) for records linked to the distributor.
3. **Cleaning:** Handling missing values and normalizing the time series.

### Tools and Forecasting Algorithm
* **Prophet:** The model utilizes the Prophet library to identify seasonality (such as summer storms) and long-term trends in service quality.
* **Pickle:** Used for the serialization and persistence of trained models, enabling fast loading of forecasts without requiring a full reprocessing of the historical database for each query.

## 4. Output Structure
The AI generates results in two main formats:
* **Quantitative Projections:** Estimated numerical values for the next 12 months.
* **Visualization:** Graphs comparing actual historical data against the trendline projected by the AI.