import os
import json
from agents import function_tool
from core.failure_collector import (
    collect_failures_from_allure,
    format_failures_for_agent,
)


@function_tool
def analyze_test_failures(report_dir: str = "reports") -> str:
    """分析测试失败用例，分类原因并给出建议。
    在 pytest 执行完后调用此工具，自动收集失败用例并分析。

    Args:
        report_dir: Allure 报告目录路径
    """
    try:
        failures = collect_failures_from_allure(report_dir)

        if not failures:
            return "所有测试用例通过，没有失败需要分析。"

        formatted = format_failures_for_agent(failures)
        return formatted
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@function_tool
def get_failure_details(test_name: str, report_dir: str = "reports") -> str:
    """获取指定失败用例的详细信息，包括完整的错误日志和堆栈。

    Args:
        test_name: 失败用例名称（支持模糊匹配）
    """
    try:
        failures = collect_failures_from_allure(report_dir)

        matched = [f for f in failures if test_name.lower() in f.get("name", "").lower()]

        if not matched:
            return f"未找到匹配的失败用例: {test_name}"

        results = []
        for f in matched:
            results.append({
                "name": f["name"],
                "status": f["status"],
                "message": f.get("message", "")[:1000],
                "trace": f.get("trace", "")[:2000],
                "duration_ms": f.get("duration", 0),
            })

        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
