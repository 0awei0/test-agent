import json
import time
import requests
from agents import function_tool
from config.settings import settings


@function_tool
def send_api_request(
    method: str,
    path: str,
    headers: str = "{}",
    body: str = "{}",
) -> str:
    """发送单个 HTTP API 请求，返回响应结果。

    Args:
        method: HTTP 方法 (GET/POST/PUT/DELETE)
        path: API 路径，如 /admin/employee/login
        headers: 请求头 JSON 字符串
        body: 请求体 JSON 字符串
    """
    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            url = f"{settings.BASE_URL}{path}"
            headers_dict = json.loads(headers) if headers and headers != "{}" else {}
            body_dict = json.loads(body) if body and body != "{}" else None

            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers_dict,
                json=body_dict,
                timeout=10,
            )
            return json.dumps(
                {
                    "status_code": response.status_code,
                    "response": response.json() if response.text else {},
                },
                ensure_ascii=False,
                indent=2,
            )
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in headers or body: {str(e)}"
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            if isinstance(e, requests.Timeout):
                return f"Error: Request timed out (10s) after {max_retries+1} attempts: {method} {path}"
            return f"Error: Connection failed after {max_retries+1} attempts: {settings.BASE_URL}{path}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

    return f"Error: {type(last_error).__name__}: {str(last_error)}"
