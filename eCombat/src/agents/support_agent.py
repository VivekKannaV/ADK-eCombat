
from pathlib import Path
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

_MODEL = "openrouter/google/gemini-2.5-flash"

_INSTRUCTION = (Path(__file__).parent / "instructions" / "formal_assistant.txt").read_text().strip()

root_agent = Agent(
    model=LiteLlm(model=_MODEL),
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction=_INSTRUCTION,
)
