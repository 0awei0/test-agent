"""
Locust Runner - YAML 驱动的性能测试

支持：
1. 固定并发压测
2. 阶梯加压压测（找到性能拐点）
"""

import os
import json
import yaml
import subprocess
import csv
from loguru import logger
from config.settings import settings


def load_perf_yaml(yaml_path: str) -> dict:
    """加载压测 YAML 配置"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_locustfile(config: dict, output_path: str):
    """根据 YAML 配置生成 locustfile.py，支持动态 token 获取"""
    base_url = config.get("base_url", settings.BASE_URL)
    scenarios = config.get("scenarios", [])
    login_config = config.get("login", {})

    login_enabled = login_config.get("enabled", False)
    login_method = login_config.get("method", "POST").lower()
    login_path = login_config.get("path", "")
    login_headers = login_config.get("headers", {})
    login_body = login_config.get("body", {})
    token_field = login_config.get("token_field", "data.token")

    tasks_code = []

    for i, scenario in enumerate(scenarios):
        weight = scenario.get("weight", 1)
        tasks = scenario.get("tasks", [])
        use_login = scenario.get("use_login", True)
        func_name = f"task_{i}"

        task_lines = []
        task_lines.append(f"    @task({weight})")
        task_lines.append(f"    def {func_name}(self):")
        task_lines.append(f'        """{scenario.get("name", f"Scenario {i}")}"""')

        for task in tasks:
            method = task.get("method", "GET").lower()
            path = task.get("path", "")
            name = task.get("name", path)
            body = task.get("body", None)
            params = task.get("params", None)

            task_lines.append(f"        # {name}")
            task_lines.append(f"        headers = {{}}")
            if use_login and login_enabled:
                task_lines.append(f"        if self.token:")
                task_lines.append(f'            headers["token"] = self.token')
            task_lines.append(f'        with self.client.{method}(')
            task_lines.append(f'            "{path}",')

            if body:
                task_lines.append(f"            json={json.dumps(body, ensure_ascii=False)},")
            if params:
                task_lines.append(f"            params={json.dumps(params)},")

            task_lines.append(f"            headers=headers,")
            task_lines.append(f'            name="{name}",')
            task_lines.append(f"            catch_response=True")
            task_lines.append(f"        ) as response:")
            task_lines.append(f"            if response.status_code != 200:")
            task_lines.append(f'                response.failure(f"Status code: {{response.status_code}}")')
            task_lines.append(f"")

        tasks_code.append("\n".join(task_lines))

    on_start_code = ""
    if login_enabled and login_path:
        on_start_code = f'''
    def on_start(self):
        """登录获取 token"""
        try:
            response = self.client.{login_method}(
                "{login_path}",
                json={json.dumps(login_body, ensure_ascii=False)},
                headers={json.dumps(login_headers)},
                name="登录获取Token",
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data
                for key in "{token_field}".split("."):
                    if isinstance(self.token, dict):
                        self.token = self.token.get(key)
                    else:
                        self.token = None
                        break
                if not self.token:
                    self.token = None
            else:
                self.token = None
        except Exception as e:
            self.token = None
'''

    locustfile = f'''"""
Auto-generated locustfile from YAML config
Dynamic token acquisition enabled: {login_enabled}
"""

from locust import HttpUser, task, between


class TestUser(HttpUser):
    wait_time = between(0.5, 2)
    host = "{base_url}"
    token = None
{on_start_code}
{chr(10).join(tasks_code)}
'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(locustfile)

    logger.info(f"[Locust] Generated locustfile: {output_path}")
    return output_path


def run_locust_test(
    locustfile_path: str,
    host: str,
    users: int = 10,
    spawn_rate: int = 5,
    run_time: str = "30s",
    output_dir: str = "reports/perf",
    csv_prefix: str = "result",
) -> dict:
    """执行单次 locust 压测"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_full = os.path.join(project_root, output_dir)
    os.makedirs(output_full, exist_ok=True)

    csv_path = os.path.join(output_full, csv_prefix)

    cmd = [
        "locust",
        "-f", locustfile_path,
        "--host", host,
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", run_time,
        "--headless",
        "--csv", csv_path,
        "--only-summary",
    ]

    logger.info(f"[Locust] Running: {users} users, {run_time}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=run_time_to_seconds(run_time) + 30,
        cwd=project_root,
    )

    output = result.stdout + result.stderr

    stats = parse_locust_csv(csv_path)
    stats["raw_output"] = output[-2000:]
    stats["config"] = {"users": users, "run_time": run_time}

    return stats


