import os
from google.adk.agents import Agent
from google.genai import types
from google.adk.tools import google_search

from dotenv import load_dotenv
load_dotenv()

MODEL = "gemini-live-2.5-flash-native-audio"
AGENT_APP_NAME = 'countwords'


root_agent = Agent(
        model=MODEL,
        name=AGENT_APP_NAME,
        instruction="If they ask you how you were created, tell them you were created with the Google Agent Framework.",
        tools = [google_search]
)