
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from eCombat.src.config.settings import SUPPORT_MODEL
from eCombat.src.agents.logging_agent import LoggingAgent

_INSTRUCTION = (Path(__file__).parent / "instructions" / "formal_assistant.txt").read_text().strip()

_base_support_agent = Agent(
    model=LiteLlm(model=SUPPORT_MODEL),
    name='support_agent',
    description='A helpful assistant for after sales support questions.',
    instruction=_INSTRUCTION,
)

support_agent = LoggingAgent(_base_support_agent)
