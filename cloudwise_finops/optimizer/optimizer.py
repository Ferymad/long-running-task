from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


optimizer = Agent(
    name="Optimizer",
    description="Analyzes cloud resources and recommends cost optimization strategies including rightsizing, reserved instances, and cross-cloud arbitrage.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
    ),
)
