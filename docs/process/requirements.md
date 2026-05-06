# Functional Requirements


## RF1 - Data Import and Structuring
**Base ID:** RF1-DATA


### RF1-DATA-INGEST - Regulatory Data Ingestion
- The system must consume CSV files and compressed Geodatabases (ZIP) from ANEEL (BDGD, DEC, FEC, and Losses).
- The system must process the file data, performing cleaning and validation of the mandatory columns required for the calculations.
- The system must store the processed data in MongoDB.


---


## RF2 - Market and Criticality Analysis
**Base ID:** RF2-ANALYTICS


### RF2-ANALYTICS-TAM - Physical Sizing (TAM)
- The system must calculate the length of Medium Voltage lines to identify the market potential for Tecsys sensors.


### RF2-ANALYTICS-PERD - Comparative Loss Analysis
- The system must rank the electrical sets by cross-referencing DEC, FEC, and regulatory limits.
- The system must visually compare (in MWh) technical and non-technical losses.


### RF2-ANALYTICS-SAM - Sensing Potential Index (SAM)
- The system must cross-reference network length, criticality, and recloser presence data to qualify and rank the regions with the highest priority potential for sensor installation.


### RF2-ANALYTICS-CRIT - Criticality and Loss Calculation and Visualization
- The system must calculate and rank the electrical sets by cross-referencing DEC, FEC, and ANEEL regulatory limits.
- The system must display a classification table (or chart) listing the electrical sets ordered from the most critical (worst efficiency) to the least critical.


---


## RF3 - Predictive Engine and Artificial Intelligence
**Base ID:** RF3-PREDICT


### RF3-PREDICT-API - Advisory API (Machine Learning)
- The system must have a dedicated API for executing the predictive model.


---


## RF4 - Georeferenced Visualization (GIS)
**Base ID:** RF4-MAPS


### RF4-MAPS-HEATMAP - Heatmaps and Polygons
- The system must render a georeferenced map, coloring the network segments based on the Criticality Index.


---


## RF5 - User Management and Authentication
**Base ID:** RF5-AUTH


### RF5-AUTH-CRUD - Account Creation and Login
- The system must allow users to create their own accounts autonomously.
- The system must authenticate users via email and encrypted password.
- The system must allow editing of basic data and account deletion.
- *Architecture Note:* All user and credential data must be stored in the relational (legacy) database, composing the structured part of the hybrid architecture.


---


# Non-Functional Requirements


## RNF1 - Mandatory Project Documentation
**Base ID:** RNF1-DOCS


### RNF1-DOCS-USER - Installation Manuals
- The team must produce a System Installation Manual.
- The team must produce a User Manual detailing how to use the features.


### RNF1-DOCS-TECH - Technical Documentation
- The team must provide API (Application Programming Interface) documentation containing the endpoints.


---


## RNF2 - Database Architecture
**Base ID:** RNF2-DATA


### RNF2-DATA-BASE - Database Modeling
- The team must deliver the database modeling or the data file structure.


### RNF2-DATA-TESTS - Data Integrity
- The system must include basic automated tests to validate database integrity.


---


## RNF3 - LGPD Compliance and Security
**Base ID:** RNF3-SEC


### RNF3-SEC-LGPD - Privacy and Anonymization
- The system must add LGPD compliance rules.
- The system must implement personal data anonymization routines in case of account deletion, as required by LGPD.


### RNF3-SEC-AUDIT - Traceability (Logs)
- The system must perform mandatory logging of access events.
- The system must record detailed data manipulation logs in an audit table.


---


## RF6 - Reports and Data Export
**Base ID:** RF6-EXPORT


### RF6-EXPORT-PDF - Commercial Proposal Generation in PDF
- The system must allow exporting the analyses generated (dashboards) to a PDF document.
- The generated PDF must consolidate the information in a structured way, serving as a ready-to-deliver technical/commercial report for the utility company.
