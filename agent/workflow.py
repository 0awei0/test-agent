"""
Test Agent Workflow - 自动化测试工作流

流程：
1. Plan Agent    → 分析 API 文档，生成测试计划
2. Generator     → 按模块批量生成测试用例
3. Reviewer      → 审核用例质量
4. Coverage      → 自动检测覆盖率
5. Feedback Loop → 未覆盖接口反馈给 Generator 重新生成
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

from agent.model import mimo_model, doubao_model
from agents import Agent, Runner
from core.coverage import analyze_coverage, format_coverage_report


# ============================================================
# 工具函数
# ============================================================

def load_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_swagger_summary(doc_path: str) -> str:
    """加载 Swagger 文档摘要"""
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


def save_yaml(content: str, filepath: str):
    """保存 YAML 文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    clean = content.replace("```yaml", "").replace("```", "").strip()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(clean)
    print(f"  ✅ 已保存: {filepath}")


# ============================================================
# Step 1: Plan Agent - 生成测试计划
# ============================================================

def run_plan_agent(swagger_paths: list) -> dict:
    """Plan Agent: 分析 API 文档，生成测试计划"""
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
    result = Runner.run_sync(planner, task)
    plan_text = result.final_output

    # 提取 JSON
    plan_text = plan_text.replace("```json", "").replace("```", "").strip()
    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        # 尝试找到 JSON 部分
        start = plan_text.find("{")
        end = plan_text.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(plan_text[start:end])
        else:
            raise ValueError("Plan Agent 输出的不是有效 JSON")

    print(f"  [Plan Agent] 完成！共 {len(plan.get('modules', []))} 个模块")
    print(f"  预估用例数: {plan.get('total_estimated_cases', '未知')}")

    # 保存计划
    plan_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"  计划已保存: {plan_path}")

    return plan


# ============================================================
# Step 2 & 3: Generate + Review - 按模块生成并审核
# ============================================================

def run_generate_and_review(modules: list, max_rounds: int = 2) -> list:
    """按模块批量生成测试用例并审核"""
    print("\n" + "=" * 60)
    print("🔧 Step 2 & 3: Generate + Review - 按模块生成并审核")
    print("=" * 60)

    generator = Agent(
        name="TestGenerator",
        instructions=load_prompt("generator.md"),
        model=mimo_model,
    )

    reviewer = Agent(
        name="TestReviewer",
        instructions=load_prompt("reviewer.md"),
        model=doubao_model if doubao_model else mimo_model,
    )

    results = []
    total = len(modules)

    for i, module in enumerate(modules, 1):
        name = module.get("name", f"模块{i}")
        apis = module.get("apis", [])
        priority = module.get("priority", "P1")

        print(f"\n  [{i}/{total}] {name} (优先级: {priority})")
        print(f"  接口数: {len(apis)}")

        # 构建生成任务
        api_list = "\n".join([
            f"- {api['method']} {api['path']} {api.get('summary', '')}"
            for api in apis
        ])
        gen_task = f"""请为{name}模块生成完整测试用例，覆盖以下接口：

{api_list}

要求：
1. 每个接口至少 3 个用例（正常+异常+边界）
2. 直接输出 YAML，不要有其他文字
3. 用中文命名用例"""

        # 生成 + 审核循环
        for round_num in range(max_rounds):
            print(f"  [Round {round_num + 1}] 生成中...")

            gen_result = Runner.run_sync(generator, gen_task)
            yaml_content = gen_result.final_output

            print(f"  [Round {round_num + 1}] 审核中...")
            review_task = f"请审核以下 YAML 测试用例：\n\n{yaml_content}"
            review_result = Runner.run_sync(reviewer, review_task)
            review_feedback = review_result.final_output

            if "通过" in review_feedback or "PASS" in review_feedback.upper():
                print(f"  [Round {round_num + 1}] ✅ 审核通过")
                break
            else:
                print(f"  [Round {round_num + 1}] ❌ 未通过，继续修改...")
                gen_task = f"请根据反馈修改测试用例。\n\n原始需求：{gen_task}\n\n上一版 YAML：\n{yaml_content}\n\n审核反馈：\n{review_feedback}"

        # 保存文件
        safe_name = name.replace("/", "_").replace(" ", "_").lower()
        filepath = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "testcases", safe_name, f"test_{safe_name}.yaml"
        )
        save_yaml(yaml_content, filepath)

        results.append({
            "module": name,
            "file": filepath,
            "status": "success",
        })

    return results


