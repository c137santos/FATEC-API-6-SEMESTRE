# Personal Data Breach Incident Response Plan

**System:** Thunderstone  
**Legal basis:** Art. 48, Law nº 13.709/2018 (LGPD)  
**Responsible:** Marilia Moraes  
**Last reviewed:** 2026-05-28

---

## 1. Incident Identification

A security incident must be treated as a **personal data breach** whenever there is exposure, unauthorized access, loss, or improper alteration of any data in the `users` table (username, email, password hash, email_token) or active OAuth2 tokens.

### Detection sources

| Source | What to look for |
|---|---|
| Audit logs (MongoDB — `audit_logs` collection) | Events `security.unauthorized_access`, `security.token.invalid`, `security.rate_limit.hit` in abnormal volume or with unknown `user_id` |
| Direct user report | Email received reporting unrecognized access to an account |
| Infrastructure provider alert | Notification of unauthorized access to the server, database, or storage |

### Classification

This plan uses **a single severity level**: any incident involving personal data triggers the full plan.

---

## 2. Immediate Containment

Run the containment script **before any other action**. It revokes all OAuth2 tokens, invalidates pending authorization codes, and clears email tokens.

```bash
# Inside the container
docker-compose exec api python docs/security/scripts/contain.py
```

Then stop the API to prevent new access while the investigation takes place:

```bash
docker-compose stop api
```

> The script automatically records its execution in the MongoDB audit log with a timestamp and count of affected records.

---

## 3. Impact Assessment

Run the queries below directly on PostgreSQL to quantify the affected data subjects.

**Connect to the database:**
```bash
docker-compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

**Count users registered during the suspect period:**
```sql
SELECT COUNT(*) AS total_subjects,
       MIN(created_at) AS first_registration,
       MAX(created_at) AS last_registration
FROM users
WHERE created_at BETWEEN '<incident_start_date>' AND '<incident_end_date>';
```

**Check OAuth2 tokens that were active at the time of the incident:**
```sql
SELECT COUNT(*) AS active_tokens
FROM oauth2_tokens
WHERE issued_at >= EXTRACT(EPOCH FROM '<incident_start_date>'::timestamp)
  AND revoked = false;
```

**Fill in the impact record:**

| Field | Value |
|---|---|
| Detection date/time | |
| Estimated incident start date/time | |
| Detection source | |
| Exposed data (columns) | |
| Number of affected data subjects | |
| Compromised tokens | |
| External access confirmed (Y/N) | |

---

## 4. ANPD Notification

**Deadline:** 72 hours from the moment the incident is known.

**Channel:** gov.br/anpd portal — security incident communication form.

**Required information (Art. 48 §1 LGPD):**

| Field | Value |
|---|---|
| Controller identification | Thunderstone |
| CNPJ | [ORGANIZATION CNPJ] |
| Data Protection Officer (DPO) name | [DPO NAME] |
| DPO contact | [DPO EMAIL] |
| Incident date | |
| Date of awareness | |
| Nature of affected data | Username, email, password hash, authentication tokens |
| Number of affected data subjects | |
| Containment measures taken | Token revocation, API shutdown, temporary credential invalidation |
| Possible consequences | Unauthorized account access, credential misuse |
| Mitigation measures | Notifying data subjects to reset passwords, monitoring new access attempts |

---

## 5. User Notification

**Channel:** Email (via `send_email` — `backend/email/envio_email.py`)  
**Deadline:** Immediately after ANPD notification, or sooner if the risk is imminent.

**Template:**

```
Subject: Important security notice — Thunderstone

Hello,

We have identified a security incident that may have affected your account
on the Thunderstone system.

What happened:
[Briefly describe the incident without exposing sensitive technical details]

Data that may have been affected:
- Email address
- Username
- Password hash (your password was not exposed in plain text)

What we have already done:
- Revoked all active access tokens
- Shut down the service for investigation
- Notified the Brazilian Data Protection Authority (ANPD)

What you should do:
1. When the service is restored, reset your password immediately
2. If you use the same password on other services, change it there too
3. Be alert to suspicious emails sent to your address

If you have any questions, reply to this email.

Regards,
Thunderstone Team
```

---

## 6. Incident Record

Every incident must be documented in a dedicated file under `docs/security/incidents/` using the naming convention `YYYY-MM-DD-brief-description.md`.

**Required fields:**

```markdown
# Incident: [title]

- Detection date:
- Awareness date:
- Detection source:
- Exposed data:
- Number of affected data subjects:
- Action timeline (with timestamps):
  - HH:MM — [action taken]
- Containment script executed: Y/N
- ANPD notified: Y/N | Date:
- Users notified: Y/N | Date:
- Root cause identified:
- Corrective measures applied:
- Status: Open / Resolved
```

The containment script (`contain.py`) automatically records its execution in MongoDB (`audit_logs`). The event can be queried with:

```bash
docker-compose exec mongo mongosh $MONGO_DB --eval \
  "db.audit_logs.find({operation: 'security.incident.containment_executed'}).sort({timestamp: -1}).limit(5)"
```

---

## 7. Responsible Party

| Step | Responsible |
|---|---|
| Identification and classification | Marilia Moraes |
| Containment execution | Marilia Moraes |
| Impact assessment | Marilia Moraes |
| ANPD notification | Marilia Moraes |
| User notification | Marilia Moraes |
| Incident record and documentation | Marilia Moraes |

---

## References

- [Law nº 13.709/2018 — LGPD, Art. 48](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [ANPD Portal — Incident communication](https://www.gov.br/anpd)
- Containment script: `docs/security/scripts/contain.py`
- Audit log service: `backend/services/audit_log_service.py`
