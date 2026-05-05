import json
import os
from agents import function_tool


@function_tool
def parse_swagger_doc(doc_path: str = "docs/admin-swagger.json") -> str:
    """解析 Swagger/OpenAPI 文档，返回接口清单（路径、方法、参数、描述）。
    Agent 调用此工具了解系统有哪些接口，然后设计测试用例。

    Args:
        doc_path: Swagger JSON 文件路径，如 docs/admin-swagger.json 或 docs/user-swagger.json
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(project_root, doc_path)

    if not os.path.exists(full_path):
        return f"Error: File not found: {doc_path}"

    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data.get("info", {})
    result = {
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "base_path": data.get("basePath", "/"),
        "apis": [],
    }

    paths = data.get("paths", {})
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                api_info = {
                    "path": path,
                    "method": method.upper(),
                    "summary": detail.get("summary", ""),
                    "tags": detail.get("tags", []),
                    "parameters": [],
                    "responses": {},
                }

                for param in detail.get("parameters", []):
                    api_info["parameters"].append({
                        "name": param.get("name", ""),
                        "in": param.get("in", ""),
                        "required": param.get("required", False),
                        "type": param.get("type", param.get("schema", {}).get("type", "")),
                        "description": param.get("description", ""),
                    })

                for code, resp in detail.get("responses", {}).items():
                    api_info["responses"][code] = resp.get("description", "")

                result["apis"].append(api_info)

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if len(output) > 8000:
        api_list = []
        for api in result["apis"]:
            api_list.append(f"{api['method']:6s} {api['path']:40s} {api['summary']}")
        output = f"共 {len(result['apis'])} 个接口：\n\n" + "\n".join(api_list)

    return output


@function_tool
def get_api_detail(doc_path: str, api_path: str, method: str = "GET") -> str:
    """获取指定接口的详细信息，包括参数、请求体、响应结构。
    用于深入了解某个接口的入参和出参，以便设计精确的测试用例。

    Args:
        doc_path: Swagger JSON 文件路径
        api_path: 接口路径，如 /admin/employee/login
        method: HTTP 方法 (GET/POST/PUT/DELETE)
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(project_root, doc_path)

    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths = data.get("paths", {})
    if api_path not in paths:
        matches = [p for p in paths if api_path in p]
        if matches:
            return f"未找到 {api_path}，你是不是要找: {matches}"
        return f"未找到接口: {api_path}"

    method_lower = method.lower()
    if method_lower not in paths[api_path]:
        return f"接口 {api_path} 不支持 {method} 方法，支持: {list(paths[api_path].keys())}"

    detail = paths[api_path][method_lower]

    definitions = data.get("definitions", {})

    result = {
        "path": api_path,
        "method": method.upper(),
        "summary": detail.get("summary", ""),
        "tags": detail.get("tags", []),
        "parameters": [],
        "request_body": None,
        "responses": {},
    }

    for param in detail.get("parameters", []):
        if param.get("in") == "body":
            schema = param.get("schema", {})
            ref = schema.get("$ref", "")
            if ref:
                ref_name = ref.split("/")[-1]
                result["request_body"] = {
                    "description": param.get("description", ""),
                    "schema_ref": ref_name,
                    "schema": definitions.get(ref_name, {}),
                }
            else:
                result["request_body"] = {"schema": schema}
        else:
            result["parameters"].append({
                "name": param.get("name", ""),
                "in": param.get("in", ""),
                "required": param.get("required", False),
                "type": param.get("type", ""),
                "description": param.get("description", ""),
            })

    for code, resp in detail.get("responses", {}).items():
        schema = resp.get("schema", {})
        ref = schema.get("$ref", "") if schema else ""
        resp_info = {"description": resp.get("description", "")}
        if ref:
            ref_name = ref.split("/")[-1]
            resp_info["schema"] = definitions.get(ref_name, {})
        result["responses"][code] = resp_info

    return json.dumps(result, ensure_ascii=False, indent=2)
