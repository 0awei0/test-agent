import os
import json
from agents import function_tool
from core.locust_runner import (
    load_perf_yaml,
    generate_locustfile,
    run_locust_test,
    run_step_load_test,
    format_perf_report,
    format_step_load_report,
)


@function_tool
def run_performance_test(
    yaml_path: str = "perf/scenarios/step_load.yaml",
    mode: str = "step_load",
) -> str:
    """执行性能测试，支持固定并发和阶梯加压两种模式。

    Args:
        yaml_path: 压测场景 YAML 文件路径
        mode: 测试模式 - "fixed"(固定并发) 或 "step_load"(阶梯加压找拐点)
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(project_root, yaml_path)

        if not os.path.exists(full_path):
            return f"Error: YAML file not found: {yaml_path}"

        config = load_perf_yaml(full_path)
        base_url = config.get("base_url", "")

        locustfile = os.path.join(project_root, "perf", "generated_locustfile.py")
        generate_locustfile(config, locustfile)

        if mode == "step_load":
            stages = config.get("config", {}).get("stages", [])
            if not stages:
                return "Error: step_load 模式需要在 config.stages 中定义阶梯配置"

            result = run_step_load_test(
                locustfile_path=locustfile,
                host=base_url,
                stages=stages,
            )
            return format_step_load_report(result)
        else:
            perf_config = config.get("config", {})
            stats = run_locust_test(
                locustfile_path=locustfile,
                host=base_url,
                users=perf_config.get("users", 10),
                spawn_rate=perf_config.get("spawn_rate", 5),
                run_time=str(perf_config.get("run_time", "30s")),
            )
            return format_perf_report(stats)

    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@function_tool
def design_perf_scenario(
    swagger_path: str = "docs/admin-swagger.json",
    priority_apis: str = "login,query",
) -> str:
    """根据 API 文档设计压测场景，输出 YAML 配置。

    Args:
        swagger_path: Swagger JSON 文件路径
        priority_apis: 重点关注的接口类型，如 login,query,order
    """
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(project_root, swagger_path)

        if not os.path.exists(full_path):
            return f"Error: Swagger file not found: {swagger_path}"

        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        apis = []
        for path, methods in data.get("paths", {}).items():
            for method, detail in methods.items():
                if method in ("get", "post", "put", "delete"):
                    apis.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": detail.get("summary", ""),
                    })

        lines = ["# 建议的压测场景配置:\n"]
        lines.append("高优先级接口（登录/查询）:")
        for api in apis:
            if any(kw in api["path"] for kw in ["login", "list", "page", "status"]):
                lines.append(f"  {api['method']:6s} {api['path']:40s} {api['summary']}")

        lines.append("\n低优先级接口（写操作）:")
        for api in apis:
            if any(kw in api["path"] for kw in ["add", "update", "delete", "save", "submit"]):
                lines.append(f"  {api['method']:6s} {api['path']:40s} {api['summary']}")

        lines.append("\n建议: 先压测查询接口（只读、无副作用），再压测写入接口。")
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
