import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
from config.settings import settings


class APIClient:
    def __init__(self, base_url: str = None, max_retries: int = 3):
        self.base_url = base_url or settings.BASE_URL
        self.session = requests.Session()
        self.token = None

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def set_token(self, token: str):
        self.token = token
        self.session.headers.update({"token": token})

    def clear_token(self):
        self.token = None
        self.session.headers.pop("token", None)

    def request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        logger.info(f"[API] {method.upper()} {url}")

        if "headers" in kwargs:
            self.session.headers.update(kwargs.pop("headers"))

        kwargs.setdefault("timeout", 10)

        try:
            response = self.session.request(method=method, url=url, **kwargs)
            logger.info(f"[API] Status: {response.status_code}")

            try:
                result = response.json()
                logger.debug(f"[API] Response: {result}")
                return result
            except Exception:
                return {"status_code": response.status_code, "text": response.text}

        except requests.Timeout:
            logger.error(f"[API] Timeout: {method.upper()} {url}")
            return {"error": "timeout", "message": f"Request timed out after {kwargs['timeout']}s"}
        except requests.ConnectionError:
            logger.error(f"[API] Connection error: {url}")
            return {"error": "connection_error", "message": f"Failed to connect to {self.base_url}"}
        except Exception as e:
            logger.error(f"[API] Error: {e}")
            return {"error": type(e).__name__, "message": str(e)}

    def get(self, path: str, **kwargs) -> dict:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> dict:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> dict:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> dict:
        return self.request("DELETE", path, **kwargs)
