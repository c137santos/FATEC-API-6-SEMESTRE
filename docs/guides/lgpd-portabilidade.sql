-- =============================================================================
-- DATA PORTABILITY – LGPD Art. 18, III
-- Thunderstone Platform
-- =============================================================================
--
-- PURPOSE
--   Produces a structured JSON report containing all personal data stored
--   about a user, to fulfill data portability requests as required by
--   Art. 18, section III of the LGPD (Brazilian General Data Protection Law,
--   Lei nº 13.709/2018).
--
-- HOW TO RUN
--   Replace user_email below with the data subject's e-mail address and
--   execute using your preferred PostgreSQL client:
--
--   Option A — command line (no quotes around the -v value):
--     psql -U <user> -d <database> \
--          -v user_email=subject@example.com \
--          -f lgpd-portabilidade.sql
--Steps
1. Enter updated data in the form:
   - Name, Email, and/or Password  
2. Provide your **Current Password** (required for validation)  
3. (Optional) Enter a **New Password**  
4. Click **"Save Changes"**
--   Option B — inside the interactive psql shell:
--     \set user_email subject@example.com
--     \i lgpd-portabilidade.sql
--
--   In both cases the :'user_email' syntax in the WHERE clause automatically
--   wraps the value in single quotes:  WHERE email = 'subject@example.com'
--
--   The output is a single JSON object printed in the "report" column.
--   To save to a file:
--     psql ... -f lgpd-portabilidade.sql -o report_<email>.json
--
-- DATA INCLUDED
--   1. account_data         — identity fields and account creation date
--   2. consent_history      — all terms accepted or declined, with date,
--                             policy version, and full policy text
--   3. oauth_grants         — third-party applications authorized via OAuth 2
--                             (client_id, scopes, issuance dates)
--
-- DATA INTENTIONALLY EXCLUDED
--   • password              — security hash; not portable personal data
--                             (cannot be reconstructed in another system
--                             with the same semantics)
--   • email_token           — temporary e-mail verification token;
--                             expires in 24 h and is not personal data
--   • access_token /
--     refresh_token (value) — session credentials; only metadata is included
--                             (client, scope, dates)
--   • oauth2_authorization_codes — expire in 60 s; purely ephemeral
--
-- DATABASE: PostgreSQL 14+
-- QUERY VERSION: 1.0 | 2026-05-26
-- =============================================================================

WITH

-- -----------------------------------------------------------------------------
-- 1. Locate the data subject by e-mail address.
--    Replace :user_email with the requesting subject's e-mail.
-- -----------------------------------------------------------------------------
subject AS (
    SELECT
        id,
        username,
        email,
        created_at,
        is_verified,
        consented_at         AS mandatory_consent_recorded_at,
        consent_policy_id    AS mandatory_consent_policy_id
    FROM users
    WHERE email = :'user_email'
),

-- -----------------------------------------------------------------------------
-- 2. Full consent history.
--    Covers both mandatory consent (privacy policy) and optional consent
--    (e.g. marketing communications), including the full text of each policy
--    as it stood at the time of acceptance or refusal.
-- -----------------------------------------------------------------------------
consent_history AS (
    SELECT
        CASE WHEN cp.is_mandatory THEN 'mandatory' ELSE 'optional' END
                             AS type,
        CASE WHEN cp.is_mandatory THEN 'Privacy Policy'
             ELSE 'Marketing Communications'
        END                  AS name,
        cp.version           AS policy_version,
        uc.accepted,
        uc.consented_at      AS recorded_at,
        cp.content           AS full_policy_text
    FROM user_consents uc
    JOIN consent_policies cp ON cp.id = uc.consent_policy_id
    WHERE uc.user_id = (SELECT id FROM subject)
    ORDER BY cp.is_mandatory DESC, uc.consented_at
),

-- -----------------------------------------------------------------------------
-- 3. OAuth 2 grants issued by the data subject.
--    Records which third-party applications were granted access to the account,
--    with which scopes and for how long.
--    Tokens where access_token_revoked_at > 0 have been revoked.
-- -----------------------------------------------------------------------------
oauth_grants AS (
    SELECT
        t.client_id,
        t.scope                              AS authorized_scopes,
        to_timestamp(t.issued_at)            AS issued_at,
        to_timestamp(t.issued_at + t.expires_in)
                                             AS expires_at,
        (t.access_token_revoked_at > 0)      AS revoked
    FROM oauth2_tokens t
    WHERE t.user_id = (SELECT id FROM subject)
    ORDER BY t.issued_at DESC
)

-- -----------------------------------------------------------------------------
-- Final result: single JSON object with all sections.
-- -----------------------------------------------------------------------------
SELECT json_build_object(

    -- Report metadata
    '_metadata', json_build_object(
        'generated_at',  now(),
        'legal_basis',   'LGPD Art. 18, III – Lei nº 13.709/2018',
        'purpose',       'Personal data portability at data subject request'
    ),

    -- Section 1: account data
    'account_data', (
        SELECT row_to_json(s) FROM subject s
    ),

    -- Section 2: consent history (array, null if no records)
    'consent_history', (
        SELECT json_agg(row_to_json(c))
        FROM consent_history c
    ),

    -- Section 3: OAuth grants (array, null if none)
    'oauth_grants', (
        SELECT json_agg(row_to_json(g))
        FROM oauth_grants g
    )

) AS report;
