"""
SAR Workflow Test - Connected Users Query
Builds and executes the connected users / network activity query against Snowflake.
Accepts a list of customer tokens and a date range.
"""

# The full multi-step SQL query template.
# Placeholders: {tokens_list}, {start_date}, {end_date}

CONNECTED_USERS_SQL = """
USE WAREHOUSE COMPLIANCE;
USE DATABASE PERSONAL_AJU;
USE SCHEMA PUBLIC;

SET START_DATE = '{start_date}';
SET END_DATE = '{end_date}';

/************************************/

-- Temporary tables will be available until the session ends

CREATE OR REPLACE TEMP TABLE token_list AS
SELECT DISTINCT 
    fc.token
  , fc.active_customer_id
FROM app_compliance.cash.customers fc
WHERE
  fc.token IN ({tokens_list})
;

--Connected Users first degree hard connections and subsequent SSN second degree connections

CREATE OR REPLACE TEMP TABLE conn_users as
SELECT
  cu.active_customer_id
  , connected_active_customer_id
  , connection_type
  , connected_user_type
  , 1 AS connection_degree
FROM app_compliance.cash.cash_connected_users AS cu
JOIN token_list AS t
  ON t.active_customer_id = cu.active_customer_id
WHERE
  connection_type IN ('PAYMENT_CARD','SSN','BANK_ACCOUNT','EMAIL')
  AND connected_user_type = 'CASH_CUSTOMER'
GROUP BY
  1, 2, 3, 4
UNION
SELECT
  t.active_customer_id
  , c.active_customer_id AS connected_active_customer_id
  , 'CASH_FOR_TEENS_SPONSOR' AS connection_type
  , 'CASH_CUSTOMER' AS connected_user_type
  , 1 AS connection_degree
FROM token_list AS t
JOIN app_compliance.cash.cash_global_cash_for_teens_sponsors AS cfts
  ON t.token = cfts.dependent_customer_token
LEFT JOIN app_compliance.cash.customers AS c
  ON cfts.sponsor_customer_token = c.token
UNION
SELECT
  t.active_customer_id
  , c.active_customer_id AS connected_active_customer_id
  , 'CASH_FOR_TEENS_SPONSORED' AS connection_type
  , 'CASH_CUSTOMER' AS connected_user_type
  , 1 AS connection_degree
FROM token_list AS t
JOIN app_compliance.cash.cash_global_cash_for_teens_sponsors AS cfts
  ON t.token = cfts.sponsor_customer_token
LEFT JOIN app_compliance.cash.customers AS c
  ON cfts.dependent_customer_token = c.token
UNION
SELECT
  active_customer_id
  , active_customer_id AS connected_active_customer_id
  , 'SELF' AS connection_type
  , 'CASH_CUSTOMER' AS connected_user_type
  , 0 AS connection_degree
FROM token_list
;

--Transfers

CREATE OR REPLACE TEMP TABLE cin_cout AS
WITH transfers_base AS (
SELECT
  cu.connected_active_customer_id
  , t.type
  , t.state
  , t.token
  , t.amount_cents
FROM app_compliance.cash.transfers t
JOIN conn_users AS cu
  ON cu.connected_active_customer_id = t.customer_id
WHERE
  to_date(t.created_at) BETWEEN $START_DATE AND $END_DATE
  AND type = 'CASH_IN'
UNION ALL
SELECT
  cu.connected_active_customer_id
  , 'CASH_IN' AS type
  , state
  , transfer_token AS token
  , amount_cents
FROM app_compliance.cash.cash_ins t
JOIN conn_users AS cu
  ON cu.connected_active_customer_id = t.active_customer_id
WHERE
  to_date(t.initiated_at) BETWEEN $START_DATE AND $END_DATE
),

transfers_dedup AS (
SELECT
  connected_active_customer_id
  , type
  , state
  , token
  , amount_cents
FROM transfers_base
QUALIFY 
  ROW_NUMBER() OVER (PARTITION BY token ORDER BY token) = 1
),

transfers_agg AS (
SELECT
    connected_active_customer_id
  , type
  , state
  , COUNT(DISTINCT token) AS cash_in_out_count
  , SUM(amount_cents / 100) AS cash_in_out_total
FROM transfers_dedup AS t
GROUP BY 
  1, 2, 3
)

SELECT
  connected_active_customer_id
, SUM(CASE
        WHEN type = 'CASH_IN' AND state in ('COMPLETE', 'COMPLETED') THEN cash_in_out_count
        ELSE NULL
      END) AS successful_cash_in_count
, SUM(CASE 
        WHEN type = 'CASH_IN' AND state = 'FAILED' THEN cash_in_out_count
        ELSE NULL
      END) AS failed_cash_in_count 
FROM transfers_agg
GROUP BY 1
ORDER BY 1
;

--Movements
CREATE OR REPLACE TEMP TABLE cash_payments AS
WITH p2p_base AS (
SELECT
  cu.connected_active_customer_id
  , m.role
  , m.payment_state
  , m.payment_id::STRING AS payment_token 
  , m.movement_amount_cents AS amount_cents
  , c.token  AS counterparty_token
FROM app_compliance.cash.movements m
JOIN conn_users cu
  ON cu.connected_active_customer_id = m.customer_id
JOIN app_compliance.cash.customers c
  ON m.original_counterparty_id = c.id
WHERE
 TO_DATE(m.created_at) BETWEEN $START_DATE AND $END_DATE
UNION ALL
SELECT
  cu.connected_active_customer_id
  , t.role
  , t.payment_state
  , t.payment_id::STRING AS payment_token 
  , t.amount_cents 
  , t.counterparty_token
FROM app_compliance.cash.p2p_transactions t
JOIN app_compliance.cash.customers c
  ON c.token = t.customer_token
JOIN conn_users cu
  ON cu.connected_active_customer_id = c.id 
WHERE
 TO_DATE(t.created_at) BETWEEN $START_DATE AND $END_DATE
),

p2p_dedup AS (
SELECT 
  connected_active_customer_id
  , role
  , payment_state
  , payment_token 
  , amount_cents
  , counterparty_token
FROM p2p_base p
QUALIFY 
  ROW_NUMBER() OVER (PARTITION BY payment_token, role ORDER BY payment_token) = 1
),

distinct_counterparty_tokens AS (
SELECT
  connected_active_customer_id
  , COUNT(DISTINCT counterparty_token) AS unique_senders_recipients
FROM p2p_dedup
GROUP BY 1
),

p2p_agg AS (
SELECT
  p2p.connected_active_customer_id
  , p2p.role
  , p2p.payment_state
  , dct.unique_senders_recipients
  , COUNT(DISTINCT p2p.payment_token) AS movement_count
  , SUM(p2p.amount_cents/100) AS total_amount_movement
FROM p2p_dedup p2p
LEFT JOIN distinct_counterparty_tokens dct
  ON p2p.connected_active_customer_id = dct.connected_active_customer_id
GROUP BY 1,2,3,4
)

SELECT 
  connected_active_customer_id
, SUM(CASE 
        WHEN role = 'SENDER' AND payment_state NOT IN ('FAILED', 'PAYMENT_STATE_CODE_FAILED') THEN movement_count
        ELSE NULL
      END) AS successful_sent_count
, SUM(CASE 
        WHEN role IN ('RECIPIENT', 'RECIEVER') AND payment_state NOT IN ('FAILED', 'PAYMENT_STATE_CODE_FAILED') THEN movement_count
        ELSE NULL
      END) AS successful_received_count
, SUM(CASE 
        WHEN role = 'SENDER' AND payment_state IN ('FAILED', 'PAYMENT_STATE_CODE_FAILED') THEN movement_count
        ELSE NULL
      END) AS failed_sent_count
, SUM(CASE 
        WHEN role IN ('RECIPIENT', 'RECIEVER') AND payment_state IN ('FAILED', 'PAYMENT_STATE_CODE_FAILED') THEN movement_count
        ELSE NULL
      END) AS failed_received_count
, MAX(unique_senders_recipients) AS unique_senders_recipients
FROM p2p_agg
GROUP BY 1
;

--BTC Withdrawals

CREATE OR REPLACE TEMP TABLE btc_wd AS
SELECT DISTINCT
    cu.connected_active_customer_id
  , COUNT(DISTINCT t.token) AS withdrawal_count
FROM app_compliance.cash.transactions t
JOIN app_compliance.cash.instrument_links i 
  ON t.instrument_token = i.instrument_token
  AND t.currency = 'BTC'
  AND t.reason_code = 'BITCOIN_TRANSFER'
JOIN app_compliance.cash.customers c
  ON i.customer_id = c.id
JOIN conn_users cu 
  ON c.active_customer_id = cu.connected_active_customer_id
WHERE
  TO_DATE(t.created_at) BETWEEN $START_DATE AND $END_DATE
GROUP BY 1
;

--Chargebacks

CREATE OR REPLACE TEMP TABLE transfers_cb AS
SELECT DISTINCT
    cu.connected_active_customer_id
  , SUM(cb.payment_amount_cents / 100) AS total_transfer_chargeback
FROM app_compliance.cash.chargebacks AS cb
JOIN conn_users AS cu
  ON cb.sender_id = cu.connected_active_customer_id
WHERE
  TO_DATE(cb.chargeback_date) BETWEEN $START_DATE AND $END_DATE
GROUP BY 1
;

--Open sar cases 

CREATE OR REPLACE TEMP TABLE sar AS
SELECT
    cu.connected_active_customer_id
  , LISTAGG(DISTINCT CASE WHEN sc.latest_case_status <> 'closed' THEN sc.case_token ELSE NULL END, ',') AS open_sar
  , LISTAGG(DISTINCT CASE WHEN sc.latest_case_status = 'closed' THEN sc.case_token ELSE NULL END, ',') AS closed_sar
FROM app_sar.sargent.cases AS sc
JOIN app_sar.sargent.cases_users AS scu 
  ON sc.case_token = scu.case_token
JOIN app_compliance.cash.customers AS c
  ON c.token = scu.user_token
JOIN conn_users AS cu
  ON c.active_customer_id = cu.connected_active_customer_id
GROUP BY 1
;

--Aggregate table

CREATE OR REPLACE TEMP TABLE final AS
SELECT
    c.token AS input_token
  , c2.token AS connected_token
  , cu.connected_user_type AS type
  , cu.connection_type
  , cu.connection_degree AS degree
  , ci.successful_cash_in_count
  , ci.failed_cash_in_count
  , cp.successful_sent_count 
  , cp.successful_received_count 
  , cp.failed_sent_count 
  , cp.failed_received_count 
  , cp.unique_senders_recipients
  , bt.withdrawal_count
  , t.total_transfer_chargeback
  , s.open_sar
  , s.closed_sar
FROM conn_users AS cu
JOIN app_compliance.cash.customers AS c
  ON cu.active_customer_id = c.id
JOIN app_compliance.cash.customers AS c2
  ON cu.connected_active_customer_id = c2.id
LEFT JOIN cin_cout AS ci
  ON cu.connected_active_customer_id = ci.connected_active_customer_id
LEFT JOIN cash_payments AS cp 
  ON cu.connected_active_customer_id = cp.connected_active_customer_id
LEFT JOIN btc_wd AS bt 
  ON bt.connected_active_customer_id = cu.connected_active_customer_id
LEFT JOIN transfers_cb AS t 
  ON t.connected_active_customer_id = cu.connected_active_customer_id
LEFT JOIN sar AS s
  ON s.connected_active_customer_id = cu.connected_active_customer_id
;

--Final output 

SELECT base.*
FROM
(
SELECT
    input_token
  , connected_token
  , LISTAGG(DISTINCT connection_type, ',') AS connection_type
  , MIN(degree) AS degree
  , COALESCE(successful_cash_in_count, 0) + COALESCE(failed_cash_in_count, 0) AS attempted_cash_in_cnt
  , COALESCE(successful_sent_count, 0) + COALESCE(Successful_received_count, 0) + COALESCE(Failed_sent_count, 0) + COALESCE(Failed_received_count, 0) AS attempted_p2p_cnt
  , COALESCE(unique_senders_recipients, 0) AS unique_senders_recipients
  , COALESCE(withdrawal_count, 0) AS withdrawal_count
  , COALESCE(total_transfer_chargeback, 0) AS total_transfer_chargeback
  , open_sar
  , closed_sar
FROM final 
GROUP BY
  1, 2, 5, 6, 7, 8, 9, 10, 11
) AS base
WHERE degree <= 1
ORDER BY
  1 ASC, 4 ASC, 2 ASC
;
"""


