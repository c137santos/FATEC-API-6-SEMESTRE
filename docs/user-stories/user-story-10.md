# 📌 [10 - USER STORY] — LGPD Compliance: Consent and Incident Notification

> ✍️ **Author:** Paloma Soares  |  🗓️ **Edited:** May 05  |  🔖 **Version:** 1.0  |  ✅ **Status:** `Ready`

---

## 🎯 1. Overview

* **Objective:** Implement the three LGPD compliance pillars focused on consultants: explicit consent collection during registration (including policy versioning), a personal data self-management panel, and a data deletion process upon request.
* **Problem:** The platform collects personal data from registered consultants without formal consent, users have no visibility or control over their information, and there is no clear deletion process — exposing the platform to ANPD penalties and loss of user trust.

**KPI / Success Metrics:**

* ✅ 100% of new registrations stored with consent records in the database (timestamp + policy version)
* ✅ 0 incomplete deletion requests

---

## 🎨 2. Visual Behavior

> *Not applicable*

```text
Registration → "Privacy Policy" section (with lorem ipsum)
        ↓
Consent checkbox (NOT pre-checked)
        ↓
"Complete Registration" button enabled only after consent is accepted

Profile menu → "Privacy & My Data"
        ↓
View / Edit / Request Deletion
```

**Visual Behavior:**

* Consent checkbox **must not be pre-checked** (pre-selection is prohibited)
* "Complete Registration" button remains disabled until consent is accepted (consent is mandatory)
* When clicking the "Privacy Policy" link, the document must be organized into three sections: Registration Data, Active Purposes, Your Rights

---

## 📋 3. Narrative

**As** a registered consultant,
**I want** to have clarity and assurance that my personal information is protected
and will be used solely and exclusively for the operation of the platform,
**So that** I can feel confident that my privacy is being fully respected.

---

#### Happy Path

1. The consultant reaches the final registration step, reads the "Privacy Policy" section, and checks the consent box.
2. The "Complete Registration" button is enabled, and the consent is logged in the database with timestamp and policy version.
3. The consultant accesses the "Profile" section and views their registration data, consent date, and accepted policy version.
4. The consultant requests account deletion, and their data is removed from the database.

---

## 🛡️ 4. Business Rules

**Data Sources:**

* `users` table (consultant registration data)
* `consent_records` table (history of accepted consents)
* `audit_logs` table (access and data manipulation events — see [US-11](/docs/user-stories/user-story-11.md))


**Specific Rules / Data:**

* The consent checkbox must never be pre-checked.
* Consent must be stored with: `user_id`, `policy_version`, `accepted_at`.
* Deleted data upon account removal: name, email, password, session tokens.

---

## ✅ 5. Acceptance Criteria

#### Consent During Registration

| Step           | Action|
| -------------- | ------------------ |
| **Given that** | the consultant is on the final registration step|
| **When**       | they check the consent checkbox|
| **Then**       | the "Complete Registration" button is enabled, the registration is completed, and the consent is stored in the database with timestamp and policy version |

#### Registration Without Consent

| Step           | Action                                                                     |
| -------------- | -------------------------------------------------------------------------- |
| **Given that** | the consultant is on the final registration step                           |
| **When**       | they attempt to complete registration without checking the consent box     |
| **Then**       | the button must remain disabled and the registration must not be completed |

#### Access to the Profile Panel

| Step           | Action|
| -------------- | ----------------- |
| **Given that** | the consultant is authenticated on the platform|
| **When**       | they access the "Profile" section|
| **Then**       | they must be able to view their registration data, consent date and version, as well as edit and deletion options for their personal data |

#### Deletion Request

| Step           | Action|
| -------------- | ------------- |
| **Given that** | the consultant requests account deletion from the panel|
| **Then**       | upon completion, all personal data must be deleted from the database (logs are not deleted because they do not contain foreign keys) |

---

## 🏁 6. Definition of Done (DoD)

* [ ] Consent section implemented in the final registration step with a non-pre-checked checkbox
* [ ] Consent stored in the database with timestamp, policy version, and user ID
* [ ] "Privacy & My Data" panel accessible from the profile menu with all three sections implemented
* [ ] Complete deletion of user personal data (ensuring referential integrity)
* [ ] No personal data deleted without explicit consultant confirmation
