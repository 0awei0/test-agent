import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # mimo 模型 (生成用)
    MIMO_API_KEY: str = os.getenv("MIMO_API_KEY", "")
    MIMO_BASE_URL: str = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    MIMO_MODEL: str = os.getenv("MIMO_MODEL", "mimo-v2.5")

    # mimo 备用 API
    MIMO_FALLBACK_API_KEY: str = os.getenv("MIMO_FALLBACK_API_KEY", "")
    MIMO_FALLBACK_BASE_URL: str = os.getenv("MIMO_FALLBACK_BASE_URL", "https://api.xiaomimimo.com/v1")

    # doubao 模型 (审核用)
    ARK_API_KEY: str = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    ARK_MODEL: str = os.getenv("ARK_MODEL", "doubao-seed-2-0-pro-260215")

    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "sky_take_out")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # 测试目标
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8080")

    # 报告路径
    REPORT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


settings = Settings()
