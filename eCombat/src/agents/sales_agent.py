
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from eCombat.src.config.settings import SALES_MODEL
from eCombat.src.agents.logging_agent import LoggingAgent

_INSTRUCTION = (Path(__file__).parent / "instructions" / "sales_assistant.txt").read_text().strip()

_base_sales_agent = Agent(
    model=LiteLlm(model=SALES_MODEL),
    name='sales_agent',
    description='A helpful assistant for pre-purchase product and sales questions.',
    instruction=_INSTRUCTION,
)

sales_agent = LoggingAgent(_base_sales_agent)
