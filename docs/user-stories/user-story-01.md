# 📌 [01 - USER STORY] — Criticality Index Calculation and Ranking Table

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 27  |  🔖 **Version:** 1.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **Objective:** Calculate the Criticality Score (percentage deviation of DEC and FEC) and display it in a ranked table.
* **Problem:** Without knowing the exact inefficiency calculation for each area, the sales team cannot effectively prioritize sales targets.

---

## 🎨 2. Visual Behavior

🔗 **Prototype Link (Figma/Wireframe):** [Link](https://www.figma.com/design/3Y1slPQuLAhqTfVUck21P9/Jean?node-id=264-30&t=Y9xyYzdNiFSWO2v1-4)

| Ranking | Electrical Group      | Actual / Target DEC | Actual / Target FEC | Criticality Score (%) |
| ------- | --------------------- | ------------------- | ------------------- | --------------------- |
| 1st     | Industrial District   | 18.5h / 12.0h       | 9.0 / 6.0           | +104.1% 🔴            |
| 2nd     | Historic Center       | 15.2h / 10.0h       | 7.5 / 7.0           | +59.1% 🔴             |
| 3rd     | University District   | 12.5h / 10.0h       | 5.5 / 5.0           | +35.0% 🔴             |
| 5th     | Vila Esperança        | 8.5h / 8.0h         | 4.1 / 4.0           | +8.7% 🟠              |
| 12th    | Southern Condominiums | 4.0h / 8.0h         | 2.0 / 5.0           | 0.0% 🟢               |

---

## 📋 3. Narrative

**As** a Tecsys commercial/technical consultant,
**I want** to view a ranking table calculating the Criticality Index of each electrical group,
**So that** I can quickly identify and prioritize the regions with the worst structural efficiency.

---

## 🛡️ 4. Business Rules

### Calculation

```python
Deviation_DEC = max(0, ((DEC_actual - DEC_limit) / DEC_limit) * 100)
Deviation_FEC = max(0, ((FEC_actual - FEC_limit) / FEC_limit) * 100)
Criticality_Score = Deviation_DEC + Deviation_FEC
```

### Criticality Level

| Color     | Range              | Description                            |
| --------- | ------------------ | -------------------------------------- |
| 🟢 Green  | = 0%               | Within or close to the target          |
| 🟠 Orange | Between 0% and 10% | Regions requiring attention            |
| 🔴 Red    | > 10%              | High criticality — primary sales focus |

### 📡 Data Source

[Collective Continuity Indicators (DEC and FEC) — ANEEL Portal](https://portalrelatorios.aneel.gov.br/indicadoresDistribuicao/indicadoresContinuidadeDECFEC)

---

## ✅ 5. Acceptance Criteria

| Step           | Action                                                          |
| -------------- | --------------------------------------------------------------- |
| **Given that** | the system imports regulatory data from ANEEL                   |
| **When**       | processing the criticality of an electrical group               |
| **Then**       | the system must strictly apply the percentage deviation formula |

| Step           | Action                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------- |
| **Given that** | the calculations were successfully completed                                                |
| **When**       | the table is displayed                                                                      |
| **Then**       | the system must render all groups sorted in descending order (from highest Score to lowest) |
