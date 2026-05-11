"""
失败用例收集器 - 收集 pytest 执行失败的用例信息
"""

import os
import json
import glob
from loguru import logger


def collect_failures_from_allure(report_dir: str = "reports") -> list:
    """从 Allure 报告目录收集失败用例"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_path = os.path.join(project_root, report_dir)

    if not os.path.exists(report_path):
        return []

    failures = []
    result_files = glob.glob(os.path.join(report_path, "*-result.json"))

    for rf in result_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                data = json.load(f)

            status = data.get("status", "")
            if status in ("failed", "broken"):
                status_details = data.get("statusDetails", {})
                failure = {
                    "name": data.get("name", "unknown"),
                    "full_name": data.get("fullName", ""),
                    "status": status,
                    "message": status_details.get("message", ""),
                    "trace": status_details.get("trace", ""),
                    "labels": {l["name"]: l["value"] for l in data.get("labels", [])},
                    "parameters": data.get("parameters", []),
                    "start": data.get("start", 0),
                    "stop": data.get("stop", 0),
                    "duration": data.get("stop", 0) - data.get("start", 0),
                }
                failures.append(failure)
        except Exception as e:
            logger.warning(f"Failed to parse {rf}: {e}")

    return failures


def collect_failures_from_pytest_output(output: str) -> list:
    """从 pytest 输出文本中解析失败用例"""
    failures = []
    lines = output.split("\n")

    in_failure_section = False
    current_failure = None

    for line in lines:
        if "FAILED" in line and "::" in line:
            if current_failure:
                failures.append(current_failure)

            parts = line.strip().split("::")
            current_failure = {
                "name": parts[-1].replace("FAILED", "").strip() if len(parts) > 1 else line.strip(),
                "file": parts[0].strip() if len(parts) > 0 else "",
                "message": "",
                "trace": "",
            }
            in_failure_section = True

        elif in_failure_section and current_failure:
            if line.strip().startswith("E ") or line.strip().startswith("AssertionError"):
                current_failure["message"] += line.strip() + "\n"
            elif "======" in line and "FAILURES" not in line:
                in_failure_section = False

    if current_failure:
        failures.append(current_failure)

    return failures


def format_failures_for_agent(failures: list) -> str:
    """格式化失败信息供 Agent 分析"""
    if not failures:
        return "没有失败的测试用例。"

    lines = [f"共 {len(failures)} 个失败用例：\n"]

    for i, f in enumerate(failures, 1):
        lines.append(f"--- 失败用例 {i} ---")
        lines.append(f"名称: {f.get('name', 'unknown')}")
        lines.append(f"状态: {f.get('status', 'unknown')}")

        if f.get("file"):
            lines.append(f"文件: {f['file']}")

        if f.get("message"):
            msg = f["message"][:500]
            lines.append(f"错误信息:\n{msg}")

        if f.get("trace"):
            trace = f["trace"][:500]
            lines.append(f"堆栈:\n{trace}")

        lines.append("")

    return "\n".join(lines)
