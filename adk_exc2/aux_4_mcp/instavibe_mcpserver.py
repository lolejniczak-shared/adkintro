import os
import json
import requests
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

import google.auth
import google.auth.transport.requests
import google.oauth2.id_token

from urllib.parse import urlparse
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Demo 🚀")

load_dotenv()
BASE_URL = os.environ.get("INSTAVIBE_BASE_URL")

# --- Structured Pydantic Models for Robust Input Validation ---
class LocationModel(BaseModel):
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    address: Optional[str] = None

# --- Helper Authentication Functions ---
def get_id_token(audience_url: str) -> Optional[str]:
    """
    Fetches a Google-signed ID token for the specified audience using ADC.
    """
    print(f"Attempting to fetch ID token for audience: {audience_url}")
    try:
        credentials, project = google.auth.default()
        auth_request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_request, audience_url)
        print("Successfully fetched ID token.")
        return token
    except Exception as e:
        print(f"Error fetching ID token: {e}")
        print("Please ensure you have authenticated with 'gcloud auth application-default login'")
        print("or that your service account has the 'Cloud Run Invoker' role.")
        return None

def verify_google_id_token(token_string: str, audience: str) -> Optional[Dict[str, Any]]:
    """
    Parses and verifies a Google-signed ID token.
    """
    if not audience:
        print("Error: Audience (INSTAVIBE_BASE_URL) is not set. Cannot verify token.")
        return None
    if not token_string:
        print("Error: No token string provided.")
        return None

    try:
        auth_request = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(token_string, auth_request, audience)
        print("Token successfully verified.")
        return id_info
    except Exception as e:
        print(f"Error: Token verification failed: {e}")
        return None

# --- MCP Tools ---

@mcp.tool()
def create_post(author_name: str, text: str, sentiment: str, base_url: str = BASE_URL) -> Optional[Dict[str, Any]]:
    """
    Sends a POST request to the /posts endpoint to create a new post.

    Args:
        author_name: The name of the post's author.
        text: The content of the post.
        sentiment: The sentiment associated with the post (e.g., 'positive', 'negative', 'neutral').
        base_url: The base URL of the API. Defaults to BASE_URL.
    """
    url = f"{base_url}/posts"
    parsed_url = urlparse(url)
    root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    token = get_id_token(root_url)
    if not token:
        print("Aborting post creation due to authentication failure.")
        return None
        
    verify_google_id_token(token, root_url)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "author_name": author_name,
        "text": text,
        "sentiment": sentiment
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Successfully created post. Status Code: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating post: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None

@mcp.tool()
def create_event(
    event_name: str, 
    description: str, 
    event_date: str, 
    locations: List[LocationModel],  # Changed from generic 'list' to strict list of structures
    attendee_names: List[str],      # Cleaned up type structure for compatibility
    base_url: str = BASE_URL
) -> Optional[Dict[str, Any]]:
    """
    Sends a POST request to the /events endpoint to create a new event registration.

    Args:
        event_name: The name of the event.
        description: The detailed description of the event.
        event_date: The date and time of the event (ISO 8601 format, e.g., "2025-06-10T09:00:00Z").
        locations: A list of Location models containing name, coordinates, etc.
        attendee_names: A list of names of the people attending the event.
        base_url: The base URL of the API. Defaults to BASE_URL.
    """
    url = f"{base_url}/events"
    token = get_id_token(base_url)
    if not token:
        print("Aborting event creation due to authentication failure.")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Serverless-Authorization": f"Bearer {token}"
    }
    
    # Pydantic models must be serialized to dicts for JSON transmission
    serialized_locations = [loc.model_dump() for loc in locations]
    
    payload = {
        "event_name": event_name,
        "description": description,
        "event_date": event_date,
        "locations": serialized_locations,
        "attendee_names": attendee_names,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Successfully created event registration. Status Code: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating event registration: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None

if __name__ == "__main__":
    mcp.run()
