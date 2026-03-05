from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset
from pydantic_settings import BaseSettings


# Settings to start with
class Settings(BaseSettings):
    MISTRAL_AI_API_KEY: str
    LLM_MODEL: str
    LLM_URL: str | None = None


load_dotenv()
_SETTINGS = Settings()


# ====================================================================================
#   Model configuration
# ====================================================================================

model_name = _SETTINGS.LLM_MODEL.lower()

if model_name.startswith("mistralai/"):
    from pydantic_ai.models.mistral import MistralModel
    from pydantic_ai.providers.mistral import MistralProvider

    if _SETTINGS.LLM_URL:
        provider = MistralProvider(
            base_url=_SETTINGS.LLM_URL,
            api_key=_SETTINGS.MISTRAL_AI_API_KEY,
        )
        llm_model = _SETTINGS.LLM_MODEL
    else:
        provider = MistralProvider(api_key=_SETTINGS.MISTRAL_AI_API_KEY)
        llm_model = _SETTINGS.LLM_MODEL.replace("mistralai/", "")

    model = MistralModel(llm_model, provider=provider)

else:
    raise EnvironmentError(f"Model not supported ({model_name})")

if False:
    mcp_tool = FastMCPToolset(Client(str(Path(__file__).parent / "server_example.py")))
else:
    mcp_tool = FastMCPToolset("http://127.0.0.1:8000/mcp")
agent = Agent(
    model,
    toolsets=[mcp_tool],
    system_prompt=(
        "You MUST use the available tools to answer questions. "
        "Never answer from memory. Always call the relevant tool first."
    ),
    instructions="""Be concise, reply with short sentences.""",
)


agent.to_cli_sync()
