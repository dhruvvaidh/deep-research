from dataclasses import dataclass, field
from datetime import datetime
import os

ENV_VARS = {
    "anthropic":   "ANTHROPIC_API_KEY",
    "google":      "GOOGLE_API_KEY",
    "openai":      "OPENAI_API_KEY",
    "huggingface": "HUGGINGFACEHUB_API_TOKEN",
}

class LLMAuthenticationError(Exception):
    """
    Raised when authentication fails for an LLM provider.
    Wraps the provider-native exception with structured context.
    """

    def __init__(
        self,
        provider: str,
        env_var: str,
        reason: str,
        original_exception: Exception = None,
    ):
        self.provider = provider
        self.env_var = env_var
        self.reason = reason
        self.original_exception = original_exception
        self.timestamp = datetime.now().isoformat()

        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [
            f"[LLMAuthenticationError]",
            f"  Provider  : {self.provider}",
            f"  Env Var   : {self.env_var}",
            f"  Reason    : {self.reason}",
            f"  Timestamp : {self.timestamp}",
        ]
        if self.original_exception:
            lines.append(f"  Caused by : {type(self.original_exception).__name__}: {self.original_exception}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"LLMAuthenticationError("
            f"provider={self.provider!r}, "
            f"env_var={self.env_var!r}, "
            f"reason={self.reason!r})"
        )


def _get_api_key(provider: str) -> str:
    env_var = ENV_VARS[provider]
    key = os.getenv(env_var, "").strip()
    if not key:
        raise LLMAuthenticationError(
            provider=provider,
            env_var=env_var,
            reason=f"Environment variable '{env_var}' is not set or is empty.",
        )
    return key


def _verify_api_key(provider: str, api_key: str) -> None:
    match provider:

        case "anthropic":
            import anthropic
            try:
                anthropic.Anthropic(api_key=api_key).models.list(limit=1)
            except anthropic.AuthenticationError as e:
                raise LLMAuthenticationError(
                    provider="Anthropic",
                    env_var=ENV_VARS[provider],
                    reason="API key was rejected by Anthropic.",
                    original_exception=e,
                ) from e

        case "google":
            from google.genai import Client
            client = Client(api_key=api_key)
            try:
                client.models.list()
            except:
                raise LLMAuthenticationError(
                    provider="Google",
                    env_var=ENV_VARS[provider],
                    reason="API key was rejected by Google Generative AI.",
                    original_exception=e,
                )

        case "openai":
            from openai import OpenAI, AuthenticationError
            try:
                OpenAI(api_key=api_key).models.list()
            except AuthenticationError as e:
                raise LLMAuthenticationError(
                    provider="OpenAI",
                    env_var=ENV_VARS[provider],
                    reason="API key was rejected by OpenAI.",
                    original_exception=e,
                ) from e

        case "huggingface":
            from huggingface_hub import HfApi, errors
            try:
                HfApi(token=api_key).whoami()
            except errors.LocalTokenNotFoundError as e:
                raise LLMAuthenticationError(
                    provider="HuggingFace",
                    env_var=ENV_VARS[provider],
                    reason="Token was rejected by HuggingFace Hub.",
                    original_exception=e,
                ) from e