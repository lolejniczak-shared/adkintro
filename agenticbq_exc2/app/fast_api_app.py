# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import contextlib
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import AGENT_APP_NAME, root_agent
from app.agent import app as adk_app
from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes

logger = logging.getLogger(__name__)

load_dotenv()
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)
otel_to_cloud = True

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Shared trigger session service and runner for BigQuery remote function invocations
_trigger_session_service = InMemorySessionService()
_trigger_runner = Runner(
    agent=root_agent,
    app_name=AGENT_APP_NAME,
    session_service=_trigger_session_service,
)


async def _run_agent(message_text: str, user_id: str = "trigger") -> list:
    """Executes the agent in an isolated session and collects generated events."""
    session = await _trigger_session_service.create_session(
        app_name=AGENT_APP_NAME, user_id=user_id, session_id=str(uuid.uuid4())
    )
    events = []
    async for event in _trigger_runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text=message_text)]
        ),
    ):
        events.append(event)
    return events


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=otel_to_cloud,
    lifespan=lifespan,
)
app.title = AGENT_APP_NAME
app.description = f"API for interacting with the Agent {AGENT_APP_NAME}"


# BigQuery Remote Function endpoints
# BigQuery remote functions send POST {"calls": [["row1"], ...], "caller": "..."}
# and expect {"replies": ["reply1", ...]}.
# BQ remote functions typically point to root POST /, but /trigger/bq and /apps/{name}/trigger/bq
# are supported for explicit routing and trigger conventions.
@app.post("/", tags=["BigQuery Trigger"])
@app.post("/trigger/bq", tags=["BigQuery Trigger"])
@app.post(f"/apps/{AGENT_APP_NAME}/trigger/bq", tags=["BigQuery Trigger"])
async def trigger_bq(request: Request):
    """Processes batch inference calls from BigQuery Remote Functions.

    Translates BigQuery request structure to ADK runner calls and returns
    replies in BigQuery remote function contract format.
    """
    body = await request.json()
    calls: list = body.get("calls", [])
    user_id = body.get("caller") or body.get("sessionUser") or "bq"

    async def _process_row(row_args: list) -> str:
        if not row_args:
            text = ""
        elif len(row_args) == 1 and isinstance(row_args[0], str):
            text = row_args[0]
        else:
            text = json.dumps(row_args)

        try:
            events = await _run_agent(text, user_id=user_id)
            # Find the final response text
            for event in reversed(events):
                if event.is_final_response() and event.message and event.message.parts:
                    text_parts = [
                        p.text for p in event.message.parts if getattr(p, "text", None)
                    ]
                    if text_parts:
                        return "".join(text_parts).strip()
            # If no final text part found, serialize events
            return json.dumps([e.model_dump(mode="json") for e in events])
        except Exception as e:
            logger.exception("Error processing row in BigQuery trigger: %s", e)
            return f"Error: {e}"

    replies = await asyncio.gather(*[_process_row(row) for row in calls])
    return {"replies": list(replies)}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
