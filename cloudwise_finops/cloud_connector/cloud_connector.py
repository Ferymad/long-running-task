from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


cloud_connector = Agent(
    name="CloudConnector",
    description="Fetches and normalizes cost data from AWS, GCP, and Azure into a unified format for analysis.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="medium", summary="auto"),
    ),
)
