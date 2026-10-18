import os
from google.adk.agents import Agent
from google.genai import types
from google.adk.tools import google_search

from dotenv import load_dotenv
load_dotenv()

MODEL = "gemini-3.8-flash"
AGENT_APP_NAME = 'countwords'


def count_words(text: str) -> int:
    """
    Counts the number of words in the provided text string.

    Args:
        text (str): The input text to analyze.

    Returns:
        int: The total count of words.
    """
    # split() without arguments automatically handles multiple spaces,
    # newlines, and tabs, returning a list of actual words.
    words = text.split()
    return len(words)

root_agent = Agent(
        model=MODEL,
        name=AGENT_APP_NAME,
        instruction="You are helpful assistant. Use available tools to answer user questions.",
        tools = [count_words]
)