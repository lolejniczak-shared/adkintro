# ruff: noqa
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

"""Customer support representative workflow agent for a shipping company.

This graph workflow classifies customer queries into shipping-related
(rates, tracking, delivery, returns) or unrelated. Shipping queries are
routed to a specialized shipping FAQ agent, while unrelated queries are
routed to a node that politely declines to answer.
"""

from collections.abc import AsyncGenerator, Generator
import os
import re
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.models import Gemini
from google.adk.workflow import Workflow
from google.genai import Client, types

load_dotenv()

MODEL = "gemini-3.8-flash"

_genai_client: Client | None = None


def get_genai_client() -> Client:
    """Returns a Google GenAI Client configured for Vertex AI or Google AI Studio."""
    global _genai_client
    if _genai_client is None:
        if os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in (
            "true",
            "1",
        ) or os.getenv("GOOGLE_CLOUD_PROJECT"):
            _genai_client = Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-east1"),
            )
        else:
            _genai_client = Client()
    return _genai_client


def extract_query_text(node_input: Any) -> str:
    """Extracts plain text query from Content, dict, or str."""
    if isinstance(node_input, str):
        return node_input
    if hasattr(node_input, "parts") and node_input.parts:
        parts_text = [
            p.text for p in node_input.parts if getattr(p, "text", None)
        ]
        if parts_text:
            return " ".join(parts_text).strip()
    if isinstance(node_input, dict):
        return str(
            node_input.get("text", "")
            or node_input.get("query", "")
            or node_input.get("prompt", "")
            or ""
        )
    if hasattr(node_input, "text"):
        return str(node_input.text)
    return str(node_input) if node_input is not None else ""


def _heuristic_shipping_check(query: str) -> str:
    """Heuristic fallback to identify shipping-related queries."""
    shipping_keywords = {
        "ship",
        "shipping",
        "shipment",
        "rate",
        "rates",
        "cost",
        "price",
        "track",
        "tracking",
        "deliver",
        "delivery",
        "delivered",
        "package",
        "parcel",
        "box",
        "return",
        "returns",
        "refund",
        "courier",
        "carrier",
        "transit",
        "freight",
        "postage",
        "label",
        "order",
        "status",
        "dispatch",
    }
    tokens = set(re.findall(r"\b\w+\b", query.lower()))
    if tokens & shipping_keywords:
        return "shipping"
    return "unrelated"


async def classify_query(node_input: Any = None) -> Event:
    """Classifies if user query is related to shipping or unrelated.

    Routes to 'shipping' if the query is about rates, tracking, delivery, or returns.
    Routes to 'unrelated' otherwise.
    """
    query_text = extract_query_text(node_input)
    if not query_text:
        return Event(output="", route="unrelated")

    prompt = (
        "You are a customer query classification system for a shipping company's customer support service.\n"
        "Analyze the following customer query and decide if it is related to shipping "
        "(such as shipping rates, package tracking, delivery status/options, returns, or shipping policies) or unrelated.\n\n"
        f'Customer Query: "{query_text}"\n\n'
        "Respond with ONLY 'shipping' if it is related to shipping, or 'unrelated' if it is unrelated."
    )

    try:
        client = get_genai_client()
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        resp_text = (response.text or "").strip().lower()
        if "shipping" in resp_text:
            route = "shipping"
        elif "unrelated" in resp_text:
            route = "unrelated"
        else:
            route = _heuristic_shipping_check(query_text)
    except Exception:
        # Graceful fallback to heuristic classification
        route = _heuristic_shipping_check(query_text)

    return Event(output=query_text, route=route)



def track_shipment(tracking_number: str) -> str:
    """Track the status and location of a package or shipment.

    Args:
        tracking_number: The package tracking number (e.g., TRK12345678).

    Returns:
        A string containing current shipment status, location, and estimated delivery date.
    """
    cleaned = tracking_number.strip().upper()
    if not cleaned:
        return "Please provide a valid tracking number."
    return (
        f"Shipment {cleaned} is currently In Transit. "
        "Current location: Central Distribution Hub, Chicago, IL. "
        "Estimated delivery date: Tomorrow by 5:00 PM."
    )


def get_shipping_rates(service_type: str = "all") -> str:
    """Get information about available shipping rates and delivery times.

    Args:
        service_type: Optional specific service ('standard', 'express', 'overnight', or 'all').

    Returns:
        Information on pricing and delivery speeds.
    """
    rates = {
        "standard": "Standard Ground (3-5 business days): Starting at $5.99 (Free for orders over $50).",
        "express": "Express 2-Day (2 business days): Starting at $14.99.",
        "overnight": "Overnight Priority (Next business day by 10:30 AM): Starting at $29.99.",
    }
    svc = service_type.strip().lower()
    if svc in rates:
        return rates[svc]
    return (
        "Available Shipping Options:\n"
        f"- {rates['standard']}\n"
        f"- {rates['express']}\n"
        f"- {rates['overnight']}"
    )


def get_return_policy() -> str:
    """Provides the company return policy and instructions for return shipping.

    Returns:
        Detailed return guidelines and procedure.
    """
    return (
        "SwiftShip Return Policy:\n"
        "- Returns are accepted within 30 days of delivery for a full refund.\n"
        "- Items must be in original condition with packaging intact.\n"
        "- Returns can be initiated online to print a prepaid return shipping label.\n"
        "- Drop off return packages at any authorized SwiftShip drop-off location or schedule a pickup."
    )


shipping_faq_agent = LlmAgent(
    name="shipping_faq_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a professional customer support representative for SwiftShip, a premier shipping company. "
        "Your role is to assist customers with shipping-related inquiries, including:\n"
        "- Shipping rates, pricing estimates, and shipping methods (Standard, Express, Overnight)\n"
        "- Package tracking, status updates, and delivery timelines\n"
        "- Delivery options, scheduling, and address changes\n"
        "- Return policies, return labels, and refund procedures\n\n"
        "Be polite, clear, accurate, and helpful. Use the available tools when specific "
        "tracking numbers, shipping rates, or return policies are requested. "
        "If a customer asks to track a package without providing a tracking number, "
        "politely prompt them for their tracking number."
    ),
    tools=[track_shipment, get_shipping_rates, get_return_policy],
    description="Specialist agent that answers shipping FAQs (rates, tracking, delivery, returns).",
)


def decline_node(node_input: Any = None) -> Generator[Event, None, None]:
    """Politely declines to answer queries that are unrelated to shipping."""
    message = (
        "Thank you for reaching out! However, I can only assist with shipping-related "
        "inquiries such as package tracking, shipping rates, delivery times, and returns. "
        "Please let me know if you have any questions regarding our shipping services!"
    )
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=message)],
        )
    )
    yield Event(output=message)


root_agent = Workflow(
    # Keep in sync with agents-cli-manifest.yaml: agents-cli derives this name
    # from the project `name:` recorded there, and telemetry reports it as
    # gen_ai.agent.name. Renaming the agent only here makes the two disagree,
    # and anything selecting traces by name stops finding this agent's.
    name="customer_support_agent",
    description="Customer support representative workflow for a shipping company.",
    edges=[
        ("START", classify_query),
        (
            classify_query,
            {
                "shipping": shipping_faq_agent,
                "unrelated": decline_node,
                "__DEFAULT__": decline_node,
            },
        ),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
