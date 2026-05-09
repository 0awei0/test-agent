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
│  │  (mimo)   │    │ (mimo+工具)│   │ (doubao)  │    │ (Python)  │      │
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
│                     Post-Test Analysis                                   │
│  ┌───────────────────────┐    ┌───────────────────────┐                │
│  │    Perf Analyzer      │    │   Failure Analyzer    │                │
│  │  (QPS/响应时间/错误率) │    │ (mimo+工具/Bug归因)   │                │
│  └───────────────────────┘    └───────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心 Workflow

### 八阶段 Pipeline

```
Step 1: Plan Agent (mimo, 纯推理)
├── 输入: Swagger JSON (70 个接口)
├── 输出: test_plan.json (13 个模块, 执行顺序)
└── 作用: 制定测试策略

Step 2: Generator Agent (mimo, 带工具)
├── 工具: parse_swagger_doc, get_api_detail
├── 可自主读取 Swagger 文档了解接口详情
└── 输出: YAML 测试用例

Step 3: Reviewer Agent (doubao, 纯推理)
├── 审核: 格式、覆盖度、断言合理性
└── 不通过则反馈给 Generator 重新生成（最多 2 轮）

Step 4: Coverage Analyzer (Python)
├── 对比 Swagger 接口清单与 YAML 用例
└── 输出: 覆盖率报告（模块级 + 接口级）

Step 5: Feedback Loop
├── 覆盖率 < 90% 时触发
├── Generator 自动补充缺失用例
└── 最多 3 轮迭代

Step 6: Pytest Execution (pytest)
├── 执行所有 YAML 测试用例
├── 生成 Allure 报告
└── 输出: 通过/失败统计

Step 7: Performance Test (locust)
├── YAML 配置化压测场景
├── 动态 Token 注入
└── 输出: QPS/响应时间/P95/错误率

Step 8: Failure Analysis (mimo, 带工具)
├── 工具: analyze_test_failures, get_failure_details
├── Agent 自主收集失败用例并分析
└── 输出: 失败分类 + Bug 报告
```

### 设计原则：混合模式

| 环节 | 模式 | 原因 |
|------|------|------|
| Plan | 纯推理 | 输入输出明确，不需要工具 |
| Generator | 带工具 | 需要读取 Swagger 了解接口详情 |
| Reviewer | 纯推理 | 只需审核文本，不需要工具 |
| Coverage | Python 函数 | 确定性逻辑，不需要 Agent |
| Pytest | Python 函数 | 确定性逻辑，不需要 Agent |
| Perf Test | Python 函数 | 确定性逻辑，不需要 Agent |
| Failure Analysis | 带工具 | 需要收集失败用例、分析原因 |

**确定性流程写死，需要推理的环节让 Agent 自主调用工具。**

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
│   ├── chain_runner.py          # 链路测试执行器
│   ├── assertion.py             # 自定义断言（7种SQL断言）
│   ├── coverage.py              # 接口覆盖率分析
│   ├── locust_runner.py         # YAML → locust + 压测
│   └── failure_collector.py     # 失败用例收集器
├── tools/                       # Agent 可调用的工具（14个）
├── agent/                       # Agent 层
│   ├── model.py                 # mimo + doubao 模型配置
│   ├── main.py                  # Agent 创建（带工具）
│   ├── workflow.py              # 8 阶段 Pipeline
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
| 多 Agent 协作 | Plan/Generator/Reviewer/Analyzer 四个 Agent，混合模式 |
| YAML 驱动测试 | 自定义 pytest Collector，支持变量替换 |
| 7 种数据库断言 | 行数、字段值、非空、范围、包含、关联校验 |
| 链路测试 | 步骤间数据传递，E2E 业务流程验证 |
| 覆盖率分析 | 对比 Swagger + YAML，Feedback Loop 自动补充 |
| 性能压测 | YAML 配置化 locust，动态 Token 注入 |
| 失败分析 | Agent 自主调用工具，分类用例问题/Bug/环境问题 |
| 工具链 | 14 个 function_tool，带错误处理和重试 |
