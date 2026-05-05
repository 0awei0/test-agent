import os
import json
from agents import function_tool
from core.coverage import analyze_coverage, format_coverage_report


@function_tool
def analyze_api_coverage(
    swagger_dir: str = "docs",
    yaml_dir: str = "testcases",
) -> str:
    """分析接口覆盖率：对比 Swagger 文档和已有 YAML 用例，输出覆盖情况。

    Args:
        swagger_dir: Swagger JSON 文件目录，如 docs
        yaml_dir: YAML 测试用例目录，如 testcases
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    swagger_full = os.path.join(project_root, swagger_dir)
    yaml_full = os.path.join(project_root, yaml_dir)

    swagger_files = []
    for f in os.listdir(swagger_full):
        if f.endswith(".json") and "swagger" in f.lower():
            swagger_files.append(os.path.join(swagger_full, f))

    if not swagger_files:
        return f"Error: No swagger JSON files found in {swagger_dir}"

    result = analyze_coverage(swagger_files, yaml_full)
    return format_coverage_report(result)


@function_tool
def get_uncovered_apis(
    swagger_dir: str = "docs",
    yaml_dir: str = "testcases",
) -> str:
    """获取未覆盖的接口清单，用于指导生成新的测试用例。

    Args:
        swagger_dir: Swagger JSON 文件目录
        yaml_dir: YAML 测试用例目录
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    swagger_full = os.path.join(project_root, swagger_dir)
    yaml_full = os.path.join(project_root, yaml_dir)

    swagger_files = []
    for f in os.listdir(swagger_full):
        if f.endswith(".json") and "swagger" in f.lower():
            swagger_files.append(os.path.join(swagger_full, f))

    if not swagger_files:
        return f"Error: No swagger JSON files found in {swagger_dir}"

    result = analyze_coverage(swagger_files, yaml_full)
    uncovered = result["uncovered"]

    if not uncovered:
        return "所有接口均已覆盖！"

    modules = {}
    for api in uncovered:
        mod = api["module"]
        if mod not in modules:
            modules[mod] = []
        modules[mod].append(api)

    lines = [f"共 {len(uncovered)} 个接口未覆盖：\n"]
    for mod, apis in sorted(modules.items()):
        lines.append(f"【{mod}】({len(apis)} 个)")
        for api in apis:
            lines.append(f"  {api['method']:6s} {api['path']:40s} {api['summary']}")
        lines.append("")

    lines.append("建议：请调用 TestGenerator Agent 为这些接口生成测试用例。")
    return "\n".join(lines)
