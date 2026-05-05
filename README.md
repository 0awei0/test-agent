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
│   ├── api_client.py            # HTTP 请求封装
│   ├── db_client.py             # MySQL 操作封装
│   ├── yaml_parser.py           # YAML 解析 + 变量替换
│   ├── yaml_runner.py           # YAML → pytest 执行
│   ├── chain_runner.py          # 链路测试执行器
│   ├── assertion.py             # 自定义断言（7种SQL断言）
│   ├── coverage.py              # 接口覆盖率分析
│   ├── locust_runner.py         # YAML → locust + 压测
│   └── failure_collector.py     # 失败用例收集器
├── tools/                       # Agent 可调用的工具（9个function_tool）
├── agent/                       # Agent 层
│   ├── model.py                 # mimo + doubao 模型配置
│   ├── workflow.py              # 完整工作流 Pipeline
│   └── prompts/                 # Prompt 模板
├── testcases/                   # YAML 测试用例
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

## 六、简历写法（可直接复制）

### 项目名称
AI 驱动的接口自动化测试平台

### 项目简介
针对苍穹外卖项目 70 个接口人工编写测试用例效率低、覆盖不全的问题，基于多 Agent 协作开发自动化测试框架。系统通过 LLM 自动解析 Swagger 文档生成 YAML 测试用例，集成性能压测与智能失败分析，实现从用例设计、执行到 Bug 归因的全流程闭环。

### 项目亮点

**1. 多 Agent 协作流水线**：设计 Plan → Generate → Review → Coverage → Perf Test → Failure Analysis 七阶段 Pipeline，引入 3 个 Agent + 双模型组合（mimo 生成 + doubao 审核），14 分钟自动完成 228 个用例生成，效率较人工提升 10 倍。

**2. YAML 驱动测试框架**：基于 pytest 自定义 Collector 实现 YAML 用例动态执行，支持变量替换、7 种数据库断言及链路测试（步骤间数据传递），用例维护成本显著降低。

**3. 覆盖率自动闭环**：建立 Feedback Loop 机制，自动对比 Swagger 接口清单与 YAML 用例，驱动 Agent 补充缺失场景，接口覆盖率从 2.9% 提升至 98.6%。

**4. 配置化全链路压测**：自研 YAML 驱动的 locust 压测方案，支持动态 Token 注入与接口权重配置。50 并发负载测试 QPS 36.72，平均响应 99ms，发现 `/admin/shop/status` 接口 500 错误。

**5. 智能归因与链路验证**：失败分析 Agent 自动解析 Allure 报告，分类为用例问题 / 代码 Bug / 环境问题并生成报告。支持 8 步 E2E 链路测试，验证"登录→查询→下单"完整业务流程。

### 关键数据

| 指标 | 数据 |
|------|------|
| API 接口数 | 70 个 |
| 测试用例数 | 228 个（YAML 驱动） |
| 接口覆盖率 | 98.6%（模块级 100%） |
| 链路测试 | 8 步业务流程，全部通过 |
| 压测并发 | 50 用户 / 60s |
| 压测 QPS | 36.72 |
| 平均响应时间 | 99ms |
| P95 响应时间 | 180ms |
| 发现 Bug | 2 个 |
| 全流程耗时 | 14 分钟 |

---

## 七、面试深挖 Q&A

### 亮点一：多 Agent 协作流水线

**Q1: 介绍一下整体架构设计**

> 系统采用七阶段 Pipeline 架构：Plan Agent 分析 Swagger 文档生成测试计划 → Generator Agent 按模块生成 YAML 用例 → Reviewer Agent 审核用例质量 → Coverage Analyzer 检测覆盖率 → Feedback Loop 补充缺失用例 → Performance Test 执行压测 → Failure Analysis 分析失败原因。整个流程通过 `workflow.py` 编排，一条命令自动执行。

**Q2: 为什么用 3 个 Agent 而不是 1 个？**