# ============================================================
# Step 4: Coverage Check - 覆盖率检测
# ============================================================

def run_coverage_check() -> dict:
    """检测接口覆盖率"""
    print("\n" + "=" * 60)
    print("📊 Step 4: Coverage Check - 覆盖率检测")
    print("=" * 60)

    project_root = os.path.dirname(os.path.dirname(__file__))
    swagger_dir = os.path.join(project_root, "docs")
    yaml_dir = os.path.join(project_root, "testcases")

    swagger_files = [
        os.path.join(swagger_dir, f)
        for f in os.listdir(swagger_dir)
        if f.endswith(".json") and "swagger" in f.lower()
    ]

    result = analyze_coverage(swagger_files, yaml_dir)
    print(format_coverage_report(result))

    return result


# ============================================================
# Step 5: Feedback Loop - 补充缺失用例
# ============================================================

def run_feedback_loop(coverage_result: dict, max_rounds: int = 3) -> dict:
    """如果覆盖率未达标，反馈给 Generator 补充"""
    target_rate = 90.0
    current_rate = coverage_result["summary"]["coverage_rate"]

    if current_rate >= target_rate:
        print(f"\n✅ 覆盖率 {current_rate}% 已达标（目标 {target_rate}%），无需补充")
        return coverage_result

    print(f"\n" + "=" * 60)
    print(f"🔄 Step 5: Feedback Loop - 补充缺失用例")
    print(f"当前覆盖率: {current_rate}%, 目标: {target_rate}%")
    print("=" * 60)

    generator = Agent(
        name="TestGenerator",
        instructions=load_prompt("generator.md"),
        model=mimo_model,
    )

    reviewer = Agent(
        name="TestReviewer",
        instructions=load_prompt("reviewer.md"),
        model=doubao_model if doubao_model else mimo_model,
    )

    for round_num in range(max_rounds):
        uncovered = coverage_result["uncovered"]
        if not uncovered:
            print("  所有接口已覆盖！")
            break

        print(f"\n  [Feedback Round {round_num + 1}] 未覆盖接口: {len(uncovered)} 个")

        # 按模块分组
        modules = {}
        for api in uncovered:
            mod = api.get("module", "未分类")
            if mod not in modules:
                modules[mod] = []
            modules[mod].append(api)

        # 逐模块补充
        for mod, apis in modules.items():
            print(f"  补充模块: {mod} ({len(apis)} 个接口)")

            api_list = "\n".join([
                f"- {api['method']} {api['path']} {api.get('summary', '')}"
                for api in apis
            ])

            gen_task = f"请为以下未覆盖接口生成测试用例：\n\n{api_list}\n\n每个接口至少 3 个用例，直接输出 YAML。"

            gen_result = Runner.run_sync(generator, gen_task)
            yaml_content = gen_result.final_output

            # 审核
            review_task = f"请审核以下 YAML 测试用例：\n\n{yaml_content}"
            review_result = Runner.run_sync(reviewer, review_task)

            # 保存到补充文件
            safe_mod = mod.replace("/", "_").replace(" ", "_").lower()
            filepath = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "testcases", safe_mod, f"test_{safe_mod}_extra.yaml"
            )
            save_yaml(yaml_content, filepath)

        # 重新检测覆盖率
        coverage_result = run_coverage_check()
        current_rate = coverage_result["summary"]["coverage_rate"]

        if current_rate >= target_rate:
            print(f"\n✅ 覆盖率 {current_rate}% 已达标！")
            break

    return coverage_result


# ============================================================
# Step 6: Performance Test - 性能测试
# ============================================================

def run_perf_test(perf_yaml: str = "perf/scenarios/core_api.yaml") -> dict:
    """执行性能测试"""
    print("\n" + "=" * 60)
    print("⚡ Step 6: Performance Test - 性能测试")
    print("=" * 60)

    from core.locust_runner import load_perf_yaml, generate_locustfile, run_locust_test, format_perf_report

    project_root = os.path.dirname(os.path.dirname(__file__))
    full_path = os.path.join(project_root, perf_yaml)

    if not os.path.exists(full_path):
        print(f"  ⚠️  压测场景文件不存在: {perf_yaml}，跳过性能测试")
        return {}

    config = load_perf_yaml(full_path)
    base_url = config.get("base_url", "")
    perf_config = config.get("config", {})

    print(f"  目标: {base_url}")
    print(f"  并发: {perf_config.get('users', 10)} 用户")
    print(f"  时长: {perf_config.get('run_time', '30s')}")

    # 生成 locustfile
    locustfile = os.path.join(project_root, "perf", "generated_locustfile.py")
    generate_locustfile(config, locustfile)

    # 执行压测
    print("  [Locust] 正在执行压测...")
    stats = run_locust_test(
        locustfile_path=locustfile,
        host=base_url,
        users=perf_config.get("users", 10),
        spawn_rate=perf_config.get("spawn_rate", 5),
        run_time=str(perf_config.get("run_time", "30s")),
    )

    report = format_perf_report(stats)
    print(report)

    return stats


