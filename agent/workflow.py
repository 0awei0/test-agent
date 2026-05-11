"""
Test Agent Workflow - 每模块独立闭环

流程：
1. Plan Agent     → 分析 API 文档，生成测试计划
2. For each module:
   2.1 Generator  → 生成 YAML 用例
   2.2 Reviewer   → 审核（对照 Swagger）
   2.3 Coverage   → 检查模块覆盖率
   2.4 如果不通过 → 回到 2.1
   2.5 Pytest     → 执行该模块测试
   2.6 Failure    → 分析失败原因
   2.7 如果是用例问题 → 回到 2.1
3. 汇总所有结果
"""

import os
import sys
import json
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

from agent.model import mimo_model, doubao_model
from agent.main import create_generator_agent, create_reviewer_agent, create_failure_analyzer_agent
from agents import Agent, Runner
from core.coverage import load_swagger_apis, analyze_module_coverage, format_coverage_report


# ============================================================
# 工具函数
# ============================================================

def load_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_swagger_summary(doc_path: str) -> str:
    with open(doc_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    apis = []
    for path, methods in data.get("paths", {}).items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                apis.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": detail.get("summary", ""),
                    "tags": detail.get("tags", []),
                })
    return json.dumps(apis, ensure_ascii=False, indent=2)


def save_yaml(content: str, filepath: str) -> bool:
    """保存 YAML 文件，自动修复常见语法问题，返回是否有效"""
    import yaml

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    clean = content.replace("```yaml", "").replace("```", "").strip()

    try:
        yaml.safe_load(clean)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(clean)
        print(f"  ✅ 已保存: {filepath}")
        return True
    except yaml.YAMLError as e:
        # 保存原始内容，但返回 False 表示有语法问题
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(clean)
        print(f"  ⚠️  YAML 语法有问题: {str(e)[:100]}")
        return False


def get_swagger_files(swagger_dir: str = "docs") -> list:
    project_root = os.path.dirname(os.path.dirname(__file__))
    swagger_path = os.path.join(project_root, swagger_dir)
    return [
        os.path.join(swagger_path, f)
        for f in os.listdir(swagger_path)
        if f.endswith(".json") and "swagger" in f.lower()
    ]


# ============================================================
# Step 1: Plan Agent
# ============================================================

def run_plan_agent(swagger_paths: list) -> dict:
    print("\n" + "=" * 60)
    print("📋 Step 1: Plan Agent - 分析 API 文档，生成测试计划")
    print("=" * 60)

    all_apis = []
    for sp in swagger_paths:
        apis = load_swagger_summary(sp)
        all_apis.append(apis)

    api_summary = "\n".join(all_apis)

    planner = Agent(
        name="PlanAgent",
        instructions=load_prompt("planner.md"),
        model=mimo_model,
    )

    task = f"请为以下 API 接口生成测试计划：\n\n{api_summary}"

    print("  [Plan Agent] 正在分析 API 文档...")
    result = Runner.run_sync(planner, task, max_turns=20)
    plan_text = result.final_output

    plan_text = plan_text.replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        start = plan_text.find("{")
        end = plan_text.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(plan_text[start:end])
        else:
            raise ValueError("Plan Agent 输出的不是有效 JSON")

    print(f"  [Plan Agent] 完成！共 {len(plan.get('modules', []))} 个模块")

    plan_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    return plan


# ============================================================
# Step 2: 单模块闭环
# ============================================================

