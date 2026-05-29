# [03 - USER STORY] — Comparative Analysis of Technical Losses (TL) and Non-Technical Losses (NTL)

**Status:** Ready for implementation | **Version:** 1.0

---

## 🎯 1. Overview

This module focuses on clarifying the origin of energy losses within the utility company, separating theft/commercial errors from structural inefficiencies in the electrical grid.

**Objective:** Visualize, for each electrical group, the exact proportion between Technical Losses (TL) and Non-Technical Losses (NTL) in relation to the total injected energy.

**Problem:** The end customer (utility company) often underestimates Technical Losses. Without visibility into how much energy is being dissipated due to infrastructure inefficiencies (heating/failures), they do not perceive the urgency of acquiring telemetry sensors.

---

## 🎨 2. Visual Behavior

🔗 **Prototype Link (Figma/Wireframe):** [Link](https://www.figma.com/design/3Y1slPQuLAhqTfVUck21P9/Jean?node-id=264-45&t=Y9xyYzdNiFSWO2v1-4)

### Visual Behavior

* The **X-Axis** will represent the absolute loss volume in MWh.
* The **Y-Axis** will represent the Electrical Groups.
* The chart type will be a **Stacked Bar Chart**.

> **Important (UI Rule):** The total bar height must not be normalized to 100%. The total size of each bar must correspond to the absolute sum of losses (TL + NTL in MWh). The bar must be divided into two colors to highlight not only the proportion, but also the **magnitude** of the problem in each region.

---

## 📋 3. Narrative

**As** a member of the commercial/technical team,
**I want** to visualize a stacked bar chart comparing the absolute volume (in MWh) of Technical Losses (TL) and Non-Technical Losses (NTL) for each electrical group,
**So that** I can visually demonstrate to the utility engineer the magnitude of the network’s structural failures and technically justify the urgency of deploying our smart sensors.

---

### Happy Path

1. The system consumes data from the database in **Megawatt-hours (MWh)**.
2. The system separates the values into:

   * Technical Losses (TL)
   * Non-Technical Losses (NTL)
3. For each electrical group, the system calculates the total loss volume.
4. The system generates a stacked bar chart.
5. The user immediately visualizes the comparison between TL and NTL for each electrical group, where:

   * The **total bar size** represents the Total Loss Volume.
   * The **internal divisions** represent the separation between TL and NTL.

---

## 🛡️ 4. Business Rules

> **Back-end Attention:** The percentages displayed in the detail card must be calculated by dividing the loss volume by the **total injected energy** (not by the total losses).

### Calculation

```text id="k8d3rp"
TL %    = (Technical_Loss_MWh / Injected_Energy) × 100
NTL %   = (Non_Technical_Loss_MWh / Injected_Energy) × 100
Total Losses = TL + NTL
```

---

## ✅ 5. Acceptance Criteria

### Stacked Bar Chart Rendering

| Step| Action|
| -------------- | ------------------- |
| **Given that** | the system processed the data in Megawatt-hours (MWh)|
| **When**| the stacked bar chart is rendered|
| **Then**| the total size of each bar must represent the Total Loss Volume. The visual structure must include: Y-Axis (vertical) with the list of electrical groups; X-Axis (horizontal) with the absolute loss volume (in MWh); each bar representing the total losses of an electrical group; 1st segment for Technical Losses (TL); 2nd segment for Non-Technical Losses (NTL) stacked to the right |

---

### Exact Percentage Calculation

| Step| Action|
| -------------- | ----------------- |
| **Given that** | the back-end is processing the data in MWh (Megawatt-hours)|
| **When**| calculating the indicators for chart display|
| **Then**| the system must strictly apply the formula defined in the Business Rules: TL % = (Technical_Loss_MWh / Injected_Energy) × 100; NTL % = (Non_Technical_Loss_MWh / Injected_Energy) × 100; Total Losses = TL + NTL |

---

### Percentage Display

| Step           | Action  |
| -------------- | ---------------- |
| **Given that** | the user is viewing the chart |
| **When**       | the stacked bar chart is displayed |
| **Then** | the system must display, directly over each bar segment (TL and NTL), the percentage corresponding to each loss type. These percentages must be calculated based on the **total losses (TL + NTL)** of the electrical group, representing the participation of each type within the total. Example: Total Losses = 70 MWh (100%); Technical Losses (TL) = 30 MWh (42.86%); Non-Technical Losses (NTL) = 40 MWh (57.14%) |
