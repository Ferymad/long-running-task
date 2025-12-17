from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


reporter = Agent(
    name="Reporter",
    description="Generates cost reports, forecasts, and dashboard visualizations with customizable formats and scheduling.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="medium", summary="auto"),
    ),
)