def run_module_pipeline(module: dict, swagger_files: list, module_index: int, total_modules: int) -> dict:
    """单模块完整闭环：生成 → 审核 → 覆盖率 → 执行 → 失败分析"""
    name = module.get("name", f"模块{module_index}")
    apis = module.get("apis", [])
    priority = module.get("priority", "P1")

    print(f"\n{'='*60}")
    print(f"📦 [{module_index}/{total_modules}] 模块: {name} (优先级: {priority})")
    print(f"   接口数: {len(apis)}")
    print(f"{'='*60}")

    generator = create_generator_agent()
    reviewer = create_reviewer_agent()
    project_root = os.path.dirname(os.path.dirname(__file__))
    safe_name = name.replace("/", "_").replace(" ", "_").lower()
    yaml_dir = os.path.join(project_root, "testcases", safe_name)

    # 构建接口列表
    api_list = "\n".join([
        f"- {api['method']} {api['path']} {api.get('summary', '')}"
        for api in apis
    ])

    # ========== 内循环 1: 生成 + 审核 + 覆盖率 ==========
    max_gen_rounds = 1
    current_yaml = None

    for gen_round in range(max_gen_rounds):
        print(f"\n  ┌─ 生成+审核 Round {gen_round + 1}")

        # 生成
        if gen_round == 0:
            gen_task = f"请为{name}模块生成完整测试用例，覆盖以下接口：\n\n{api_list}\n\n要求覆盖所有场景（正常/异常/边界/权限）。"
        else:
            gen_task = f"请根据审核反馈修改测试用例。\n\n模块：{name}\n接口：\n{api_list}\n\n上一版 YAML：\n{current_yaml}\n\n审核反馈：\n{review_feedback}"

        print(f"  │  [Generator] 生成中...")
        gen_result = Runner.run_sync(generator, gen_task, max_turns=20)
        current_yaml = gen_result.final_output

        # 审核
        print(f"  │  [Reviewer] 审核中...")
        review_task = f"请审核以下 YAML 测试用例，对照 Swagger 文档检查接口准确性和场景覆盖度：\n\n{current_yaml}"
        review_result = Runner.run_sync(reviewer, review_task, max_turns=20)
        review_feedback = review_result.final_output

        # 保存 YAML
        filepath = os.path.join(yaml_dir, f"test_{safe_name}.yaml")
        yaml_valid = save_yaml(current_yaml, filepath)

        # 如果 YAML 语法有问题，让 Generator 修复
        if not yaml_valid:
            print(f"  │  [Generator] 修复 YAML 语法...")
            fix_task = f"请修复以下 YAML 的语法错误，保持用例内容不变，只修复格式：\n\n{current_yaml}"
            fix_result = Runner.run_sync(generator, fix_task, max_turns=20)
            current_yaml = fix_result.final_output
            yaml_valid = save_yaml(current_yaml, filepath)

        # 检查审核结果
        if "通过" in review_feedback or "PASS" in review_feedback.upper():
            print(f"  │  ✅ 审核通过")
        else:
            print(f"  │  ❌ 审核未通过")
            print(f"  │  反馈: {review_feedback[:200]}...")
            continue

        # 检查模块覆盖率
        coverage = analyze_module_coverage(apis, os.path.join(project_root, "testcases"))
        print(f"  │  覆盖率: {coverage['coverage_rate']}% ({coverage['covered_apis']}/{coverage['total_apis']})")
        print(f"  │  用例数: P0={coverage['priority_counts']['P0']} P1={coverage['priority_counts']['P1']} P2={coverage['priority_counts']['P2']}")

        if coverage['coverage_rate'] >= 90:
            print(f"  └─ ✅ 覆盖率达标")
            break
        else:
            print(f"  └─ ⚠️ 覆盖率不足，继续补充...")

    # ========== 内循环 2: 执行 + 失败分析 ==========
    max_exec_rounds = 1
    module_result = {
        "module": name,
        "yaml_file": filepath,
        "coverage": coverage,
        "test_result": None,
        "failure_analysis": None,
    }

    for exec_round in range(max_exec_rounds):
        print(f"\n  ┌─ 执行 Round {exec_round + 1}")

        # 执行 pytest
        print(f"  │  [Pytest] 执行 {name} 模块测试...")
        testcases_dir = os.path.join(project_root, "testcases", safe_name)
        cmd = [
            os.path.join(project_root, ".venv", "bin", "pytest"),
            testcases_dir,
            "--alluredir", os.path.join(project_root, "reports"),
            "-v", "--tb=short",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=project_root)
        output = result.stdout + result.stderr
        lines = output.strip().split("\n")
        summary_lines = [l for l in lines if "passed" in l or "failed" in l or "==" in l]
        test_summary = "\n".join(summary_lines[-5:]) if summary_lines else output[-500:]

        # 解析通过率
        import re
        passed_count, failed_count = 0, 0
        for line in lines:
            m = re.search(r"(\d+) passed", line)
            if m:
                passed_count = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed_count = int(m.group(1))
        total_tests = passed_count + failed_count
        pass_rate = round(passed_count / total_tests * 100, 1) if total_tests > 0 else 0

        print(f"  │  {test_summary}")
        print(f"  │  通过率: {passed_count}/{total_tests} ({pass_rate}%)")

        module_result["test_result"] = {
            "returncode": result.returncode,
            "output": test_summary,
            "passed": passed_count,
            "failed": failed_count,
            "total": total_tests,
            "pass_rate": pass_rate,
        }

        # 如果全部通过，不需要失败分析
        if result.returncode == 0:
            print(f"  └─ ✅ 全部通过")
            break

        # 失败分析
        print(f"  │  [Failure Analyzer] 分析失败原因...")
        from core.failure_collector import collect_failures_from_allure, format_failures_for_agent

        failures = collect_failures_from_allure("reports")
        if not failures:
            print(f"  └─ ⚠️ 没有收集到失败信息")
            break

        analyzer = create_failure_analyzer_agent()
        formatted = format_failures_for_agent(failures)
        analysis_task = f"请分析以下测试失败用例，判断是用例问题、代码Bug还是环境问题：\n\n{formatted}"
        analysis_result = Runner.run_sync(analyzer, analysis_task, max_turns=20)
        analysis = analysis_result.final_output

        module_result["failure_analysis"] = analysis
        print(f"  │  分析结果: {analysis[:200]}...")

        # 判断是否是用例问题
        if "用例问题" in analysis or "断言" in analysis or "参数" in analysis:
            print(f"  └─ 🔄 用例问题，反馈给 Generator 重新生成...")
            # 反馈给下一轮生成
            gen_task = f"请根据失败分析修改测试用例。\n\n模块：{name}\n失败分析：\n{analysis}\n\n当前 YAML：\n{current_yaml}"
            gen_result = Runner.run_sync(generator, gen_task, max_turns=20)
            current_yaml = gen_result.final_output
            save_yaml(current_yaml, filepath)
        else:
            print(f"  └─ 🐛 代码 Bug 或环境问题，记录并继续")
            break

    return module_result


