# 📌 [02 - USER STORY] — Sensoring Potential Index (SAM) Bar Chart

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 09  |  🔖 **Version:** 1.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **What is SAM?** A strategic indicator that combines network criticality (DEC/FEC), medium-voltage network extension, and existing protection infrastructure.
* **Objective:** Display a descending bar chart to guide the commercial team and utility engineers directly to the areas with the highest ROI.

---

## 🎨 2. Visual Behavior

The bar chart must display the electrical groups sorted in descending order based on the SAM index.

🔗 **Prototype Link (Figma/Wireframe):** [Link](https://www.figma.com/design/3Y1slPQuLAhqTfVUck21P9/Jean?node-id=264-45&t=nGn2Q3IHypqrq6CC-4)

---

## 📋 3. Narrative

**As** a member of the commercial/technical team,
**I want** to visualize a bar chart ordered by the electrical groups with the highest SAM index,
**So that** I can quickly identify which regions should be prioritized for sensor deployment (high criticality, large network extension, and few reclosers).

---

## 🛡️ 4. Business Rules

#### SAM Calculation

```text id="j5m1k9"
SAM = (MV_Network_Extension * Criticality) / Existing_Reclosers
```

#### Division by Zero Handling

Groups with 0 reclosers must receive special handling to avoid mathematical errors.

---

## ✅ 5. Acceptance Criteria

| Step           | Action                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------- |
| **Given that** | the system has processed the SAM index for all electrical groups                             |
| **When**       | the chart is rendered                                                                        |
| **Then**       | the system must display a vertical bar chart sorted from the highest SAM value to the lowest |
