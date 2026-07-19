from dotenv import load_dotenv
from oss4climate_app.src.mcp_server import mcp
from pydantic_ai import Agent
from pydantic_ai.toolsets.fastmcp import FastMCPToolset
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Define the following variables in a ".env" file
    MISTRAL_AI_API_KEY: str | None = None
    CLAUDE_API_KEY: str | None = None
    LLM_MODEL: str
    LLM_URL: str | None = None


# ====================================================================================
#   Load model configuration
# ====================================================================================

load_dotenv()
_SETTINGS = Settings()
model_name = _SETTINGS.LLM_MODEL.lower()

# Choose the right model and provider given the user choice
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

elif model_name.startswith("anthropic:"):
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    if _SETTINGS.LLM_URL:
        provider = AnthropicProvider(
            base_url=_SETTINGS.LLM_URL,
            api_key=_SETTINGS.CLAUDE_API_KEY,
        )
        llm_model = _SETTINGS.LLM_MODEL
    else:
        provider = AnthropicProvider(api_key=_SETTINGS.MISTRAL_AI_API_KEY)
        llm_model = _SETTINGS.LLM_MODEL

    model = AnthropicModel(llm_model, provider=provider)

else:
    raise EnvironmentError(f"Model not supported ({model_name})")

# Spin the MCP in the background
mcp_tool = FastMCPToolset(mcp)
# mcp_tool = FastMCPToolset("http://localhost:8080/mcp/sse")
agent = Agent(
    model,
    toolsets=[mcp_tool],
    system_prompt="""
Your are an assistant to discovery of open-source projects in the fields that are of interest to the user.

You MUST use the available tools to answer questions.
Never answer from memory. Always call the relevant tool first.
""",
    instructions="""Be helpful, and frame your answers in a way that makes it easier to
identify the best solution for a developer to build on top of.""",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app=agent.to_web(), port=8082)