# ============================================================
# 主工作流
# ============================================================

def run_workflow(swagger_dir: str = "docs"):
    start_time = time.time()

    print("\n" + "🚀" * 20)
    print("  Test Agent Workflow 开始执行")
    print("  模式: 每模块独立闭环")
    print("🚀" * 20)

    swagger_files = get_swagger_files(swagger_dir)
    if not swagger_files:
        print("❌ 未找到 Swagger JSON 文件")
        return

    print(f"\n找到 {len(swagger_files)} 个 Swagger 文件:")
    for sf in swagger_files:
        print(f"  - {os.path.basename(sf)}")

    # Step 1: Plan
    plan = run_plan_agent(swagger_files)
    modules = plan.get("modules", [])
    execution_order = plan.get("execution_order", [])
    if execution_order:
        order_map = {name: i for i, name in enumerate(execution_order)}
        modules.sort(key=lambda m: order_map.get(m.get("name", ""), 999))

    # Step 2: 逐模块执行闭环
    all_results = []
    for i, module in enumerate(modules, 1):
        result = run_module_pipeline(module, swagger_files, i, len(modules))
        all_results.append(result)

    # Step 3: 汇总结果
    print("\n" + "=" * 60)
    print("📊 最终汇总报告")
    print("=" * 60)

    total_apis = 0
    covered_apis = 0
    total_cases = 0
    total_passed = 0
    total_failed = 0
    passed_modules = 0
    failed_modules = 0

    for r in all_results:
        cov = r.get("coverage", {})
        total_apis += cov.get("total_apis", 0)
        covered_apis += cov.get("covered_apis", 0)
        total_cases += cov.get("total_cases", 0)

        test = r.get("test_result", {})
        if test and test.get("returncode") == 0:
            passed_modules += 1
        else:
            failed_modules += 1

        status = "✅" if test and test.get("returncode") == 0 else "❌"
        cov_rate = cov.get("coverage_rate", 0)
        test_passed = test.get("passed", 0) if test else 0
        test_total = test.get("total", 0) if test else 0
        test_pass_rate = test.get("pass_rate", 0) if test else 0
        total_passed += test_passed
        total_failed += test.get("failed", 0) if test else 0
        print(f"  {status} {r['module']:20s} 覆盖率:{cov_rate:5.1f}%  通过率:{test_passed}/{test_total} ({test_pass_rate}%)")

    overall_rate = round(covered_apis / total_apis * 100, 1) if total_apis > 0 else 0
    overall_pass_rate = round(total_passed / (total_passed + total_failed) * 100, 1) if (total_passed + total_failed) > 0 else 0
    elapsed = time.time() - start_time

    print(f"\n  总接口:     {total_apis}")
    print(f"  已覆盖:     {covered_apis}")
    print(f"  总用例:     {total_cases}")
    print(f"  总覆盖率:   {overall_rate}%")
    print(f"  总通过数:   {total_passed}")
    print(f"  总失败数:   {total_failed}")
    print(f"  总通过率:   {overall_pass_rate}%")
    print(f"  通过模块:   {passed_modules}/{len(all_results)}")
    print(f"  失败模块:   {failed_modules}/{len(all_results)}")
    print(f"  总耗时:     {elapsed:.1f} 秒")
    print("=" * 60)

    return all_results


if __name__ == "__main__":
    run_workflow()
