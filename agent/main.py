from agents import Agent, Runner
from agent.model import mimo_model, doubao_model
from tools import all_tools
import os


def load_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def create_generator_agent() -> Agent:
    """创建测试用例生成 Agent（使用 mimo）"""
    system_prompt = load_prompt("generator.md")
    return Agent(
        name="TestGenerator",
        instructions=system_prompt,
        model=mimo_model,
        tools=[],
    )


def create_reviewer_agent() -> Agent:
    """创建测试用例审核 Agent（使用 doubao）"""
    system_prompt = load_prompt("reviewer.md")
    model = doubao_model if doubao_model else mimo_model
    return Agent(
        name="TestReviewer",
        instructions=system_prompt,
        model=model,
        tools=[],
    )


def generate_and_review(task: str, max_rounds: int = 3) -> str:
    """生成 + 审核闭环工作流"""
    generator = create_generator_agent()
    reviewer = create_reviewer_agent()

    current_yaml = None

    for round_num in range(max_rounds):
        print(f"\n{'='*50}")
        print(f"第 {round_num + 1} 轮")
        print(f"{'='*50}")

        # 1. 生成/修改用例
        if round_num == 0:
            gen_task = f"请根据以下需求生成 YAML 格式的测试用例：\n\n{task}"
        else:
            gen_task = f"请根据审核反馈修改测试用例。\n\n原始需求：{task}\n\n上一版 YAML：\n{current_yaml}\n\n审核反馈：\n{review_feedback}"

        print(f"\n[Generator] 正在生成...")
        gen_result = Runner.run_sync(generator, gen_task)
        current_yaml = gen_result.final_output
        print(f"[Generator] 生成完成")

        # 2. 审核用例
        print(f"\n[Reviewer] 正在审核...")
        review_task = f"请审核以下 YAML 测试用例：\n\n{current_yaml}"
        review_result = Runner.run_sync(reviewer, review_task)
        review_feedback = review_result.final_output
        print(f"[Reviewer] 审核完成")

        # 3. 检查是否通过
        if "通过" in review_feedback or "PASS" in review_feedback.upper():
            print(f"\n✅ 审核通过！")
            return current_yaml
        else:
            print(f"\n❌ 审核未通过，继续修改...")
            print(f"反馈: {review_feedback[:200]}...")

    print(f"\n达到最大轮数 {max_rounds}，返回最后一版")
    return current_yaml
