import os
from fastapi.testclient import TestClient

# Ensure environment variables are loaded
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "genai-app-builder")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("MODEL", "gemini-3.8-flash")

from app.agent import count_words, root_agent
from app.fast_api_app import app


def test_count_words_function():
    assert count_words("Hello world") == 2
    assert count_words("   One   two   three   four   ") == 4
    assert count_words("SingleWord") == 1
    assert count_words("") == 0


def test_bq_remote_function_endpoints():
    client = TestClient(app)

    bq_payload = {
        "requestId": "test-req-123",
        "caller": "//bigquery.googleapis.com/projects/genai-app-builder/jobs/test",
        "sessionUser": "user@example.com",
        "userDefinedContext": {},
        "calls": [
            ["The quick brown fox jumps over the lazy dog"],
            ["BigQuery remote function calls ADK agent"]
        ]
    }

    # Test /trigger/bq endpoint
    response = client.post("/trigger/bq", json=bq_payload)
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert "replies" in data
    assert len(data["replies"]) == 2
    print("\n--- /trigger/bq replies ---")
    for r in data["replies"]:
        print("Reply:", r)

    # Test root / endpoint (required for BQ remote functions without paths)
    response_root = client.post("/", json=bq_payload)
    assert response_root.status_code == 200
    data_root = response_root.json()
    assert "replies" in data_root
    assert len(data_root["replies"]) == 2


if __name__ == "__main__":
    test_count_words_function()
    print("test_count_words_function passed!")
    test_bq_remote_function_endpoints()
    print("test_bq_remote_function_endpoints passed!")