> 单一 Agent 的 prompt 会非常长，既要懂 API 分析、又要会写用例、还要会审核，效果不好。拆分成 3 个 Agent 后：
> - Plan Agent 专注于模块划分和优先级排序
> - Generator Agent 专注于 YAML 用例生成
> - Reviewer Agent 专注于质量审核
>
> 每个 Agent 的 prompt 更聚焦，输出质量更高。这也是软件工程"单一职责"原则的体现。

**Q3: 为什么 Generator 和 Reviewer 用不同模型？**

> mimo 擅长代码生成，速度快、成本低，适合批量生成 YAML。doubao 推理能力强，审核更严格，能发现格式错误、覆盖不全、断言不合理等问题。不同模型组合能发挥各自优势，也展示了多模型协作能力。

**Q4: Agent 之间怎么通信？**

> Agent 之间不是直接通信，而是由 `workflow.py` 主流程协调。Generator 的输出（YAML 字符串）作为 Reviewer 的输入传入。如果不通过，Reviewer 的反馈会和原始需求一起传回 Generator。这是**编排式协作**，不是对等通信。

**Q5: 为什么选择 OpenAI Agent SDK 而不是 LangChain？**

> OpenAI Agent SDK 更轻量，核心抽象只有 Agent、Runner、Tool 三个。LangChain 太重，概念太多（Chain、Agent、Memory、Retriever 等），学习成本高。而且 Agent SDK 的 `@function_tool` 装饰器非常简洁，一个函数加 docstring 就能变成 Tool。

**Q6: Prompt 是怎么设计的？**

> 每个 Agent 有独立的 prompt 文件：
> - `planner.md`：定义输出 JSON 格式、模块划分原则、优先级标准
> - `generator.md`：定义 YAML 格式、用例设计原则（正常/异常/边界）
> - `reviewer.md`：定义审核标准（格式、覆盖度、断言合理性）
>
> 关键是给 Agent 明确的输出格式约束和质量标准。

---

### 亮点二：YAML 驱动测试框架

**Q7: pytest 是怎么执行 YAML 用例的？**

> 实现了自定义 `pytest.Collector`：
> - `pytest_collect_file` 钩子在收集阶段识别 `.yaml` 文件（文件名以 `test_` 开头）
> - `YamlFile.collect()` 解析 YAML，为每个 case 生成一个 `YamlItem` 测试项
> - `YamlItem.runtest()` 调用 `yaml_runner.py` 发送请求、做断言
>
> 这样 pytest 不知道底层是 YAML，只管收集和执行，完全兼容 pytest 的标记、报告、插件机制。

**Q8: 变量替换 `{{token}}` 是怎么实现的？**

> `yaml_parser.py` 中的 `replace_variables` 函数递归遍历 YAML 数据结构，用正则匹配 `{{变量名}}`，从 context 字典中取值替换。context 包含 `base_url`、`admin_token` 等预定义变量。
>
> 链路测试中，`extract` 字段从响应中提取值存入 context，后续步骤的 `{{变量名}}` 就能引用。

**Q9: 7 种数据库断言分别是什么？怎么实现的？**

> `assertion.py` 实现了 7 种断言：
> 1. `expect_not_empty` — 查询结果不为空
> 2. `expect_empty` — 查询结果为空
> 3. `expect_row_count` — 断言返回行数
> 4. `expect_field` — 断言指定字段的值（如 price=3800）
> 5. `expect_field_not_null` — 字段不能为 NULL
> 6. `expect_field_range` — 字段值在范围内（如 price 在 100-10000）
> 7. `expect_field_contains` — 字段包含子串
>
> 每种断言是一个独立函数，`yaml_runner.py` 的 `run_db_checks` 根据 YAML 配置调用对应函数。

**Q10: YAML 格式是怎么设计的？为什么不直接用 Python？**

