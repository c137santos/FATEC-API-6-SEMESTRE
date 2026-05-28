# 📌 [06 - USER STORY] — Filter Panel and Analysis Generation by Utility Company

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 12  |  🔖 **Version:** 3.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **Objective:** Serve as the platform’s central screen — the first thing the consultant sees after logging in — where they select the utility company and the year range to analyze, confirm the generation, and wait while the system performs all processing tasks in the background.
* **Problem:** Before the platform, consultants had to manually download ANEEL data, run scripts in notebooks, process calculations, and create charts on their own — a fragmented, time-consuming process that depended heavily on technical expertise.
* **Success:** The consultant selects the utility company and year range, clicks confirm, and waits on the screen while the system automatically processes everything. Once completed, the results are ready and the report is generated — with no manual steps or technical knowledge required.

---

## 🎨 2. Visual Behavior

🔗 **Prototype Link (Figma/Wireframe):** [Link](https://www.figma.com/design/3Y1slPQuLAhqTfVUck21P9/Jean?node-id=119-2&t=KXdBr8XbBWHOGycD-4)

```text id="r2k8x1"
After login → Filter Panel
         ↓
Select utility company (list from SPIKE-02)
         ↓
Define the year range
         ↓
Click "Generate Analysis"
         ↓
Loading state with progress messages by stage
         ↓
Upon completion: confirmation message sent to the registered email
```

### Visual Behavior

The technical complexity of the process remains completely hidden. The consultant does not see URLs, pipelines, or processing details. The loading screen must convey progress and reassurance through user-friendly messages:

* *"Fetching data from ANEEL..."*
* *"Processing utility company information..."*
* *"Calculating criticality indexes..."*
* *"Generating your report..."*

---

## 📋 3. Narrative

**As** a Tecsys commercial consultant,
**I want** to automatically generate the complete analysis for a selected utility company,
**So that** I can prepare and conduct commercial presentations autonomously, without needing to understand or interact with any technical step of the process.

---

### Happy Path

1. The consultant logs in and accesses the Filter Panel.
2. Selects the utility company from the dropdown menu (automatically loaded by SPIKE-02).
3. Defines the desired year range (e.g., 2023–2025).
4. Clicks on "Generate Analysis".
5. The screen enters a loading state displaying progress messages for each stage.
6. The system automatically processes everything in the background (technical details documented in SPIKE-01).

---

## 🛡️ 4. Business Rules

* **Data Sources:** The utility companies available in the dropdown menu are automatically loaded into the database by [SPIKE-02](/docs/user-stories/spike-02.md).
* **Invisible Processing:** The entire technical pipeline runs in the background, with no consultant interaction required after clicking "Generate Analysis".

### Dependencies

* The technical pipeline is documented in [SPIKE-01](/docs/user-stories/spike-01.md) to ensure the dropdown list is populated.
* The generated results directly feed into [US-07 (Automatic PDF Report Generation)](/docs/user-stories/user-story-07.md).

### Specific Rules

* The "Generate Analysis" button must remain disabled until both the utility company and the year range are selected.
* In case of processing failure, no partial data must be displayed to the consultant.

---

## ✅ 5. Acceptance Criteria

### Filter Selection and Confirmation

| Step           | Action|
| -------------- | ---------------- |
| **Given that** | the consultant is on the Filter Panel after login|
| **When**       | they select a valid utility company and year range and click on "Generate Analysis"|
| **Then**       | the system must start the background processing and immediately display the loading state on the screen |

---

### Visual Feedback by Stage

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the consultant confirmed the analysis generation|
| **When**       | the system is processing the data|
| **Then**       | the screen must display progress messages in user-friendly language, updated as each pipeline stage is completed (minimum of 3 visible stages), without freezing the interface or exposing any technical details |

---

### Redirection Upon Completion

| Step           | Action|
| -------------- | ------------------ |
| **Given that** | the processing has been successfully completed|
| **When**       | all data is ready|
| **Then**       | the consultant must be automatically redirected to the results screen containing the charts and generated report — with no additional action required |

---

### Processing Failure

| Step           | Action|
| -------------- | ---------------- |
| **Given that** | the consultant confirmed the analysis generation|
| **When**       | a failure occurs at any stage of the processing                                                                               |
| **Then**       | the system must stop the loading state and display: *"Unable to generate the analysis. Please try again or contact support."* |

---

### Available Utility Company List

| Step           | Action|
| -------------- | -----------------|
| **Given that** | the consultant is viewing the utility company selection menu|
| **When**       | they open the selection field|
| **Then**       | they must see only the utility companies automatically loaded by SPIKE-02, with no invalid or empty options |

---

## 🏁 6. Definition of Done (DoD)

* [ ] Filter Panel screen implemented with utility company dropdown and year range selector
* [ ] Utility company list automatically populated via SPIKE-02 (no manual insertion)
* [ ] "Generate Analysis" button disabled until filters are fully selected
* [ ] Loading screen displays progressive stage messages (minimum of 3 visible stages)
* [ ] User-friendly error message displayed in case of failure, without exposing technical details
* [ ] SPIKE-01 completed and pipeline validated with at least two real utility companies
