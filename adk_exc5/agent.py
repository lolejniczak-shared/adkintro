import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.planners.built_in_planner  import BuiltInPlanner


#### Router with sub agents - experts

load_dotenv()

MODEL = "gemini-3.8-flash"
AGENT_APP_NAME = 'employee_assistant'

expert_marketing = LlmAgent(
        model=MODEL,
        name="marketing_expert",
        description="Agent to answer questions about marketing strategies",
        instruction="You are marketing specialist",
        mode = "task",
        tools = []
)

expert_cloud = LlmAgent(
        model=MODEL,
        name="google_cloud_expert",
        description="Agent to answer questions about google cloud services" ,
        instruction="You are google cloud specialist",
        tools = []
)

expert_legal = LlmAgent(
        model=MODEL,
        name="legal_stuff_expert",
        description="Agent to answer questions about legal",
        instruction="You are legal specialist",
        tools = []
)


root_agent = LlmAgent(
        model=MODEL,
        name=AGENT_APP_NAME,
        instruction="Route user requests to best experts to answer questions. When needed break question into smaller questions that can be covered by available experts and let them answer question from their domain",
        sub_agents = [
            expert_marketing, 
            expert_cloud, 
            expert_legal
           ],
        planner = BuiltInPlanner(
                thinking_config = types.ThinkingConfig(thinking_budget=-1, 
                include_thoughts = True)
        )
)