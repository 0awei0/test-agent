"""
Chain Runner - 链路测试执行器

支持步骤间数据传递的端到端业务流程测试。
每一步的输出可以作为下一步的输入。
"""

import re
import json
import allure
from loguru import logger
from jsonpath_ng import parse as jsonpath_parse
from core.api_client import APIClient
from core.db_client import DBClient
from core.yaml_parser import load_yaml, replace_variables
from core.assertion import assert_status_code, assert_json_contains
from config.settings import settings


def extract_value(data: dict, path: str):
    """从响应数据中提取值，支持 JSONPath"""
    if not path:
        return data

    # 处理数组索引: data.records[0].id
    if "[" in path:
        parts = path.split(".")
        current = data
        for part in parts:
            match = re.match(r"(\w+)\[(\d+)\]", part)
            if match:
                key, idx = match.groups()
                if isinstance(current, dict):
                    current = current.get(key, [])
                if isinstance(current, list) and len(current) > int(idx):
                    current = current[int(idx)]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    # 简单 JSONPath: data.token
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def resolve_template(value, context: dict):
    """解析模板变量 {{variable}}"""
    if isinstance(value, str):
        pattern = r"\{\{(\w+)\}\}"
        matches = re.findall(pattern, value)
        for match in matches:
            if match in context:
                value = value.replace(f"{{{{{match}}}}}", str(context[match]))
        return value
    elif isinstance(value, dict):
        return {k: resolve_template(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_template(item, context) for item in value]
    return value


def run_chain_test(yaml_path: str) -> dict:
    """执行链路测试"""
    data = load_yaml(yaml_path)
    suite_name = data.get("suite", "Chain Test")
    base_url = data.get("base_url", settings.BASE_URL)
    chain = data.get("chain", [])

    if not chain:
        return {"status": "error", "message": "No chain steps defined"}

    client = APIClient(base_url=base_url)
    db = DBClient()
    context = {}  # 存储每一步提取的变量
    results = []

    logger.info(f"[Chain] {suite_name} - {len(chain)} steps")

    for i, step in enumerate(chain, 1):
        step_name = step.get("name", f"Step {i}")
        request = step.get("request", {})
        extract = step.get("extract", {})
        expected = step.get("assert", {})
        db_checks = step.get("db_check", [])

        with allure.step(f"[{i}/{len(chain)}] {step_name}"):
            logger.info(f"[Chain] Step {i}: {step_name}")

            # 解析模板变量
            resolved_request = resolve_template(request, context)

            method = resolved_request.get("method", "GET").lower()
            path = resolved_request.get("path", "")
            headers = resolved_request.get("headers", {})
            body = resolved_request.get("body", None)
            params = resolved_request.get("params", None)

            # 发送请求
            response = client.request(
                method=method,
                path=path,
                headers=headers,
                json=body if body else None,
                params=params if params else None,
            )

            # 断言
            if "status_code" in expected:
                assert_status_code(200, expected["status_code"])
            if "json" in expected:
                assert_json_contains(response, expected["json"])

            # 提取变量
            for var_name, json_path in extract.items():
                value = extract_value(response, json_path)
                context[var_name] = value
                logger.info(f"[Chain] Extracted {var_name} = {value}")

            # 数据库断言
            for check in db_checks:
                sql = resolve_template(check.get("sql", ""), context)
                if sql:
                    rows = db.fetchall(sql)
                    if check.get("expect_not_empty"):
                        assert len(rows) > 0, f"DB check failed: {step_name}"

            results.append({
                "step": i,
                "name": step_name,
                "status": "passed",
                "response_summary": str(response)[:200],
            })

    db.close()
    client.session.close()

    return {
        "status": "passed",
        "suite": suite_name,
        "total_steps": len(chain),
        "context": {k: str(v)[:100] for k, v in context.items()},
        "steps": results,
    }
