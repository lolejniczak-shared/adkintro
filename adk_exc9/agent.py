import os
from google.adk.agents import Agent
from google.genai import types
from google.adk.tools import google_search
from typing import AsyncGenerator
from pydantic import BaseModel
from pydantic import Field
import json

from dotenv import load_dotenv
load_dotenv()

MODEL = "gemini-3.8-flash"
AGENT_APP_NAME = 'countwords'

class InvocationSchema(BaseModel):
    question: str = Field(description="user question")
    intent: str = Field(description="user intent")
    answer: str = Field(description="answer to user question")


root_agent = Agent(
        model=MODEL,
        name=AGENT_APP_NAME,
        instruction="If they ask you how you were created, tell them you were created with the Google Agent Framework.",
        tools = [google_search],
        output_schema = InvocationSchema,
        output_key = "last_invocation"
)