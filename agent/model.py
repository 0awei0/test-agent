import os

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from config.settings import settings

set_tracing_disabled(True)


def _validate_api_key(api_key: str, base_url: str) -> bool:
    """验证 API key 是否可用（同步请求）"""
    import requests
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "mimo-v2.5", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=10,
            proxies={"http": None, "https": None},
        )
        return resp.status_code == 200
    except Exception:
        return False


def create_mimo_model():
    """创建 mimo 模型，优先使用 token-plan，401/429 则 fallback"""
    # 先验证主 key
    if settings.MIMO_API_KEY and _validate_api_key(settings.MIMO_API_KEY, settings.MIMO_BASE_URL):
        client = AsyncOpenAI(
            api_key=settings.MIMO_API_KEY,
            base_url=settings.MIMO_BASE_URL,
        )
        return OpenAIChatCompletionsModel(
            model=settings.MIMO_MODEL,
            openai_client=client,
        )

    # 主 key 不可用，使用 fallback
    if settings.MIMO_FALLBACK_API_KEY:
        print(f"[Model] Primary mimo key unavailable, using fallback: {settings.MIMO_FALLBACK_BASE_URL}")
        client = AsyncOpenAI(
            api_key=settings.MIMO_FALLBACK_API_KEY,
            base_url=settings.MIMO_FALLBACK_BASE_URL,
        )
        return OpenAIChatCompletionsModel(
            model=settings.MIMO_MODEL,
            openai_client=client,
        )

    # 都不可用，使用主 key（让运行时报错以便排查）
    client = AsyncOpenAI(
        api_key=settings.MIMO_API_KEY,
        base_url=settings.MIMO_BASE_URL,
    )
    return OpenAIChatCompletionsModel(
        model=settings.MIMO_MODEL,
        openai_client=client,
    )


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
doubao_model = create_doubao_model() if settings.ARK_API_KEY and not settings.ARK_API_KEY.startswith("your_") else None