def validate_token(token: str) -> str:
    """Sanitize and validate a single customer token."""
    token = token.strip().strip("'\"")
    # Only allow alphanumeric, underscores, and hyphens
    if not all(c.isalnum() or c in ('_', '-') for c in token):
        raise ValueError(f"Invalid token format: {token}")
    return token


def validate_date(date_str: str) -> str:
    """Validate date is in YYYY-MM-DD format."""
    import re
    date_str = date_str.strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")
    return date_str


def build_query(tokens: list, start_date: str, end_date: str) -> str:
    """
    Build the full connected users SQL query.
    
    Args:
        tokens: List of customer token strings (e.g., ['C_8mc9xgyqy', 'C_abc123'])
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        Complete SQL query string ready for execution
    """
    # Validate inputs
    validated_tokens = [validate_token(t) for t in tokens if t.strip()]
    if not validated_tokens:
        raise ValueError("At least one token is required.")
    
    start_date = validate_date(start_date)
    end_date = validate_date(end_date)
    
    # Build quoted token list: 'token1', 'token2', ...
    tokens_list = ", ".join(f"'{t}'" for t in validated_tokens)
    
    # Fill template
    query = CONNECTED_USERS_SQL.format(
        tokens_list=tokens_list,
        start_date=start_date,
        end_date=end_date
    )
    
    return query


def split_query_statements(query: str) -> list:
    """
    Split the multi-statement SQL into individual statements for sequential execution.
    Returns a list of non-empty SQL statements.
    """
    statements = []
    for stmt in query.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        # Strip leading comment-only lines and block comments to find actual SQL
        lines = stmt.split('\n')
        has_sql = False
        for line in lines:
            stripped = line.strip()
            # Skip comments and block comment delimiters
            if (stripped and 
                not stripped.startswith('--') and 
                not stripped.startswith('/*') and 
                not stripped.startswith('*') and 
                stripped != '*/' and
                not all(c in '/*' for c in stripped)):
                has_sql = True
                break
        if has_sql:
            statements.append(stmt)
    return statements
