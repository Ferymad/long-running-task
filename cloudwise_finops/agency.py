from dotenv import load_dotenv
from agency_swarm import Agency
from finops_ceo import finops_ceo
from cloud_connector import cloud_connector
from anomaly_detector import anomaly_detector
from optimizer import optimizer
from policy_engine import policy_engine
from reporter import reporter

load_dotenv()


def create_agency(load_threads_callback=None):
    """Create and return the CloudWise FinOps agency instance.

    This function is required for deployment.
    """
    agency = Agency(
        finops_ceo,  # Entry point - receives user messages
        communication_flows=[
            # CEO orchestrates all workers
            (finops_ceo, cloud_connector),
            (finops_ceo, anomaly_detector),
            (finops_ceo, optimizer),
            (finops_ceo, policy_engine),
            (finops_ceo, reporter),
            # Cross-agent collaboration for pipeline workflows
            (cloud_connector, anomaly_detector),
            (anomaly_detector, optimizer),
            (optimizer, policy_engine),
            (policy_engine, optimizer),
        ],
        shared_instructions="shared_instructions.md",
    )
    return agency


if __name__ == "__main__":
    agency = create_agency()
    agency.terminal_demo()

    # For programmatic testing:
    # response = agency.get_response_sync("Show me total costs across all clouds for the last 30 days")
    # print(response)
