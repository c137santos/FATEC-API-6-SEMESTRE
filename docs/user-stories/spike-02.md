# 📌 [02 - SPIKE] — Automatic Distributor Loading and ANEEL Pipeline Orchestration

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Apr. 11  |  🔖 **Version:** 3.0  |  ⏳ **Status:** `Ready`
>
> **Type:** Technical Spike  |  **Timebox:** Maximum 1 Sprint  |  **Linked to:** [US-06 — Filter Panel and Distributor Analysis Generation](/docs/user-stories/user-story-06.md)

---

## 🎯 1. Objective

Design and validate the infrastructure that connects the consultant’s selection to the data pipeline, eliminating any manual steps from the workflow. This Spike delivers three chained responsibilities:

1. **Automatic distributor loading** — on application startup, fetch and persist the metadata (ID and Name) of all available distributors from ANEEL into PostgreSQL, automatically populating the selection menu for US-06.
2. **Listing endpoint** — expose the distributors stored in PostgreSQL to the front-end through `GET /distributors`.
3. **Pipeline orchestration** — based on the consultant’s selection (distributor + year range), dynamically build the ANEEL URL and trigger the SPIKE-01 pipeline.

### Technical Narrative (Developer Story)

```text id="y0mt48"
As an engineering team,
We need to design and validate the data loading infrastructure during application startup
(FastAPI + PostgreSQL) and the asynchronous pipeline orchestration (MongoDB),
So that the filter selection interface (US-06) can be populated in a fully
automated way, without manual bottlenecks or request blocking.
```

---

## ❓ 2. Problem / Technical Uncertainty

* What is the best approach in FastAPI to ensure distributor fetching and persistence into PostgreSQL happens only once during application startup?
* How can we guarantee that the PostgreSQL distributor table is properly updated (upsert) without duplicating records after each restart?
* How can we ensure SPIKE-01 is triggered asynchronously without blocking the response sent to the front-end?
* In case of pipeline trigger failure, can the system abort the flow and return a controlled error before processing begins?

---

## 🗺️ 3. Pipeline Scope (Architecture)

### Phase 1: Application Startup (FastAPI)

```text id="z7k8d1"
[Application Startup]
  ↓ [1. FastAPI sends a GET request to the ANEEL API to fetch distributor Names and IDs]
  ↓ [2. System saves/updates (Upsert) this data into the PostgreSQL database]
```

### Phase 2: User Flow and Orchestration (US-06)

```text id="c3w9p2"
[Consultant accesses the filter screen]
  ↓ [1. Front-end calls the GET /distributors endpoint from FastAPI (Reads from PostgreSQL)]
  ↓ [2. Consultant selects the distributor and year range, then clicks "Generate Analysis"]
  ↓ [3. Front-end sends the distributor ID + years to FastAPI]
  ↓ [4. Back-end triggers the SPIKE-01 pipeline, passing the ID and year range]
     → SPIKE-01 handles: streaming download → ETL → persistence into MongoDB
  ↓ [5. MongoDB confirmation triggers the Calculation Trigger (US-08)]
```

### 📡 3.1 Distributor Search Endpoint in ANEEL (Startup)

```text id="m6s4n8"
GET https://www.arcgis.com/sharing/rest/search?q=BDGD%20AND%20(distribuidora%20OR%20distribuicao)&type=Feature%20Service&orgid=<ORG_ID_ANEEL>&maxItems=100&f=json
```

**Fields to be used:**

| Field            | Key     | Description                        | Example                           |
| ---------------- | ------- | ---------------------------------- | --------------------------------- |
| Distributor ID   | `id`    | Unique ArcGIS item identifier      | `"id": "abc123xyz"`               |
| Distributor Name | `title` | Dataset name (requires processing) | `"title": "BDGD - CPFL Paulista"` |

**What should be stored in PostgreSQL after processing:**

```json
{ "id": "abc123xyz", "name": "CPFL Paulista" }
```

---

## ✅ 4. Spike Completion Criteria

* [ ] **Startup Synchronization:** FastAPI startup routine implemented, consuming the ANEEL endpoint, processing the `title`, and storing `id + name` into PostgreSQL via upsert.
* [ ] **Listing Endpoint:** `GET /distributors` endpoint created, tested, and returning data read from PostgreSQL.
* [ ] **Dynamic Orchestration:** Logic implemented to receive the distributor `id` from the front-end and correctly trigger the SPIKE-01 pipeline.
* [ ] **SPIKE-01 Integration:** Flow tested to confirm the trigger correctly forwards parameters and that SPIKE-01 receives the data and completes the flow up to MongoDB.
* [ ] **Exception Handling:** Failure behavior tested. The system must abort the flow and return an appropriate HTTP error without breaking the application.

---

## 🛡️ 5. Rules and Technical Constraints

### Databases Involved

* **PostgreSQL:** Used exclusively to store static metadata (distributor ID and name).
* **MongoDB:** Remains the final destination for post-ETL data — responsibility of SPIKE-01.

### Responsibility of this Spike

Acts as the orchestrator — fetches metadata, populates PostgreSQL, exposes the listing endpoint, and triggers SPIKE-01. Downloading, ETL processing, and persistence of raw data are exclusively handled by SPIKE-01.

### Startup Performance

The initialization routine must not excessively impact the API boot time.

---

## 🔗 6. Dependencies

* [SPIKE-01 — Asynchronous Processing of `.gdb.zip` Files](/docs/user-stories/spike-01.md) must be implemented and accessible.
* Requires `ORG_ID_ANEEL` configured as an environment variable.
* Requires PostgreSQL database credentials/configuration.
