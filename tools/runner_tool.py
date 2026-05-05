import subprocess
import os
from agents import function_tool


@function_tool
def run_pytest_by_yaml(yaml_path: str = "", markers: str = "") -> str:
    """执行 YAML 格式的测试用例，返回测试结果摘要。

    Args:
        yaml_path: YAML 用例文件路径，为空则执行所有用例
        markers: pytest markers 过滤条件，如 "smoke" 或 "P0"
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = ["pytest"]

        if yaml_path:
            full_path = os.path.join(project_root, yaml_path)
            if not os.path.exists(full_path):
                return f"Error: YAML file not found: {yaml_path}"
            cmd.append(full_path)

        if markers:
            cmd.extend(["-m", markers])

        cmd.extend(["--alluredir=reports", "--clean-alluredir", "-v"])

        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        output = result.stdout + result.stderr
        lines = output.strip().split("\n")

        summary_lines = [l for l in lines if "passed" in l or "failed" in l or "error" in l or "==" in l]
        return "\n".join(summary_lines[-10:]) if summary_lines else output[-1000:]

    except subprocess.TimeoutExpired:
        return "Error: pytest execution timed out (120s limit)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