> YAML 格式设计目标是**可读性**和**非技术人员可维护性**：
> ```yaml
> cases:
>   - name: 新增菜品_正常流程
>     request:
>       method: POST
>       path: /admin/dish
>       body: {name: "宫保鸡丁", price: 3800}
>     assert:
>       json: {code: 1}
>     db_check:
>       - sql: "SELECT * FROM dish WHERE name='宫保鸡丁'"
>         expect_not_empty: true
> ```
>
> 优势：不需要写 Python 代码、容易理解、容易批量修改、可以被 Agent 生成。缺点是灵活性不如 Python，但对于接口测试场景足够了。

**Q11: 为什么不直接用 pytest 的 parametrize？**

> `parametrize` 适合同一接口不同参数的场景，但不适合：
> - 不同接口的用例（路径、方法、参数都不同）
> - 需要数据库校验的场景
> - 需要变量替换的场景
>
> 自定义 Collector 更灵活，每个 YAML 文件就是一个测试套件，每个 case 就是一个测试用例。

---

### 亮点三：覆盖率自动闭环

**Q12: 覆盖率是怎么计算的？**

> `coverage.py` 的逻辑：
> 1. 从 Swagger JSON 提取所有接口（路径+方法），共 70 个
> 2. 扫描 testcases/ 下所有 YAML 文件，提取已覆盖的接口
> 3. 路径匹配：精确匹配 → 去掉 query 参数匹配 → `{id}` 参数模糊匹配 → 前缀匹配
> 4. 覆盖率 = 已覆盖接口数 / 总接口数 × 100%
>
> 支持模块级统计，每个模块单独计算覆盖率。

**Q13: 路径匹配怎么处理 `/admin/dish/{id}` 和 `/admin/dish/123`？**

> `_path_matches` 函数逐段比较：
> - Swagger 路径: `/admin/dish/{id}` → 拆分为 `["admin", "dish", "{id}"]`
> - 用例路径: `/admin/dish/123` → 拆分为 `["admin", "dish", "123"]`
> - 逐段比较时，`{id}` 以 `{` 开头 `}` 结尾，视为通配符，匹配任意值
>
> 还支持前缀匹配：`/admin/category` 匹配 `/admin/category/list`。

**Q14: Feedback Loop 是怎么实现的？**

> `workflow.py` 中的 `run_feedback_loop` 函数：
> 1. 检查覆盖率是否达到 90% 目标
> 2. 如果未达标，取未覆盖接口列表
> 3. 按模块分组，喂给 Generator Agent 生成补充用例
> 4. Reviewer Agent 审核
> 5. 重新运行覆盖率检测
> 6. 最多 3 轮迭代
>
> 关键是把未覆盖接口作为上下文传给 Generator，让它针对性生成。

**Q15: 为什么不追求 100% 覆盖？**

> 两个原因：
> 1. 文件上传接口（`/admin/common/upload`）不适合用 YAML 测试，需要 multipart/form-data
> 2. 投入产出比：从 98.6% 到 100% 可能需要花很多时间处理边界情况，但价值不大
>
> 90% 是合理的工程目标，剩余的可以人工补充。

---

### 亮点四：配置化全链路压测

**Q16: 压测是怎么实现的？**

> `locust_runner.py` 的流程：
> 1. 读取 YAML 压测配置（并发数、时长、接口列表、权重）
> 2. 动态生成 `locustfile.py`，每个场景对应一个 `@task(weight)` 方法
> 3. 如果配置了 login，生成 `on_start()` 方法自动登录获取 token
> 4. 调用 `subprocess.run` 执行 locust 命令（headless 模式）
> 5. 解析 locust 输出的 CSV 文件，提取 QPS、响应时间、错误率等指标

**Q17: token 动态获取怎么实现的？**

