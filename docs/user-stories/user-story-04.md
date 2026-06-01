# 📌 [04 - USER STORY] — Top 10 Ranking of Electrical Groups by TAM (Medium-Voltage Network Extension)

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 09  |  🔖 **Version:** 1.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

This feature maps the Total Addressable Market (TAM) of each electrical group by identifying the regions with the largest medium-voltage network extensions.

* **Objective:** Display a ranking of the 10 electrical groups with the highest TAM.
* **Problem:** Extremely large networks have a statistically higher probability of failures, make fault patrol and localization more difficult, and increase restoration time (DEC). The commercial team needs to quickly highlight these large-scale areas in order to focus sensor sales efforts on them.

---

## 🎨 2. Visual Behavior

### 🔗 Prototype Link (Figma)

🔗 **Prototype Link (Figma/Wireframe):** [Link](https://www.figma.com/design/3Y1slPQuLAhqTfVUck21P9/Jean?node-id=264-65&t=KXdBr8XbBWHOGycD-4)

---

## 📋 3. Narrative

**As** a Tecsys commercial/technical consultant,
**I want** to view a ranking highlighting the 10 electrical groups with the largest medium-voltage line extension (TAM),
**So that** I can demonstrate to the utility engineer that these large-scale networks represent the greatest operational vulnerability, showing that long extensions drastically increase the probability of failures, make fault patrol and localization more difficult, generate high technical losses, and increase system restoration time, thereby justifying the urgent and targeted deployment of our sensors precisely in these blind spots.

---

### Happy Path

1. The system consumes the dataset containing segments classified as Medium Voltage.
2. The system groups the data by electrical group.
3. The system sums the extension lengths of each group (TAM).
4. The system sorts the results in descending order.
5. The system selects the top 10 highest values.
6. The system displays a ranking with the electrical groups and their respective extensions.

---

## 🛡️ 4. Business Rules

* **Data Processing:** Group the data by electrical group, sum the medium-voltage extensions, sort in descending order, and provide a clean payload.
* **Voltage Filter:** Only medium-voltage extensions must be considered.
* **Unit Conversion:** If the original ANEEL/BDGD file provides segment lengths in meters (m), the script must convert the values by dividing by 1,000 to return the final data in kilometers (km).

---

## ✅ 5. Acceptance Criteria

### Total Extension Calculation (TAM)

| Step           | Action|
| -------------- | ---------------- |
| **Given that** | the system processes the utility company's geographic database                                                                           |
| **When**       | calculating the TAM of each electrical group                                                                                             |
| **Then**       | the system must sum the physical length of all line segments strictly classified as "Medium Voltage" within that electrical group region |

---

### Horizontal Bar Chart Rendering (Top 10)

| Step           | Action           |
| -------------- | -----------------|
| **Given that** | the TAM has been calculated and sorted in descending order for all groups|
| **When**       | the ranking visual component is loaded on the screen|
| **Then**       | the system must render a horizontal bar chart displaying exclusively the "Top 10"; Y-Axis (vertical): names of the Electrical Groups; X-Axis (horizontal): numerical scale representing size in kilometers (km) |

