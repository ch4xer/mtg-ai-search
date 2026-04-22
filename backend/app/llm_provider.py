"""OpenAI-compatible chat model provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


@dataclass(frozen=True)
class ChatProviderConfig:
    provider: str
    api_key: str
    base_url: str
    model: str


def get_chat_provider_config() -> ChatProviderConfig:
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

    if provider == "deepseek":
        return ChatProviderConfig(
            provider=provider,
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )

    if provider == "siliconflow":
        return ChatProviderConfig(
            provider=provider,
            api_key=os.getenv("SILICONFLOW_API_KEY", ""),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            model=os.getenv("SILICONFLOW_CHAT_MODEL", os.getenv("SILICONFLOW_MODEL", "Pro/moonshotai/Kimi-K2.5")),
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}")


def is_chat_provider_configured() -> bool:
    return bool(get_chat_provider_config().api_key)


def create_chat_llm(**kwargs) -> ChatOpenAI:
    config = get_chat_provider_config()
    return ChatOpenAI(
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        **kwargs,
    )