> YAML 中配置 login 段：
> ```yaml
> login:
>   enabled: true
>   path: /admin/employee/login
>   body: {username: "admin", password: "123456"}
>   token_field: "data.token"
> ```
>
> 生成的 locustfile 中，每个虚拟用户启动时调用 `on_start()`：
> ```python
> def on_start(self):
>     response = self.client.post("/admin/employee/login", json={...})
>     data = response.json()
>     self.token = data["data"]["token"]  # 按 token_field 路径提取
> ```
>
> 后续请求自动携带 `headers={"token": self.token}`。

**Q18: 为什么不直接用 locust 的 Python 代码？**

> YAML 配置化的优势：
> 1. 不需要写 Python，测试人员就能配置压测场景
> 2. 可以被 Agent 自动生成
> 3. 场景可复用、可版本管理
> 4. 统一格式，方便批量执行和结果对比

**Q19: 压测发现了什么问题？**

> 50 并发 / 60s 压测结果：
> - `/admin/shop/status` 接口 100% 返回 500 错误，这是应用层 Bug
> - 其他接口 0% 错误率，QPS 36.72，平均响应 99ms
> - P95 响应时间 180ms，P99 220ms，说明大部分请求响应很快
>
> 这个 Bug 是压测自动发现的，说明压测方案有效。

**Q20: QPS 36.72 算高吗？怎么优化？**

> 对于 2 核 4G 的云服务器来说，36.72 QPS 是正常水平。瓶颈可能在：
> 1. 数据库连接数限制
> 2. Spring Boot 默认 Tomcat 线程池（200 线程）
> 3. MySQL 查询没有优化
>
> 优化方向：加缓存（Redis）、数据库读写分离、增加服务器配置。

---

### 亮点五：智能归因与链路验证

**Q21: 失败分析 Agent 是怎么工作的？**

> `failure_collector.py` 从 Allure 报告目录读取 `*-result.json` 文件，提取 status 为 failed/broken 的用例，收集错误信息和堆栈。Agent 根据错误模式分类：
> - 500 错误 → 代码 Bug
> - 断言不匹配 → 用例问题（如期望 code=999 但实际 code=1）
> - 超时/连接失败 → 环境问题
>
> 输出结构化分析报告 + Bug 报告模板。

**Q22: 链路测试怎么实现步骤间数据传递？**

> `chain_runner.py` 维护一个 `context` 字典：
> 1. 每步执行后，`extract` 字段指定要提取的变量名和 JSONPath
> 2. `extract_value` 函数从响应中按路径提取值（支持 `data.token`、`data.records[0].id`）
> 3. 存入 context
> 4. 后续步骤的 request 中，`{{变量名}}` 会被 `resolve_template` 替换为 context 中的值
>
> 例如：登录提取 token → 查询菜品提取 dish_id → 添加购物车使用 dish_id。

**Q23: 链路测试和普通测试有什么区别？**

> 普通测试：每个用例独立，互不依赖
> 链路测试：步骤间有数据依赖，模拟真实业务流程
>
> 链路测试的价值：能发现接口间的集成问题。比如登录接口返回的 token 格式变了，后面的接口都会失败。

**Q24: 链路测试失败了怎么定位问题？**

> 链路测试每步都有独立断言。如果 Step 3 失败：
> 1. 检查 Step 2 的 extract 是否正确提取了变量
> 2. 检查 Step 3 的 request 中变量替换是否正确
> 3. 检查 Step 3 的接口是否有 Bug
>
> `chain_runner` 返回每步的执行结果，可以精确定位失败步骤。

**Q25: Bug 报告是怎么生成的？**

> 失败分析 Agent 根据模板生成：
> ```json
> {
>   "title": "[菜品管理] 新增菜品返回500错误",
>   "severity": "P1",
>   "steps": "1. 调用 POST /admin/dish\n2. 参数: {...}\n3. 返回: 500",
>   "expected": "返回 code=1 成功",
>   "actual": "返回 500 Internal Server Error",
>   "api_response": "{...}"
> }
> ```
>
> 包含标题、严重程度、复现步骤、期望结果、实际结果、接口返回。

