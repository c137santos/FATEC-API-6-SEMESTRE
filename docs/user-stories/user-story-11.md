# 📌 [11 - USER STORY] — Access and Data Manipulation Logs

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** Recently  |  🔖 **Version:** 1.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **Objective:** Implement an immutable and auditable logging structure capable of recording all relevant access and personal data manipulation events within the platform, without storing personal data inside the logs themselves, ensuring traceability and LGPD compliance before the ANPD, including export and email delivery functionality.
* **Problem:** The platform currently lacks a structured record of who accessed or manipulated data, when it happened, and with what outcome — making it impossible to investigate incidents, respond to ANPD audits, or demonstrate compliance in the event of legal inquiries.

**KPI / Success Metrics:**

* ✅ 100% of cataloged events properly logged in their corresponding flows
* ✅ 0 personal data stored within log payloads

---

## 🎨 2. Visual Behavior

> *Not applicable — backend-only User Story. Logs are internal infrastructure; administrator visualization is covered by a separate User Story.*

---

## 📋 3. Narrative

**As** a system administrator,
**I want** to have a clear and tamper-proof history of who accessed, generated, or modified
strategic information within the platform,
**So that** I can fully understand what happened in cases of errors, audits, or suspicious behavior, ensuring the protection of our business.

---

#### Happy Path

1. A user performs an action listed in the logging catalog → event is recorded.
2. A consultant accepts consent during registration → `consent.accepted` event is recorded with `policy_version` in the metadata.
3. A consultant requests account deletion → `account.deletion.requested` and `account.deletion.confirmed` events are logged sequentially.
4. A consultant requests audit logs → a CSV file is generated → the file is sent to the registered email address.

---

## 🛡️ 4. Business Rules

### Data / Specific Rules

| Rule                              | Description|
| --------------------------------- | ------------------------------------ |
| **BR01 — Absolute Immutability**  | The MongoDB log collection must be strictly append-only. No UPDATE or DELETE operations are allowed.|
| **BR02 — Zero-PII Policy**        | Persisting personal data inside log payloads (such as within the `ValuesChanges` field) is strictly prohibited. Only identification keys (IDs), structural metadata, and change flags are allowed. |
| **BR03 — Identity Decoupling**    | `UserId` must be stored in a denormalized manner and typed as `String` to ensure traceability even after account deletion.|
| **BR04 — Mandatory Structure**    | Every insertion must contain: `EntityName`, `Operation`, `UserId`, `Timestamp (UTC)`, `ValuesChanges`.|
| **BR05 — Action Standardization** | The `Operation` field must follow a strict Enum/event catalog defined by the system.                                                                                                               |

### Event Catalog

| Category                 | Events|
| ------------------------ | --------------------------- |
| Authentication           | `auth.login.success`, `auth.login.failure`, `auth.login.blocked`, `auth.logout`, `auth.password.reset_requested` |
| Registration and Account | `account.created`, `account.updated`, `account.deletion`|
| Consent                  | `consent.accepted`, `consent.revoked`|
| Security                 | `security.unauthorized_access`, `security.token.invalid`, `security.rate_limit.hit`|
| Report                   | `report.requested`, `report.generated`, `report.failed`|
| Logs                     | `report.audit_logs.exported`                                                                                     |

### Examples of `ValuesChanges`

**For Reports:**
`{ "period": "2026-01", "department": "sales", "format": "csv" }`

**For Data Changes:**
`{ "fields_updated": ["password", "address", "phone_number"] }`

**For Consent Auditing:**
`{ "policy_version": "2.1", "acceptance_method": "click-wrap", "ip_address_mask": "192.168.x.x" }`

---

## ✅ 5. Acceptance Criteria

#### Entity Mapping

| Step           | Action|
| -------------- | ------------------- |
| **Given that** | a change is made to any system entity|
| **When**       | an Added, Updated, or Deleted command is executed|
| **Then**       | the log must mandatorily store: `EntityName` (table/class name), `Operation` (performed action), `UserId` (ID of the user who performed the action as a string) |

#### Immutability and LGPD Compliance

| Step           | Action|
| -------------- | -----------------|
| **Given that** | a log entry has been inserted|
| **Then**       | no UPDATE or DELETE operation must be allowed in this collection; in the event of user deletion, the `UserId` field must remain preserved for audit history purposes (stored as string) |

#### Log Visualization

> Stored in MongoDB + log visualization document.

---

## 🏁 6. Definition of Done (DoD)

* [ ] Log persistence structure implemented in the backend and correctly storing data in the MongoDB collection
* [ ] Schema validation ensures all mandatory fields are properly filled
* [ ] Zero-PII rule validated in code (filtering emails, CPF numbers, and real names before saving)
* [ ] Asynchronous CSV generation and email delivery routine for administrators completed
* [ ] MongoDB and application configured to block any UPDATE or DELETE attempts on the log collection
