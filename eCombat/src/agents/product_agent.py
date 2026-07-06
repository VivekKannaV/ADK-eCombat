
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from eCombat.src.config.settings import _PRODUCT_MODEL

_INSTRUCTION = (Path(__file__).parent / "instructions" / "product_assistant.txt").read_text().strip()

product_agent = Agent(
    model=LiteLlm(model=_PRODUCT_MODEL),
    name='product_agent',
    description='A helpful assistant for product-related questions.',
    instruction=_INSTRUCTION,
)
