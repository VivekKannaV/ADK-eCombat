from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from eCombat.src.agents.sales.sales_agent import sales_agent
from eCombat.src.agents.support.support_agent import support_agent
from eCombat.src.agents.logger.logging_agent import LoggingAgent
from eCombat.src.config.settings import SUPPORT_MODEL

_INSTRUCTION = (
    Path(__file__).parent / "instructions" / "ecombat_assistant.txt"
).read_text().strip()

_base_ecombat_agent = Agent(
    model=LiteLlm(model=SUPPORT_MODEL),
    name="ecombat_agent",
    description="Routes ecommerce user requests to the correct specialist agent.",
    instruction=_INSTRUCTION,
    sub_agents=[sales_agent, support_agent],
)

ecombat_agent = LoggingAgent(_base_ecombat_agent)