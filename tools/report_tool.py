import os
import json
from agents import function_tool


@function_tool
def read_test_report(report_dir: str = "reports") -> str:
    """读取测试报告目录，返回测试结果摘要。

    Args:
        report_dir: 报告目录路径
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_path = os.path.join(project_root, report_dir)

    if not os.path.exists(report_path):
        return "Report directory not found"

    result_files = [f for f in os.listdir(report_path) if f.endswith("-result.json")]

    if not result_files:
        return "No test result files found"

    summary = {"total": 0, "passed": 0, "failed": 0, "broken": 0, "skipped": 0}
    failures = []

    for fname in result_files[:50]:
        fpath = os.path.join(report_path, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                status = data.get("status", "unknown")
                summary["total"] += 1
                if status in summary:
                    summary[status] += 1
                if status in ("failed", "broken"):
                    failures.append({
                        "name": data.get("name", "unknown"),
                        "status": status,
                        "message": data.get("statusMessage", "")[:200],
                    })
        except Exception:
            continue

    report = {"summary": summary}
    if failures:
        report["failures"] = failures[:10]

    return json.dumps(report, ensure_ascii=False, indent=2)