# ============================================================
# Step 7: Failure Analysis - 失败分析
# ============================================================

def run_failure_analysis() -> str:
    """分析测试失败用例"""
    print("\n" + "=" * 60)
    print("🔍 Step 7: Failure Analysis - 失败分析")
    print("=" * 60)

    from core.failure_collector import collect_failures_from_allure, format_failures_for_agent

    failures = collect_failures_from_allure("reports")

    if not failures:
        print("  ✅ 没有失败的测试用例")
        return ""

    print(f"  发现 {len(failures)} 个失败用例")

    analyzer = Agent(
        name="FailureAnalyzer",
        instructions=load_prompt("failure_analyzer.md"),
        model=mimo_model,
    )

    formatted = format_failures_for_agent(failures)
    task = f"请分析以下测试失败用例，判断是用例问题、代码Bug还是环境问题：\n\n{formatted}"

    result = Runner.run_sync(analyzer, task)
    analysis = result.final_output

    print(f"  分析完成:")
    print(f"  {analysis[:300]}...")

    return analysis


# ============================================================
# 主工作流
# ============================================================

def run_workflow(swagger_dir: str = "docs"):
    """执行完整的测试工作流"""
    start_time = time.time()

    print("\n" + "🚀" * 20)
    print("  Test Agent Workflow 开始执行")
    print("🚀" * 20)

    project_root = os.path.dirname(os.path.dirname(__file__))
    swagger_path = os.path.join(project_root, swagger_dir)

    swagger_files = [
        os.path.join(swagger_path, f)
        for f in os.listdir(swagger_path)
        if f.endswith(".json") and "swagger" in f.lower()
    ]

    if not swagger_files:
        print("❌ 未找到 Swagger JSON 文件")
        return

    print(f"\n找到 {len(swagger_files)} 个 Swagger 文件:")
    for sf in swagger_files:
        print(f"  - {os.path.basename(sf)}")

    # Step 1: Plan
    plan = run_plan_agent(swagger_files)

    # Step 2 & 3: Generate + Review
    modules = plan.get("modules", [])
    execution_order = plan.get("execution_order", [])

    # 按 execution_order 排序
    if execution_order:
        order_map = {name: i for i, name in enumerate(execution_order)}
        modules.sort(key=lambda m: order_map.get(m.get("name", ""), 999))

    generate_results = run_generate_and_review(modules)

    # Step 4: Coverage Check
    coverage_result = run_coverage_check()

    # Step 5: Feedback Loop
    final_result = run_feedback_loop(coverage_result)

    # Step 6: Performance Test
    perf_result = run_perf_test()

    # Step 7: Failure Analysis
    failure_result = run_failure_analysis()

    # 最终报告
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 最终报告")
    print("=" * 60)
    print(f"总接口数:   {final_result['summary']['total_apis']}")
    print(f"已覆盖:     {final_result['summary']['covered_apis']}")
    print(f"测试用例数: {final_result['summary']['total_cases']}")
    print(f"最终覆盖率: {final_result['summary']['coverage_rate']}%")
    if perf_result and perf_result.get("total"):
        total = perf_result["total"]
        print(f"压测 QPS:   {total.get('rps', 0):.2f}")
        print(f"平均响应:   {total.get('avg_response_time', 0):.2f} ms")
        print(f"P95 响应:   {total.get('p95', 0):.2f} ms")
        print(f"错误率:     {total.get('failures', 0) / max(total.get('requests', 1), 1) * 100:.2f}%")
    if failure_result:
        print(f"失败分析:   {failure_result}")
    print(f"总耗时:     {elapsed:.1f} 秒")
    print("=" * 60)

    return final_result


if __name__ == "__main__":
    run_workflow()
