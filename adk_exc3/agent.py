from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
import os
load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

mcpt = McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://mapstools.googleapis.com/mcp",
                headers={
                    "X-Goog-Api-Key": API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                timeout=5,
                sse_read_timeout=300
            )
)


root_agent = LlmAgent(
    model="gemini-3.8-flash",
    name="travel_planner",
    instruction="Plan travel routes and search locations using Google Maps.",
    tools=[mcpt],
)