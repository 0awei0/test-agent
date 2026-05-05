"""
Locust Runner - YAML 驱动的性能测试

将 YAML 压测场景转换为 locustfile.py 并执行，收集结果。
"""

import os
import json
import yaml
import subprocess
import tempfile
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

    # 登录配置
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
                task_lines.append(f'            headers[\"token\"] = self.token')
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

    # 生成 on_start 登录方法
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
                # 解析 token_field 路径 (如 "data.token")
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

    # 生成 locustfile 内容
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
) -> dict:
    """执行 locust 压测"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_full = os.path.join(project_root, output_dir)
    os.makedirs(output_full, exist_ok=True)

    csv_prefix = os.path.join(output_full, "result")

    cmd = [
        "locust",
        "-f", locustfile_path,
        "--host", host,
        "--users", str(users),
        "--spawn-rate", str(spawn_rate),
        "--run-time", run_time,
        "--headless",
        "--csv", csv_prefix,
        "--only-summary",
    ]

    logger.info(f"[Locust] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=run_time_to_seconds(run_time) + 30,
        cwd=project_root,
    )

    output = result.stdout + result.stderr
    logger.info(f"[Locust] Output:\n{output[-500:]}")

    # 解析结果
    stats = parse_locust_csv(csv_prefix)
    stats["raw_output"] = output[-2000:]

    return stats


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

    stats = {
        "total": {},
        "endpoints": [],
    }

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
    """格式化性能测试报告"""
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
        lines.append(f"中位数响应时间: {total.get('median_response_time', 0):.2f} ms")
        lines.append(f"P95 响应时间:  {total.get('p95', 0):.2f} ms")
        lines.append(f"P99 响应时间:  {total.get('p99', 0):.2f} ms")
        lines.append(f"最大响应时间:  {total.get('max_response_time', 0):.2f} ms")
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
