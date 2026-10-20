# ADK Word Count Agent with BigQuery Remote Function Trigger

This project provides an ADK (Agent Development Kit) agent equipped with a `count_words` tool, prepared via `agents-cli` for Cloud Run deployment and configured to handle BigQuery Remote Function batch inference calls (`/trigger/bq` and `/`).

## Architecture & BigQuery Contract

BigQuery Remote Functions call Cloud Run over HTTPS using a batching protocol:
- **Request Format:**
  ```json
  {
    "caller": "//bigquery.googleapis.com/projects/...",
    "sessionUser": "user@example.com",
    "userDefinedContext": {},
    "calls": [
      ["Row 1 text to analyze"],
      ["Row 2 text to analyze"]
    ]
  }
  ```
- **Response Format:**
  ```json
  {
    "replies": [
      "Agent reply for row 1",
      "Agent reply for row 2"
    ]
  }
  ```

In [`app/fast_api_app.py`](file:///home/user/prepday1/agenticbq_exc2/app/fast_api_app.py), the `trigger_bq` endpoint translates the incoming BigQuery rows to ADK `Runner` executions, running each row inside an isolated ephemeral session, and returns the agent's replies in the exact order expected by BigQuery.

Both `/trigger/bq` and `/` (root endpoint required if BigQuery remote functions don't accept subpaths) are mapped to this handler.

## Project Structure

```
├── app/
│   ├── agent.py               # Defines root_agent, count_words tool, and model (gemini-3.8-flash)
│   ├── fast_api_app.py        # FastAPI server with /trigger/bq and / BigQuery remote function endpoints
│   └── app_utils/             # Service & A2A utilities
├── deployment/
│   └── terraform/             # Terraform infrastructure including BigQuery connection & routine
├── 1_deploy_to_cloudrun.sh    # Script to deploy the service to Cloud Run
├── bigquery_remote_function.sql # SQL snippet to define and test the remote function in BigQuery
├── test_bq_endpoint.py        # Local verification test script
├── Dockerfile                 # Cloud Run container definition
└── agents-cli-manifest.yaml   # agents-cli configuration
```

## Agent Definition ([`app/agent.py`](file:///home/user/prepday1/agenticbq_exc2/app/agent.py))

```python
MODEL = os.getenv("MODEL", "gemini-3.8-flash")
AGENT_APP_NAME = os.getenv("AGENT_APP_NAME", "countwords")

def count_words(text: str) -> int:
    """
    Counts the number of words in the provided text string.

    Args:
        text (str): The input text to analyze.

    Returns:
        int: The total count of words.
    """
    words = text.split()
    return len(words)

root_agent = Agent(
    model=MODEL,
    name=AGENT_APP_NAME,
    instruction="You are helpful assistant. Use available tools to answer user questions.",
    tools=[count_words],
)
```

## Verification & Testing

Run the test suite to verify the tool and the BigQuery batch endpoint:

```bash
/home/user/prepday1/vadk/bin/python3 test_bq_endpoint.py
```

## Deployment to Cloud Run

To deploy to Cloud Run:

```bash
./1_deploy_to_cloudrun.sh
```

Or using `agents-cli`:

```bash
agents-cli deploy --deployment-target cloud_run --service-name countwords
```
