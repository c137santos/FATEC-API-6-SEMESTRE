# 📌 [07 - USER STORY] — Automatic PDF Report Generation

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 11  |  🔖 **Version:** 2.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **Objective:** Automatically generate a PDF report consolidating the SAM, PT/PNT, TAM, Criticality Index, and Heat Map charts as soon as the calculations are completed, eliminating any manual action from the consultant.
* **Problem:** Without automatic PDF generation, the consultant would need to manually access the system after processing, assemble the presentation material themselves, and risk using outdated or incomplete data.
* **Success:** The PDF is automatically generated, without visual formatting issues, immediately after the calculation process is completed, remaining available and ready for commercial use without any consultant intervention.

---

## 🎨 2. Visual Behavior

> *Not applicable*

### Visual Behavior

The PDF layout must be structured and professional, without overlapping axes or cropped text. The document must contain a header with the utility company name and generation date, conveying credibility during commercial presentations.

---

## 📋 3. Narrative

**As** a Tecsys sales consultant,
**I want** the system to automatically generate a PDF report consolidating the SAM, PT/PNT, TAM, Criticality Index, and Heat Map charts as soon as the calculations are completed,
**So that** I have the presentation material ready without any manual action and can focus entirely on the commercial approach with the utility engineer.

---

### Happy Path

1. MongoDB confirms that the processed utility company data has been successfully saved by the ETL pipeline.
2. The trigger is automatically activated in FastAPI — without any consultant interaction.
3. The calculation endpoint processes the Criticality Index, TAM, SAM, PT, and PNT metrics in the background.
4. The system internally validates the accuracy of the calculated results.
5. The PDF generation module is triggered, rendering the 5 charts in the defined sequence.
6. The generated PDF is stored and made available — ready to be sent to the consultant.

---

## 🛡️ 4. Business Rules

* **Data Sources:** Clean dataset recently stored in MongoDB.
* **Dependencies:** Directly depends on the successful completion of US-06 (Dynamic Ingestion and ETL). The generated PDF is the direct input for [US-09 (Email Sharing)](/docs/user-stories/user-story-09.md).
* **Performance:** To avoid server blocking, the trigger must run as an asynchronous task.
* **Chart Sequence in the PDF:** SAM → PT/PNT → TAM → Criticality Index → Heat Map.

---

## ✅ 5. Acceptance Criteria

### Automatic Post-ETL Trigger Execution

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the ETL pipeline confirmed data persistence in MongoDB|
| **When**       | the database transaction is completed|
| **Then**       | the system must automatically trigger the calculation processing endpoints in the background, without requiring any interaction from the consultant in the Front-end |

---

### Calculation Accuracy Guarantee

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the calculation endpoints (TAM, SAM, PT, PNT, and Criticality Index) were triggered|
| **When**       | the results are generated|
| **Then**       | the system must strictly apply the exact business rules (including meter-to-kilometer conversion in SAM), and the calculations must pass automated tests that ensure mathematical accuracy |

---

### Correct PDF Generation with the 5 Charts

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the calculations were processed successfully and accurately|
| **When**       | the report module is triggered|
| **Then**       | the system must generate a structured PDF file containing the SAM, PT/PNT, TAM, Criticality Index, and Heat Map charts, including a header identifying the utility company and the generation date, without layout breaks or cropped text |

---

### PDF Generation Failure

| Step           | Action|
| -------------- | ---------------- |
| **Given that** | the calculations were successfully completed|
| **When**       | an error occurs in the PDF generation module|
| **Then**       | the system must internally log the error with sufficient details for diagnostics, without impacting the consultant’s navigation within the platform |

---

## 🏁 6. Definition of Done (DoD)

* [ ] Trigger integrated with MongoDB persistence events
* [ ] Back-end unit tests created and passing, validating the mathematical accuracy of calculation functions
* [ ] Generated PDF contains the 5 charts in the correct sequence with an identification header
* [ ] Visual validation of the PDF completed using different datasets (different utility companies)
* [ ] Background processing time does not impact consultant navigation
* [ ] PDF generation failure scenarios correctly recorded in the logs
