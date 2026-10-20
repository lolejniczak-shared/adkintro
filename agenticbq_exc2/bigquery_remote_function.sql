-- BigQuery Remote Function Setup & Testing
-- Project: genai-app-builder
-- Dataset: meetup0202 (or your custom dataset)
-- Cloud Run Endpoint: https://<cloud-run-service-url> or https://<cloud-run-service-url>/trigger/bq

-- 1. Create a Cloud Resource Connection in BigQuery (if not already existing)
-- Run via bq command line or BigQuery console:
-- bq mk --connection --location=EU --project_id=genai-app-builder --connection_type=CLOUD_RESOURCE bq-remote-conn
-- Then grant the connection's service account 'roles/run.invoker' on your Cloud Run service:
-- gcloud run services add-iam-policy-binding countwords \
--   --region europe-west4 \
--   --member="serviceAccount:<CONNECTION_SERVICE_ACCOUNT>" \
--   --role="roles/run.invoker"

-- 2. Define the Remote Function in BigQuery
-- Note: Replace <PROJECT_ID>, <DATASET>, <CONNECTION>, and <CLOUD_RUN_URL> with your values.
CREATE OR REPLACE FUNCTION `genai-app-builder.meetup0202.count_words_remote`(text STRING)
RETURNS STRING
REMOTE WITH CONNECTION `genai-app-builder.eu.meetup0202_conn`
OPTIONS (
  -- BigQuery Remote Functions send POST {"calls": [["row1"], ...]}
  -- You can use the root URL (https://<service-url>) or /trigger/bq
  endpoint = 'https://countwords-xxxx-ey.a.run.app/trigger/bq',
  max_batching_rows = 10
);

-- 3. Query using the remote function
-- Scalar test:
SELECT `genai-app-builder.meetup0202.count_words_remote`('The quick brown fox jumps over the lazy dog') AS word_count_result;

-- Table test over rows:
SELECT
  comment_text,
  `genai-app-builder.meetup0202.count_words_remote`(comment_text) AS word_count_analysis
FROM
  `genai-app-builder.meetup0202.social_media_comments`
LIMIT 10;
