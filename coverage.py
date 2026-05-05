#!/usr/bin/env python3
"""接口覆盖率分析脚本 - 直接运行"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.coverage import analyze_coverage, format_coverage_report


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    swagger_dir = os.path.join(project_root, "docs")
    yaml_dir = os.path.join(project_root, "testcases")

    swagger_files = []
    for f in os.listdir(swagger_dir):
        if f.endswith(".json") and "swagger" in f.lower():
            swagger_files.append(os.path.join(swagger_dir, f))

    if not swagger_files:
        print("Error: No swagger JSON files found in docs/")
        sys.exit(1)

    print(f"Swagger 文件: {len(swagger_files)} 个")
    for sf in swagger_files:
        print(f"  - {os.path.basename(sf)}")
    print()

    result = analyze_coverage(swagger_files, yaml_dir)
    print(format_coverage_report(result))

    if result["uncovered"]:
        print(f"\n提示: 运行 Agent 自动生成缺失用例:")
        print(f'  python -m agent.main')
        print(f'  > 请为以下接口生成测试用例: ...')


if __name__ == "__main__":
    main()
