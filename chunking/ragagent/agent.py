import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import VertexAiSearchTool

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "genai-app-builder")
DATASTORE_PROJECT_ID = os.getenv("DATASTORE_PROJECT_ID", "genai-app-builder")
DATASTORE_ID = os.getenv(
    "DATASTORE_ID",
    f"projects/{DATASTORE_PROJECT_ID}/locations/global/collections/default_collection/dataStores/pekao-docs_1792520005788",
)
MODEL = os.getenv("MODEL", "gemini-3.7-flash")

root_agent = Agent(
    name="rag_agent",
    model=MODEL,
    description="RAG agent grounded in Vertex AI Search datastore.",
    instruction=(
        "You are a helpful knowledge assistant. "
        "Answer questions accurately using information from the Vertex AI Search datastore. "
        "Always ground your responses in retrieved documents and cite sources when available."
    ),
    tools=[
        VertexAiSearchTool(data_store_id=DATASTORE_ID)
    ],
)