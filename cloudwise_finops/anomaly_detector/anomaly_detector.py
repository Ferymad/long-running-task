from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning


anomaly_detector = Agent(
    name="AnomalyDetector",
    description="Detects cost anomalies using statistical analysis and triggers alerts for spending spikes.",
    instructions="./instructions.md",
    files_folder="./files",
    tools_folder="./tools",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
    ),
)