---

### 综合问题

**Q26: 这个项目最大的技术挑战是什么？**

> 两个挑战：
> 1. **YAML 动态执行**：让 pytest 能直接执行 YAML 用例，需要自定义 Collector，理解 pytest 的收集机制
> 2. **Agent 质量控制**：LLM 生成的 YAML 可能有格式错误、覆盖不全，需要 Reviewer Agent 审核 + Feedback Loop 迭代

**Q27: 如果让你重新设计，会改什么？**

> 1. 用 Pydantic 做 YAML schema 校验，提前发现格式问题
> 2. 加一个 Agent 负责从 Swagger 自动生成完整的 YAML（不需要 Plan → Generate 两步）
> 3. 压测支持阶梯加压，自动找到性能拐点
> 4. 加 Web 界面展示测试报告

**Q28: 这个项目你学到了什么？**

> 1. Agent 不是万能的，需要合理的架构设计和质量控制机制
> 2. YAML 驱动是降低门槛的好方案，但要平衡灵活性和易用性
> 3. 自动化测试的价值不只是"跑通"，而是"发现问题"——压测发现的 500 错误就是例子

**Q29: Agent 的工具调用失败怎么处理？**

> 三层保障：
> 1. **工具层**：每个 `@function_tool` 都有 try/except，捕获异常返回错误字符串，不会让 Agent 崩溃
> 2. **网络层**：API Client 配置了 urllib3 重试策略（3 次重试、0.5s 退避、5xx 自动重试），单次请求 10s 超时
> 3. **Agent 层**：prompt 里告诉 Agent "如果工具返回 Error，尝试换一种方式或跳过"
>
> 关键原则：**工具永远不应该抛异常给 Agent，而是返回可读的错误信息**。

**Q30: 一共有哪些工具？分别做什么？**

> Agent 可调用 14 个 function_tool：
>
> | 工具 | 功能 |
> |------|------|
> | parse_swagger_doc | 解析 Swagger 文档，返回接口清单 |
> | get_api_detail | 获取单个接口的详细参数和响应结构 |
> | analyze_api_coverage | 分析接口覆盖率 |
> | get_uncovered_apis | 获取未覆盖接口清单 |
> | run_pytest_by_yaml | 执行 YAML 测试用例 |
> | send_api_request | 发送单个 HTTP 请求 |
> | query_database | 执行 SQL 查询 |
> | read_test_report | 读取测试报告 |
> | generate_test_data | 用 Faker 生成测试数据 |
> | run_performance_test | 执行压测 |
> | design_perf_scenario | 设计压测场景 |
> | analyze_test_failures | 分析失败用例 |
> | get_failure_details | 获取失败用例详情 |

**Q31: 工具的稳定性怎么保证？**

> 1. **错误处理**：每个工具 try/except，返回 `"Error: ..."` 而不是抛异常
> 2. **输入校验**：检查文件路径是否存在、SQL 是否是 SELECT（防注入）
> 3. **超时控制**：pytest 执行 120s 超时、HTTP 请求 10s 超时
> 4. **重试机制**：API Client 用 urllib3 Retry，5xx 自动重试 3 次
> 5. **幂等设计**：读操作天然幂等，写操作（如执行 pytest）有 `--clean-alluredir` 清理

---

## 八、服务信息

| 服务 | 地址 | 密码 |
|------|------|------|
| 苍穹外卖 | http://124.222.42.246:8080 | admin / 123456 |
| Swagger | http://124.222.42.246:8080/doc.html | - |
| MySQL | 124.222.42.246:3306 | root / Sky@2026!Test |
| Redis | 124.222.42.246:6379 | Redis@2026! |
| mimo API | https://token-plan-cn.xiaomimimo.com/v1 | 见 .env |
| doubao API | https://ark.cn-beijing.volces.com/api/v3 | 见 .env |
