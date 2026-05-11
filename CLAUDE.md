# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-driven API test automation platform using multi-agent collaboration (OpenAI Agent SDK). Agents generate, review, and iterate on YAML test cases against Swagger API docs, then execute them via pytest and locust.

## Commands

```bash
# Setup
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env  # fill in API keys, DB creds, BASE_URL

# Run full 8-stage pipeline (plan → generate → review → coverage → execute → perf → failure analysis)
python -m agent.workflow

# Run tests — MUST bypass local proxy (port 7897) or tests get HTML 备案 page instead of JSON
NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' pytest testcases/ --alluredir=reports/

# Run a single test module
NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' pytest testcases/员工管理/ --alluredir=reports/ -v

# Run tests by priority marker
NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' pytest -m P0 testcases/ --alluredir=reports/

# Chain (E2E) tests
NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' pytest testcases/chain/ --alluredir=reports/ -v

# Coverage analysis (no proxy needed, reads local files)
python coverage.py
```

## Architecture

### Agent Pipeline (8 stages, in `agent/workflow.py`)

The workflow processes each test module independently in a closed loop:

1. **Plan Agent** (mimo, pure reasoning) — reads Swagger JSON, outputs `test_plan.json` with module list and execution order
2. **Generator Agent** (mimo, with tools) — generates YAML test cases, can call `parse_swagger_doc` / `get_api_detail`
3. **Reviewer Agent** (doubao, pure reasoning) — reviews YAML against Swagger for correctness and coverage
4. **Coverage Analyzer** (Python function) — compares Swagger endpoints vs generated YAML, triggers feedback loop if <90%
5. **Feedback Loop** — if coverage insufficient, Generator adds missing cases (up to 3 rounds)
6. **Pytest Execution** — runs YAML tests via custom pytest collector
7. **Performance Test** (locust) — YAML-configured load tests with dynamic token injection
8. **Failure Analyzer** (mimo, with tools) — classifies failures as test-case issues vs code bugs vs environment problems

Design principle: **deterministic steps are plain Python functions; steps needing reasoning use Agents with tools.**

### Key Components

- **`conftest.py`** — Custom pytest collector (`YamlFile`/`YamlItem`) that discovers `test_*.yaml` files and runs them as pytest items. Also auto-applies priority markers (P0/P1/P2) from nodeid.
- **`core/yaml_parser.py`** — YAML loading + `{{variable}}` template replacement
- **`core/yaml_runner.py`** — Executes a single YAML test case: sends HTTP request, runs response assertions, runs DB assertions
- **`core/chain_runner.py`** — E2E chain test executor with step-to-step data passing via `{{variable}}` extraction
- **`core/locust_runner.py`** — Generates `locustfile.py` from YAML config, runs fixed-rate or step-load tests, analyzes inflection points
- **`core/assertion.py`** — 7 custom DB assertion types (row count, field value, not-null, range, contains, etc.)
- **`core/api_client.py`** — HTTP client with retry and timeout
- **`core/db_client.py`** — MySQL wrapper (PyMySQL)
- **`core/coverage.py`** — Compares Swagger endpoint list against YAML test cases
- **`tools/`** — 13 function_tools available to Agents (swagger parsing, API requests, DB queries, perf testing, failure analysis, etc.)

### Model Configuration (`agent/model.py`)

- **mimo** (mimo-v2.5) — primary model for generation and analysis, uses OpenAI-compatible API with fallback support
- **doubao** (doubao-seed-2.0) — review model, via ByteDance ARK API
- Both configured via `.env` and `config/settings.py`

### Test Case Format

YAML files in `testcases/` follow this structure (discovered automatically by `conftest.py`):

```yaml
suite: "模块名"
base_url: "{{base_url}}"  # or explicit URL
cases:
  - name: "测试用例名"
    priority: P0
    request:
      method: POST
      path: /api/endpoint
      headers: { "token": "{{admin_token}}" }
      body: { ... }
    assert:
      status_code: 200
      json: { "code": 0 }
    db_check:
      - sql: "SELECT ..."
        expect_not_empty: true
        expect_field: { name: "status", value: 1 }
```

Chain tests (in `testcases/chain/`) use `chain:` instead of `cases:`, with `extract:` to pass data between steps.

### Environment Variables

All config in `.env` (see `.env.example`). Key groups: MIMO_* (generation model), ARK_* (review model), MYSQL_*, BASE_URL. Loaded by `config/settings.py` via python-dotenv.

## Known Issues

### Proxy causes tests to fail
Local proxy (`http_proxy=http://127.0.0.1:7897`) intercepts requests to `zombieai.cn` and returns a Tencent Cloud 备案 HTML page instead of JSON. Always run pytest with proxy disabled: prefix commands with `NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy=''`.

### Domain blocked by ICP filing
`zombieai.cn` is intercepted by Tencent Cloud's 备案 enforcement — GET requests return HTML. `BASE_URL` in `.env` must use IP `124.222.42.246` instead of the domain. MySQL/Redis host still uses the domain (they connect on different ports not affected).

### AI-generated test assertions don't match server
Test cases were auto-generated by the Agent without precise knowledge of server behavior. Common mismatches:
- Error messages: tests expect "用户不存在", server returns "账号不存在" (no differentiation for security)
- `type` field: tests use string `"food"`, API expects integer `1` (dish) or `2` (setmeal)
- `{{check_not_null}}` template is not implemented in the framework
- Empty/null body tests: server returns non-JSON 400 response, assertion code doesn't handle this

### mimo API quota / fallback
`model.py` fallback logic only triggers on client creation errors, not on runtime 429 (quota exhausted). If primary mimo API quota is exhausted, `python -m agent.workflow` will fail. Use the paid fallback key in `.env` (MIMO_FALLBACK_*).

## Interview Notes Sync

When making changes to the project (new features, architecture changes, tool additions, pipeline modifications), **update the interview notes** at:
`/Users/a1-6/Library/Mobile Documents/iCloud~md~obsidian/Documents/notes/测开项目面经.md`

Keep the following in sync:
- Architecture diagram and pipeline stages
- Project structure (tool count, new modules)
- Q&A answers that reference specific numbers or behaviors
- Service credentials in section 八
- 简历写法 section if capabilities change
