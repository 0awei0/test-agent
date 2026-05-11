import json
import os
import glob
from loguru import logger


def load_swagger_apis(doc_path: str) -> list:
    """从 Swagger JSON 提取所有接口列表"""
    with open(doc_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    apis = []
    paths = data.get("paths", {})
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                apis.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": detail.get("summary", ""),
                    "tags": detail.get("tags", []),
                    "module": detail.get("tags", ["未分类"])[0] if detail.get("tags") else "未分类",
                })
    return apis


def load_yaml_testcases(yaml_dir: str) -> list:
    """扫描所有 YAML 文件，提取已覆盖的接口"""
    covered = []
    yaml_files = glob.glob(os.path.join(yaml_dir, "**", "*.yaml"), recursive=True)
    yaml_files.extend(glob.glob(os.path.join(yaml_dir, "**", "*.yml"), recursive=True))

    for yf in yaml_files:
        try:
            import yaml
            with open(yf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            suite = data.get("suite", os.path.basename(yf))
            cases = data.get("cases", [])

            for case in cases:
                req = case.get("request", {})
                path = req.get("path", "")
                method = req.get("method", "GET").upper()
                name = case.get("name", "")
                priority = case.get("priority", "")

                if path:
                    covered.append({
                        "file": os.path.relpath(yf, yaml_dir),
                        "suite": suite,
                        "case_name": name,
                        "priority": priority,
                        "path": path,
                        "method": method,
                    })
        except Exception as e:
            logger.warning(f"Failed to parse {yf}: {e}")

    return covered


def match_api_to_cases(api: dict, covered: list) -> list:
    """匹配接口与已覆盖的用例"""
    api_path = api["path"]
    api_method = api["method"]

    matched = []
    for case in covered:
        case_path = case["path"]
        case_method = case["method"]

        if case_method == api_method:
            if case_path == api_path:
                matched.append(case)
            elif _path_matches(api_path, case_path):
                matched.append(case)

    return matched


def _path_matches(swagger_path: str, case_path: str) -> bool:
    """路径模糊匹配，处理 {id} 等参数和 query 参数"""
    # 去掉 query 参数
    case_path = case_path.split("?")[0]

    swagger_parts = swagger_path.strip("/").split("/")
    case_parts = case_path.strip("/").split("/")

    if len(swagger_parts) != len(case_parts):
        # 尝试前缀匹配（如 /admin/category 匹配 /admin/category/list）
        if len(case_parts) > len(swagger_parts):
            return case_path.startswith(swagger_path.split("?")[0])
        return False

    for sp, cp in zip(swagger_parts, case_parts):
        if sp.startswith("{") and sp.endswith("}"):
            continue
        if sp != cp:
            return False

    return True


def analyze_coverage(swagger_paths: list, yaml_dir: str) -> dict:
    """分析接口覆盖率"""
    all_apis = []
    for sp in swagger_paths:
        apis = load_swagger_apis(sp)
        all_apis.extend(apis)

    covered_cases = load_yaml_testcases(yaml_dir)

    covered_apis = []
    uncovered_apis = []

    for api in all_apis:
        matched = match_api_to_cases(api, covered_cases)
        if matched:
            api["cases"] = matched
            api["case_count"] = len(matched)
            covered_apis.append(api)
        else:
            api["cases"] = []
            api["case_count"] = 0
            uncovered_apis.append(api)

    total = len(all_apis)
    covered_count = len(covered_apis)
    coverage_rate = (covered_count / total * 100) if total > 0 else 0

    modules = {}
    for api in all_apis:
        mod = api["module"]
        if mod not in modules:
            modules[mod] = {"total": 0, "covered": 0, "apis": []}
        modules[mod]["total"] += 1
        if api in covered_apis:
            modules[mod]["covered"] += 1
        modules[mod]["apis"].append(api)

    for mod in modules:
        t = modules[mod]["total"]
        c = modules[mod]["covered"]
        modules[mod]["rate"] = round(c / t * 100, 1) if t > 0 else 0

    return {
        "summary": {
            "total_apis": total,
            "covered_apis": covered_count,
            "uncovered_apis": len(uncovered_apis),
            "total_cases": len(covered_cases),
            "coverage_rate": round(coverage_rate, 1),
        },
        "covered": covered_apis,
        "uncovered": uncovered_apis,
        "modules": modules,
    }


def analyze_module_coverage(apis: list, yaml_dir: str) -> dict:
    """分析单个模块的覆盖率"""
    covered_cases = load_yaml_testcases(yaml_dir)

    covered_apis = []
    uncovered_apis = []

    for api in apis:
        matched = match_api_to_cases(api, covered_cases)
        if matched:
            api["cases"] = matched
            api["case_count"] = len(matched)
            covered_apis.append(api)
        else:
            api["cases"] = []
            api["case_count"] = 0
            uncovered_apis.append(api)

    total = len(apis)
    covered_count = len(covered_apis)
    coverage_rate = (covered_count / total * 100) if total > 0 else 0

    # 统计用例优先级分布
    priority_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "other": 0}
    for case in covered_cases:
        priority = case.get("priority", "other")
        if priority in priority_counts:
            priority_counts[priority] += 1
        else:
            priority_counts["other"] += 1

    return {
        "total_apis": total,
        "covered_apis": covered_count,
        "uncovered_apis": len(uncovered_apis),
        "total_cases": len(covered_cases),
        "coverage_rate": round(coverage_rate, 1),
        "priority_counts": priority_counts,
        "covered": covered_apis,
        "uncovered": uncovered_apis,
    }


def format_coverage_report(result: dict) -> str:
    """格式化覆盖率报告"""
    s = result["summary"]
    lines = []
    lines.append("=" * 60)
    lines.append("接口覆盖率报告")
    lines.append("=" * 60)
    lines.append(f"总接口数:   {s['total_apis']}")
    lines.append(f"已覆盖:     {s['covered_apis']}")
    lines.append(f"未覆盖:     {s['uncovered_apis']}")
    lines.append(f"测试用例数: {s['total_cases']}")
    lines.append(f"覆盖率:     {s['coverage_rate']}%")
    lines.append("")

    lines.append("-" * 60)
    lines.append("模块覆盖率:")
    lines.append("-" * 60)
    for mod, info in sorted(result["modules"].items()):
        bar_len = int(info["rate"] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  {mod:20s} {bar} {info['rate']:5.1f}% ({info['covered']}/{info['total']})")
    lines.append("")

    if result["uncovered"]:
        lines.append("-" * 60)
        lines.append(f"未覆盖接口 ({len(result['uncovered'])} 个):")
        lines.append("-" * 60)
        for api in result["uncovered"]:
            lines.append(f"  {api['method']:6s} {api['path']:40s} {api['summary']}")
        lines.append("")

    if result["covered"]:
        lines.append("-" * 60)
        lines.append(f"已覆盖接口 ({len(result['covered'])} 个):")
        lines.append("-" * 60)
        for api in result["covered"]:
            lines.append(f"  {api['method']:6s} {api['path']:40s} ({api['case_count']} 个用例)")

    return "\n".join(lines)
