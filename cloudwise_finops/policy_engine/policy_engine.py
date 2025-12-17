from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


policy_engine = Agent(
    name="PolicyEngine",
    description="Enforces budget policies and validates automation actions against compliance rules and risk thresholds.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
    ),
)
