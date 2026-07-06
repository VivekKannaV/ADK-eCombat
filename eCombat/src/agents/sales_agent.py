
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from eCombat.src.config.settings import _SALES_MODEL

_INSTRUCTION = (Path(__file__).parent / "instructions" / "sales_assistant.txt").read_text().strip()

sales_agent = Agent(
    model=LiteLlm(model=_SALES_MODEL),
    name='sales_agent',
    description='A helpful assistant for sales support questions.',
    instruction=_INSTRUCTION,
)
