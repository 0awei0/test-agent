import os

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from config.settings import settings

set_tracing_disabled(True)


def create_mimo_model():
    """创建 mimo 模型，优先使用 token-plan，失败则 fallback"""
    try:
        client = AsyncOpenAI(
            api_key=settings.MIMO_API_KEY,
            base_url=settings.MIMO_BASE_URL,
        )
        return OpenAIChatCompletionsModel(
            model=settings.MIMO_MODEL,
            openai_client=client,
        )
    except Exception:
        if settings.MIMO_FALLBACK_API_KEY:
            client = AsyncOpenAI(
                api_key=settings.MIMO_FALLBACK_API_KEY,
                base_url=settings.MIMO_FALLBACK_BASE_URL,
            )
            return OpenAIChatCompletionsModel(
                model=settings.MIMO_MODEL,
                openai_client=client,
            )
        raise


def create_doubao_model():
    """创建 doubao 模型用于审核"""
    client = AsyncOpenAI(
        api_key=settings.ARK_API_KEY,
        base_url=settings.ARK_BASE_URL,
    )
    return OpenAIChatCompletionsModel(
        model=settings.ARK_MODEL,
        openai_client=client,
    )


mimo_model = create_mimo_model()
doubao_model = create_doubao_model() if settings.ARK_API_KEY else None
