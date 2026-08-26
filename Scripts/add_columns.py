import pandas as pd
import duckdb as dd


transcript = pd.read_csv("Data/raw_csv/transcript.csv")
portfolio = pd.read_csv("Data/raw_csv/portfolio.csv")
profile = pd.read_csv("Data/raw_csv/profile.csv")


# 1. DEFINE INTENTIONALLY COMPLETED OFFERS
offer_status = """
WITH campaigns AS (
    -- 1. SEPARATE SAME OFFERS BY TIME SENT
    SELECT
        person,
        "offer id",
        time,
        event,
        SUM(CASE WHEN event = 'offer received' THEN 1 ELSE 0 END)
            OVER (PARTITION BY person, "offer id" ORDER BY time) AS campaign_id 
        -- if an offer has been sent to the same users multiple times, it will be labeled as 1 the first time, 2 the second. and so on
    FROM transcript
    WHERE event != 'transaction'
)

-- 2. PIVOT OFFER TIMES AND DEFINE INTENTIONALLY COMPLETED
SELECT
    c.person,
    c."offer id",
    p.duration,
    p.offer_type,
    MAX(CASE WHEN c.event = 'offer received' THEN c.time END) AS time_received,
    MAX(CASE WHEN c.event = 'offer viewed' THEN c.time END) AS time_viewed,
    MAX(CASE WHEN c.event = 'offer completed' THEN c.time END) AS time_completed, -- this put the timeline on the same row for each offer
    
    CASE
        WHEN time_viewed >= time_received
            AND time_completed >= time_viewed
            AND time_completed <= time_received + (p.duration * 24) -- duration is expressed in days. 
        THEN 1 ELSE 0 -- Intentionally completed (1) if has been received. viewed, and completed before the deadline
    END AS is_success
FROM campaigns c
JOIN portfolio p ON c."offer id" = p.id
GROUP BY c.person, c."offer id", c.campaign_id, p.duration, p.offer_type -- remove join duplicates
"""

offer_status = dd.sql(offer_status)

# 1.1 CREATE A NEW TRANSCRIPT WITH THIS NEW COLUMN
is_success = offer_status.to_df()
is_success["event"] = "offer completed" # this allows to add the status only for offer completed events
new_transcript = pd.merge(left=transcript, 
                          right=is_success, 
                          left_on=["person", "offer id", "time", "event"],
                          right_on=["person", "offer id", "time_completed", "event"],
                          how="left")
new_transcript.drop(columns={"time_received", "time_viewed", "time_completed", "duration", "offer_type"}, inplace=True) # remove merge columns

# 1.2 FLAG TRANSACTIONS THAT HAPPENED OUTSIDE ACTIVE OFFER WINDOWS
natural_transaction_status = """
SELECT
    t.person,
    t.time,
    t.amount,
    CASE WHEN MAX(s."offer id") IS NULL THEN 1 ELSE 0 END AS is_natural_transaction
FROM transcript t
LEFT JOIN offer_status s
    ON t.person = s.person
    AND t.time >= s.time_viewed
    AND t.time <= COALESCE(s.time_completed, s.time_received + (s.duration * 24))
WHERE t.event = 'transaction'
GROUP BY t.person, t.time, t.amount
"""

natural_transaction_status = dd.sql(natural_transaction_status).to_df()
new_transcript = pd.merge(
    new_transcript,
    natural_transaction_status,
    on=["person", "time", "amount"],
    how="left",
)
new_transcript["is_natural_transaction"] = (
    new_transcript["is_natural_transaction"].fillna(0).astype(int)
)
new_transcript.to_csv("Data/processed/transcript.csv", index=False)


# 2. CALCULATE CUSTOMER AVERAGE NATURAL SPENDING AND RESPOSIVENESS TO OFFERS 

customers = """
WITH user_sensibility AS (
    -- 3. DEFINE OFFER SENSIBILITY AS # INTENTIONALLY COMPLETED OFFERS / # RECEIVED OFFERS
    SELECT 
        person,
        SUM(is_success) / CAST(COUNT(time_received) AS FLOAT) AS offer_sensitivity
    FROM offer_status
    WHERE offer_type != 'informational'
    GROUP BY person 
),

natural_transactions AS (
    -- 4. IDENTIFY TRANSACTIONS HAPPENED OUTSIDE ACTIVE OFFERS WINDOWS
    SELECT 
        t.person, 
        t.time, 
        t.amount
    FROM transcript t
    LEFT JOIN offer_status s 
        ON t.person = s.person
        AND t.time >= s.time_viewed
        AND t.time <= COALESCE(s.time_completed, s.time_received + (s.duration * 24)) -- if it completes an offer before the deadline, the window is time_received-time_completed
    WHERE t.event = 'transaction'
    GROUP BY t.person, t.time, t.amount
    HAVING MAX(s."offer id") IS NULL
),

user_spending AS (
    -- 5. COMPUTE HOW ON AVERAGE EACH USER SPEND WHEN THERE ARE NO ACTIVE OFFERS
    SELECT 
        person,
        AVG(amount) AS avg_natural_spending
    FROM natural_transactions
    GROUP BY person
)

-- PUT EVERYTHING TOGETHER
SELECT 
    p.id AS person,
    COALESCE(us.avg_natural_spending, 0) AS avg_natural_spending,
    COALESCE(sens.offer_sensibility, 0) AS offer_sensibility
FROM profile p
LEFT JOIN user_spending us ON p.id = us.person
LEFT JOIN user_sensibility sens ON p.id = sens.person
WHERE p.age != 118 
  AND p.gender != 'O';
"""

# 2.1 CREATE A NEW PROFILE WITH THESE TWO ADDITIONAL INFORMATIONS FOR EACH USER

new_features = dd.sql(customers).to_df()
new_profile = pd.merge(left=profile, right=new_features, left_on='id', right_on='person', how='left')
new_profile.drop(["person"], axis=1).to_csv("Data/processed/profile.csv", index=False)