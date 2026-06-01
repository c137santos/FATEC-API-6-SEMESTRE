# Database Mapping

## PostgreSQL (Relational)

Database used for authentication, access control and consents.

### Tables

| Table | Description | Main Fields |
|--------|-----------|-------------------|
| `users` | System users | id, username, email, password, created_at, is_verified, email_token, consented_at, consent_policy_id |
| `consent_policies` | Consent policies | id, version, content, is_mandatory, created_at |
| `user_consents` | User consents | id, user_id (FK), consent_policy_id (FK), accepted, consented_at |
| `distribuidoras` | Energy distributors | id (PK), date_gdb (PK), dist_name, job_id, processed_at, updated_at |
| `distribuidora_cnpj` | Distributor CNPJ | dist_id (PK), cnpj, cnpj_match, cnpj_source, cnpj_enrichment_status, updated_at |

---

## MongoDB (NoSQL)

Database used to store analysis data, calculations and results.

### Collections

| Collection | Description | Main Documents |
|---------|-----------|----------------------|
| `audit_logs` | System audit logs | operation, user_id, timestamp, entity_type, entity_id, details, status |
| `jobs` | Job/processing management | job_id, status, dist_id, date_gdb, created_at, updated_at, render_paths |
| `circuitos_mt` | Medium Voltage Circuits (CTMT) | job_id, records (array), created_at, updated_at |
| `conjuntos` | Sets of distributors | job_id, dist_id, date_gdb, circuit_count, created_at |
| `segmentos_mt_tabular` | MT segments in tabular format | job_id, dist_id, segment_data, created_at |
| `segmentos_mt_geo` | MT segments with geographic data | job_id, dist_id, geometry, segment_data, created_at |
| `unsemt` | UNS (Business Unit) data | job_id, dist_id, uns_data, created_at |
| `dec_fec_realizado` | Realized DEC/FEC indices | num_cnpj, ide_conj, sig_indicador, ano_indice, num_periodo, vlr_indice, dat_geracao |
| `dec_fec_limite` | DEC/FEC limits | num_cnpj, ide_conj, sig_indicador, ano_limite, vlr_limite, dat_geracao |
| `score_criticidade` | Calculated criticality scores | job_id, dist_id, score_data, created_at, updated_at |
| `mapa_criticidade` | Generated criticality maps | job_id, dist_id, map_data, geometry, created_at |
| `TAM` | Average Service Time | job_id, dist_id, tam_value, period, created_at |
| `sam_resultados` | SAM analysis results | job_id, dist_id, sam_data, metrics, created_at |
| `pt_pnt_resultados` | PT and PNT results | job_id, dist_id, pt_data, pnt_data, created_at |

---

## Relationships

### PostgreSQL
- **users** ← FK `consent_policy_id` → **consent_policies**
- **user_consents** ← FK `user_id` → **users**
- **user_consents** ← FK `consent_policy_id` → **consent_policies**
- **distribuidora_cnpj** ← PK `dist_id` references **distribuidoras**

### MongoDB
- All collections use `job_id` as a correlation key for processing tracking
- `dist_id` (distributor) is used as a filter in several collections
- `date_gdb` is used for temporal versioning of data
