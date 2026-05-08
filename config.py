from main import model_provider
from langchain_core.language_models import BaseChatModel
from utils import _get_api_key,_verify_api_key,ENV_VARS

MAX_ITERATIONS = 3

def get_llm(model_provider: str, model_name: str = None, **kwargs) -> BaseChatModel:
    provider = model_provider.lower().replace(" ", "_")

    if provider not in ENV_VARS:
        raise ValueError(
            f"Unknown provider '{model_provider}'. "
            f"Supported: {list(ENV_VARS.keys())}"
        )

    api_key = _get_api_key(provider)
    _verify_api_key(provider, api_key)

    match provider:

        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name or "claude-sonnet-4-20250514",
                api_key=api_key,
                **kwargs
            )

        case "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name or "gemini-2.0-flash",
                google_api_key=api_key,
                **kwargs
            )

        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name or "gpt-4o",
                api_key=api_key,
                **kwargs
            )

        case "huggingface":
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
            endpoint = HuggingFaceEndpoint(
                repo_id=model_name or "mistralai/Mistral-7B-Instruct-v0.3",
                huggingfacehub_api_token=api_key,
                **kwargs
            )
            return ChatHuggingFace(llm=endpoint)
