import sys
from pathlib import Path
import logging

# Set logging level to INFO at the application's entry point
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the project root to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from google.adk import Agent
from config import settings
from agent.prompts import DATA_ANALYST_INSTRUCTIONS, SERVICENOW_INSTRUCTIONS, COORDINATOR_INSTRUCTIONS # Import all three instruction sets
from tools.db_tools import execute_analytics_sql
from tools.servicenow_tools import (
    get_servicenow_ticket_details,
    create_servicenow_ticket,
    search_servicenow_incidents,
    update_servicenow_ticket
)

# 1. Data Analyst Sub-Agent
data_analyst_agent = Agent(
    name="data_analyst_agent",
    model=settings.adk_model_name,
    instruction=DATA_ANALYST_INSTRUCTIONS,
    tools=[execute_analytics_sql]
)

# 2. ServiceNow Sub-Agent
servicenow_agent = Agent(
    name="servicenow_agent",
    model=settings.adk_model_name,
    instruction=SERVICENOW_INSTRUCTIONS,
    tools=[
        get_servicenow_ticket_details,
        create_servicenow_ticket,
        search_servicenow_incidents,
        update_servicenow_ticket
    ]
)

# 3. Coordinator / Root Agent
# This agent orchestrates between the sub-agents
agent = Agent(
    name="support_chatbot",
    model=settings.adk_model_name,
    instruction=COORDINATOR_INSTRUCTIONS,
    sub_agents=[data_analyst_agent, servicenow_agent]
)

# Export for ADK web runner discovery
root_agent = agent

def build_agent() -> Agent:
    return agent