#!/bin/bash
# uv-tools.sh - uv 快捷命令集，类似 conda 的使用体验
# 用法: source uv-tools.sh

# 获取项目根目录
export UV_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 激活 uv 虚拟环境（类似 conda activate）
uv-activate() {
    local project_dir="${1:-$UV_PROJECT_ROOT}"
    if [ -f "$project_dir/.venv/bin/activate" ]; then
        source "$project_dir/.venv/bin/activate"
        echo "✅ 已激活 uv 环境: $project_dir/.venv"
        echo "   Python: $(python --version)"
        echo "   路径: $(which python)"
    else
        echo "❌ 未找到 .venv，请先运行 uv-create"
        return 1
    fi
}

# 创建 uv 环境（类似 conda create）
uv-create() {
    local python_version="${1:-3.12}"
    local project_dir="${2:-$UV_PROJECT_ROOT}"
    cd "$project_dir"
    uv venv --python "$python_version" .venv
    uv sync
    echo "✅ 环境创建完成: Python $python_version"
    echo "   运行 uv-activate 激活环境"
}

# 安装包（类似 conda install）
uv-install() {
    if [ $# -eq 0 ]; then
        echo "用法: uv-install <package1> [package2] ..."
        return 1
    fi
    uv add "$@"
}

# 移除包（类似 conda remove）
uv-remove() {
    if [ $# -eq 0 ]; then
        echo "用法: uv-remove <package1> [package2] ..."
        return 1
    fi
    uv remove "$@"
}

# 列出已安装包（类似 conda list）
uv-list() {
    uv pip list
}

# 运行 Python 命令（自动使用 uv 环境）
uv-run() {
    uv run "$@"
}

# 运行 pytest（自动绕过代理）
uv-test() {
    local test_path="${1:-testcases/}"
    local extra_args="${@:2}"
    NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' \
        uv run pytest "$test_path" --alluredir=reports/ -v $extra_args
}

# 运行单个测试模块
uv-test-module() {
    local module="$1"
    if [ -z "$module" ]; then
        echo "用法: uv-test-module <模块名>"
        echo "示例: uv-test-module 员工管理"
        return 1
    fi
    uv-test "testcases/$module/"
}

# 运行 workflow（输出到日志文件）
uv-workflow() {
    local log_file="logs/workflow_$(date +%Y%m%d_%H%M%S).log"
    mkdir -p logs
    echo "🚀 启动 workflow，日志文件: $log_file"
    NO_PROXY='*' no_proxy='*' HTTP_PROXY='' HTTPS_PROXY='' http_proxy='' https_proxy='' \
        uv run python -m agent.workflow 2>&1 | tee "$log_file"
}

# 查看 workflow 日志
uv-log() {
    local log_file="$1"
    if [ -z "$log_file" ]; then
        # 显示最新的日志文件
        log_file=$(ls -t logs/workflow_*.log 2>/dev/null | head -1)
        if [ -z "$log_file" ]; then
            echo "❌ 未找到日志文件"
            return 1
        fi
    fi
    echo "📄 日志文件: $log_file"
    cat "$log_file"
}

# 清理 uv 缓存
uv-clean() {
    uv cache clean
    echo "✅ 缓存已清理"
}

# 显示 uv 环境信息
uv-info() {
    echo "=== uv 环境信息 ==="
    echo "项目目录: $UV_PROJECT_ROOT"
    echo "Python 版本: $(uv run python --version 2>/dev/null || echo '未安装')"
    echo "虚拟环境: $UV_PROJECT_ROOT/.venv"
    echo "已安装包数: $(uv pip list 2>/dev/null | wc -l | tr -d ' ')"
    echo ""
    echo "=== 可用命令 ==="
    echo "uv-activate    激活虚拟环境"
    echo "uv-create      创建新环境"
    echo "uv-install     安装包"
    echo "uv-remove      移除包"
    echo "uv-list        列出已安装包"
    echo "uv-run         运行 Python 命令"
    echo "uv-test        运行 pytest 测试"
    echo "uv-test-module 运行单个测试模块"
    echo "uv-workflow    运行 workflow（带日志）"
    echo "uv-log         查看 workflow 日志"
    echo "uv-clean       清理缓存"
    echo "uv-info        显示环境信息"
}

# 如果直接运行此脚本，显示帮助信息
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "请使用 source 命令加载 uv 工具集:"
    echo "  source uv-tools.sh"
    echo ""
    uv-info
fi
