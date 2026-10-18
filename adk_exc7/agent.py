from google.adk import Agent, Workflow
from google.adk.workflow import node
from typing import Any

@node(name="framework_manifest")
def my_node(node_input: Any):
    return "This workflow is handled by ADK 2.0"

generate_fruit_agent = Agent(
    name="generate_fruit_agent",
    instruction="Return the name of a random fruit. Return only the name.",
)

generate_benefit_agent = Agent(
    name="generate_benefit_agent",
    instruction="Tell me a health benefit about the specified fruit.",
)

root_agent = Workflow(
    name="root_agent",
    edges=[("START", my_node, generate_fruit_agent, generate_benefit_agent)],
)