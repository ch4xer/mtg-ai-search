"""DeepSeek chat model provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)


@dataclass(frozen=True)
class ChatProviderConfig:
    api_key: str
    base_url: str
    model: str


def get_chat_provider_config() -> ChatProviderConfig:
    return ChatProviderConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    )


def is_chat_provider_configured() -> bool:
    return bool(get_chat_provider_config().api_key)


def create_chat_llm(**kwargs) -> ChatOpenAI:
    config = get_chat_provider_config()
    extra_body = dict(kwargs.pop("extra_body", {}) or {})
    extra_body["thinking"] = {"type": "disabled"}
    kwargs["extra_body"] = extra_body

    return ChatOpenAI(
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        **kwargs,
    )
