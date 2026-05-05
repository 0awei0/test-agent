import os
import json
from agents import function_tool
from core.locust_runner import (
    load_perf_yaml,
    generate_locustfile,
    run_locust_test,
    format_perf_report,
)


@function_tool
def run_performance_test(
    yaml_path: str = "perf/scenarios/login_and_query.yaml",
    users: int = 10,
    spawn_rate: int = 5,
    run_time: str = "30s",
) -> str:
    """执行 YAML 定义的性能测试场景，返回测试报告。

    Args:
        yaml_path: 压测场景 YAML 文件路径
        users: 并发用户数（默认 10）
        spawn_rate: 每秒启动用户数（默认 5）
        run_time: 运行时长，如 30s、1m、5m（默认 30s）
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(project_root, yaml_path)

    if not os.path.exists(full_path):
        return f"Error: YAML file not found: {yaml_path}"

    config = load_perf_yaml(full_path)

    base_url = config.get("base_url", "")
    config_users = config.get("config", {}).get("users", users)
    config_spawn = config.get("config", {}).get("spawn_rate", spawn_rate)
    config_time = config.get("config", {}).get("run_time", run_time)

    locustfile = os.path.join(project_root, "perf", "generated_locustfile.py")
    generate_locustfile(config, locustfile)

    stats = run_locust_test(
        locustfile_path=locustfile,
        host=base_url,
        users=config_users,
        spawn_rate=config_spawn,
        run_time=str(config_time),
    )

    return format_perf_report(stats)


@function_tool
def design_perf_scenario(
    swagger_path: str = "docs/admin-swagger.json",
    priority_apis: str = "login,query",
) -> str:
    """根据 API 文档设计压测场景，输出 YAML 配置。
    调用此工具来生成压测场景，然后用 run_performance_test 执行。

    Args:
        swagger_path: Swagger JSON 文件路径
        priority_apis: 重点关注的接口类型，如 login,query,order
    """
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
