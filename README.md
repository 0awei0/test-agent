# Test Agent - AI 驱动的接口自动化测试平台

> 基于 pytest + OpenAI Agent SDK 的智能测试框架，通过多 Agent 协作实现测试用例的自动生成、审核、执行、覆盖率分析和性能压测。

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Agent Workflow Pipeline                           │
│                                                                          │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐      │
│  │   Plan    │───►│ Generator │───►│ Reviewer  │───►│ Coverage  │      │
│  │  Agent    │    │  Agent    │    │  Agent    │    │ Analyzer  │      │
│  │  (mimo)   │    │  (mimo)   │    │ (doubao)  │    │ (Python)  │      │
│  └───────────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘      │
│       │                 │                │                 │            │
│       │                 ◄────────────────┘                 │            │
│       │              Feedback Loop                         │            │
│       ▼                                                    ▼            │
│  ┌───────────┐                                      ┌───────────┐      │
│  │ Test Plan │                                      │ Coverage  │      │
│  │  (JSON)   │                                      │  Report   │      │
│  └───────────┘                                      └───────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Test Framework (pytest + locust)                    │
│  YAML Runner → 功能测试    Chain Runner → 链路测试    Locust → 压测     │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Target System                                  │
│              苍穹外卖 (Spring Boot + MySQL + Redis)  70 APIs            │
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Post-Test Analysis                                   │
│  ┌───────────────────────┐    ┌───────────────────────┐                │
│  │    Perf Analyzer      │    │   Failure Analyzer    │                │
│  │  (QPS/响应时间/错误率) │    │ (Bug归因/分类/报告)   │                │
│  └───────────────────────┘    └───────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心 Workflow

### 七阶段 Pipeline

```
Step 1: Plan Agent (mimo)
├── 输入: Swagger JSON (70 个接口)
├── 分析: 按业务功能划分模块，确定优先级
├── 输出: test_plan.json (13 个模块, 执行顺序, 预估用例数)
└── 作用: 制定测试策略，避免盲目生成

Step 2: Generator Agent (mimo)
├── 输入: 测试计划中的模块列表
├── 执行: 按模块批量生成 YAML 测试用例
├── 输出: testcases/ 目录下的 YAML 文件
└── 特点: 每个接口至少 3 个用例（正常+异常+边界）

Step 3: Reviewer Agent (doubao)
├── 输入: Generator 生成的 YAML
├── 审核: 格式正确性、覆盖度、断言合理性
├── 输出: 审核通过 / 修改建议
└── 机制: 不通过则反馈给 Generator 重新生成（最多 2 轮）

Step 4: Coverage Analyzer (Python)
├── 输入: Swagger JSON + YAML 用例
├── 分析: 对比接口清单和已覆盖用例
├── 输出: 覆盖率报告（模块级 + 接口级）
└── 阈值: 目标 90%，低于则触发 Feedback Loop

Step 5: Feedback Loop
├── 输入: 未覆盖接口清单
├── 执行: 自动生成缺失用例
├── 验证: 重新检测覆盖率
└── 终止: 覆盖率达标 或 达到最大轮数

Step 6: Performance Test (locust)
├── 输入: 压测场景 YAML
├── 执行: 动态生成 locustfile → 执行压测
├── 特点: 自动登录获取 token，动态注入请求
└── 输出: 性能报告（QPS、响应时间、P95/P99、错误率）

Step 7: Failure Analysis
├── 输入: Allure 报告中的失败用例
├── 分析: Agent 分类失败原因（用例问题/Bug/环境问题）
└── 输出: 结构化分析报告 + Bug 报告模板
```

---

## 三、项目结构

```
test-agent/
├── config/settings.py           # 统一配置管理
├── core/                        # 框架核心
│   ├── api_client.py            # HTTP 请求封装（重试+超时）
│   ├── db_client.py             # MySQL 操作封装
│   ├── yaml_parser.py           # YAML 解析 + 变量替换
│   ├── yaml_runner.py           # YAML → pytest 执行
│   ├── chain_runner.py          # 链路测试执行器（步骤间数据传递）
│   ├── assertion.py             # 自定义断言（7种SQL断言）
│   ├── coverage.py              # 接口覆盖率分析
│   ├── locust_runner.py         # YAML → locust + 压测
│   └── failure_collector.py     # 失败用例收集器
├── tools/                       # Agent 可调用的工具（14个function_tool）
├── agent/                       # Agent 层
│   ├── model.py                 # mimo + doubao 模型配置
│   ├── workflow.py              # 完整工作流 Pipeline
│   └── prompts/                 # Prompt 模板
├── testcases/                   # YAML 测试用例（228个）
├── perf/scenarios/              # 压测场景 YAML
└── docs/                        # Swagger JSON
```

---

## 四、技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| Agent SDK | openai-agents | 轻量、Python-first、支持 function_tool |
| 生成模型 | mimo-v2.5 | 国产、性价比高、兼容 OpenAI API |
| 审核模型 | doubao-seed-2.0 | 字节出品、推理能力强 |
| 测试框架 | pytest | 生态丰富、插件机制强大 |
| 报告 | allure-pytest | 业界标准、可视化好 |
| 性能测试 | locust | Python 原生、YAML 驱动 |

---

## 五、运行结果

### 功能测试
- 总接口数: 70，已覆盖: 69
- 测试用例数: 228（YAML 驱动）
- 接口覆盖率: 98.6%（模块级 100%）

### 性能测试（50 并发 / 60s）
- QPS: 36.72，平均响应: 99ms，P95: 180ms
- 发现 `/admin/shop/status` 接口 500 错误（应用 Bug）

### 链路测试
- 8 步业务流程全部通过
- 步骤间数据自动传递（token、dish_id、setmeal_id）

---

## 六、快速使用

```bash
# 1. 创建虚拟环境
uv venv --python 3.12 .venv
source .venv/bin/activate

# 2. 安装依赖
uv pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 和服务器信息

# 4. 一键执行完整工作流
python -m agent.workflow

# 5. 或单独执行
python coverage.py                    # 查看覆盖率
pytest testcases/ --alluredir=reports/ # 执行功能测试
```

---

## 七、功能特性

| 功能 | 说明 |
|------|------|
| 多 Agent 协作 | Plan/Generator/Reviewer 三个 Agent，双模型组合 |
| YAML 驱动测试 | 自定义 pytest Collector，支持变量替换 |
| 7 种数据库断言 | 行数、字段值、非空、范围、包含、关联校验 |
| 链路测试 | 步骤间数据传递，E2E 业务流程验证 |
| 覆盖率分析 | 对比 Swagger + YAML，Feedback Loop 自动补充 |
| 性能压测 | YAML 配置化 locust，动态 Token 注入 |
| 失败分析 | Agent 自动分类（用例问题/Bug/环境问题） |
| 工具链 | 14 个 function_tool，带错误处理和重试 |