def run_step_load_test(
    locustfile_path: str,
    host: str,
    stages: list,
    output_dir: str = "reports/perf",
) -> dict:
    """阶梯加压压测

    Args:
        stages: [{"users": 10, "run_time": "30s"}, {"users": 20, "run_time": "30s"}, ...]
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_full = os.path.join(project_root, output_dir)
    os.makedirs(output_full, exist_ok=True)

    results = []

    for i, stage in enumerate(stages):
        users = stage.get("users", 10)
        run_time = stage.get("run_time", "30s")
        spawn_rate = stage.get("spawn_rate", min(users, 5))

        print(f"\n  阶段 {i+1}/{len(stages)}: {users} 并发, {run_time}")

        stats = run_locust_test(
            locustfile_path=locustfile_path,
            host=host,
            users=users,
            spawn_rate=spawn_rate,
            run_time=run_time,
            output_dir=output_dir,
            csv_prefix=f"stage_{i+1}",
        )

        total = stats.get("total", {})
        rps = total.get("rps", 0)
        avg_rt = total.get("avg_response_time", 0)
        p95 = total.get("p95", 0)
        error_rate = (total.get("failures", 0) / max(total.get("requests", 1), 1)) * 100

        results.append({
            "stage": i + 1,
            "users": users,
            "run_time": run_time,
            "rps": round(rps, 2),
            "avg_response_time": round(avg_rt, 2),
            "p95": round(p95, 2),
            "error_rate": round(error_rate, 2),
            "requests": total.get("requests", 0),
            "failures": total.get("failures", 0),
        })

        print(f"    QPS: {rps:.2f}, 平均: {avg_rt:.2f}ms, P95: {p95:.2f}ms, 错误率: {error_rate:.2f}%")

    # 分析拐点
    inflection = analyze_inflection(results)

    return {
        "stages": results,
        "inflection": inflection,
    }


def analyze_inflection(results: list) -> dict:
    """分析性能拐点

    拐点判定条件（满足任一）：
    1. P95 响应时间超过 500ms
    2. 错误率超过 5%
    3. QPS 不再增长或下降
    """
    if len(results) < 2:
        return {"found": False, "reason": "数据点不足"}

    inflection_point = None
    max_qps = 0
    max_qps_stage = 0

    for i, r in enumerate(results):
        # 检查响应时间
        if r["p95"] > 500:
            inflection_point = {
                "stage": r["stage"],
                "users": r["users"],
                "reason": f"P95 响应时间 {r['p95']:.0f}ms 超过 500ms",
                "metric": "p95",
                "value": r["p95"],
            }
            break

        # 检查错误率
        if r["error_rate"] > 5:
            inflection_point = {
                "stage": r["stage"],
                "users": r["users"],
                "reason": f"错误率 {r['error_rate']:.1f}% 超过 5%",
                "metric": "error_rate",
                "value": r["error_rate"],
            }
            break

        # 检查 QPS 增长
        if r["rps"] > max_qps:
            max_qps = r["rps"]
            max_qps_stage = r["stage"]

    # 检查 QPS 是否下降
    if not inflection_point and max_qps_stage < len(results):
        for i in range(max_qps_stage, len(results)):
            if results[i]["rps"] < max_qps * 0.9:  # QPS 下降超过 10%
                inflection_point = {
                    "stage": results[i]["stage"],
                    "users": results[i]["users"],
                    "reason": f"QPS 从 {max_qps:.2f} 下降到 {results[i]['rps']:.2f}",
                    "metric": "qps",
                    "value": results[i]["rps"],
                }
                break

    if inflection_point:
        return {
            "found": True,
            "point": inflection_point,
            "recommendation": f"建议并发数: {results[max(0, inflection_point['stage']-2)]['users']} 用户",
        }

    return {
        "found": False,
        "reason": "未找到拐点，系统在测试范围内表现稳定",
        "recommendation": f"可以尝试更高并发，当前最大: {results[-1]['users']} 用户",
    }


def format_step_load_report(result: dict) -> str:
    """格式化阶梯加压报告"""
    lines = []
    lines.append("=" * 70)
    lines.append("阶梯加压性能测试报告")
    lines.append("=" * 70)
    lines.append("")

    # 性能曲线表格
    lines.append(f"{'阶段':>4s} {'并发':>6s} {'QPS':>8s} {'平均(ms)':>10s} {'P95(ms)':>10s} {'错误率':>8s} {'状态':>6s}")
    lines.append("-" * 70)

    inflection_stage = result.get("inflection", {}).get("point", {}).get("stage", 999)

    for r in result.get("stages", []):
        status = "⚠️ 拐点" if r["stage"] == inflection_stage else "✅"
        lines.append(
            f"{r['stage']:>4d} {r['users']:>6d} {r['rps']:>8.2f} "
            f"{r['avg_response_time']:>10.2f} {r['p95']:>10.2f} "
            f"{r['error_rate']:>7.2f}% {status:>6s}"
        )

    lines.append("")

    # 拐点分析
    inflection = result.get("inflection", {})
    if inflection.get("found"):
        point = inflection["point"]
        lines.append(f"🔴 性能拐点: 阶段 {point['stage']} ({point['users']} 并发)")
        lines.append(f"   原因: {point['reason']}")
        lines.append(f"   建议: {inflection['recommendation']}")
    else:
        lines.append(f"🟢 {inflection.get('reason', '未找到拐点')}")
        lines.append(f"   建议: {inflection.get('recommendation', '')}")

    return "\n".join(lines)


def run_time_to_seconds(run_time: str) -> int:
    """将 run_time 字符串转换为秒数"""
    run_time = run_time.strip().lower()
    if run_time.endswith("s"):
        return int(run_time[:-1])
    elif run_time.endswith("m"):
        return int(run_time[:-1]) * 60
    elif run_time.endswith("h"):
        return int(run_time[:-1]) * 3600
    return 30


def parse_locust_csv(csv_prefix: str) -> dict:
    """解析 locust CSV 结果"""
    def safe_float(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    stats = {"total": {}, "endpoints": []}

    stats_file = f"{csv_prefix}_stats.csv"
    if not os.path.exists(stats_file):
        return stats

    with open(stats_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            if name == "Aggregated":
                stats["total"] = {
                    "requests": safe_int(row.get("Request Count", 0)),
                    "failures": safe_int(row.get("Failure Count", 0)),
                    "avg_response_time": safe_float(row.get("Average Response Time", 0)),
                    "min_response_time": safe_float(row.get("Min Response Time", 0)),
                    "max_response_time": safe_float(row.get("Max Response Time", 0)),
                    "median_response_time": safe_float(row.get("Median Response Time", 0)),
                    "p95": safe_float(row.get("95%", 0)),
                    "p99": safe_float(row.get("99%", 0)),
                    "rps": safe_float(row.get("Requests/s", 0)),
                    "failures_per_sec": safe_float(row.get("Failures/s", 0)),
                }
            elif name and name != "Name":
                stats["endpoints"].append({
                    "name": name,
                    "method": row.get("Type", ""),
                    "requests": safe_int(row.get("Request Count", 0)),
                    "failures": safe_int(row.get("Failure Count", 0)),
                    "avg_response_time": safe_float(row.get("Average Response Time", 0)),
                    "p95": safe_float(row.get("95%", 0)),
                    "p99": safe_float(row.get("99%", 0)),
                    "rps": safe_float(row.get("Requests/s", 0)),
                })

    return stats


def format_perf_report(stats: dict) -> str:
    """格式化单次压测报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("性能测试报告")
    lines.append("=" * 60)

    total = stats.get("total", {})
    if total:
        requests = total.get("requests", 0)
        failures = total.get("failures", 0)
        error_rate = (failures / requests * 100) if requests > 0 else 0

        lines.append(f"总请求数:     {requests}")
        lines.append(f"失败数:       {failures}")
        lines.append(f"错误率:       {error_rate:.2f}%")
        lines.append(f"QPS:          {total.get('rps', 0):.2f}")
        lines.append(f"平均响应时间:  {total.get('avg_response_time', 0):.2f} ms")
        lines.append(f"P95 响应时间:  {total.get('p95', 0):.2f} ms")
        lines.append(f"P99 响应时间:  {total.get('p99', 0):.2f} ms")
        lines.append("")

    endpoints = stats.get("endpoints", [])
    if endpoints:
        lines.append("-" * 60)
        lines.append("接口级指标:")
        lines.append("-" * 60)
        lines.append(f"{'接口':<30s} {'请求':>6s} {'QPS':>8s} {'平均(ms)':>10s} {'P95(ms)':>10s} {'错误率':>8s}")
        lines.append("-" * 80)
        for ep in endpoints:
            reqs = ep.get("requests", 0)
            fails = ep.get("failures", 0)
            error_rate = (fails / reqs * 100) if reqs > 0 else 0
            lines.append(
                f"{ep['name']:<30s} {reqs:>6d} {ep.get('rps', 0):>8.2f} "
                f"{ep.get('avg_response_time', 0):>10.2f} {ep.get('p95', 0):>10.2f} "
                f"{error_rate:>7.2f}%"
            )

    return "\n".join(lines)
