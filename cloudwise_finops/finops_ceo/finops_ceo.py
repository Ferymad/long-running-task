from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


finops_ceo = Agent(
    name="FinOpsCEO",
    description="Orchestrates multi-cloud cost analysis workflows, routes user requests to specialized agents, and synthesizes results into actionable insights.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
    ),
)
