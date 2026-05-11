import allure
from loguru import logger
from core.yaml_parser import replace_variables
from core.api_client import APIClient
from core.db_client import DBClient
from core.assertion import (
    assert_status_code,
    assert_json_contains,
    assert_db_not_empty,
    assert_db_empty,
    assert_db_field,
    assert_db_field_not_null,
    assert_db_row_count,
    assert_db_field_in_range,
    assert_db_field_contains,
)
from config.settings import settings

# Token cache (module-level, persists across test cases in a session)
_token_cache = {}


def _unlock_admin():
    """Unlock admin account (may be locked by wrong-password tests)"""
    try:
        from core.db_client import DBClient
        db = DBClient()
        db.execute('UPDATE employee SET status=1 WHERE username="admin"')
        db.close()
    except Exception:
        pass


def _login_and_get_token(username: str, password: str, login_path: str) -> str:
    """Login and cache the token. Always unlocks admin account first."""
    cache_key = f"{username}:{login_path}"

    if username == "admin":
        _unlock_admin()

    if cache_key in _token_cache:
        return _token_cache[cache_key]

    client = APIClient(base_url=settings.BASE_URL)
    resp = client.request("POST", login_path, json={"username": username, "password": password})
    token = (resp.get("data") or {}).get("token", "")
    if token:
        _token_cache[cache_key] = token
        logger.info(f"[Auth] Got token for {username}: {token[:20]}...")
    else:
        logger.warning(f"[Auth] Failed to get token for {username}: {resp}")
    return token


def _refresh_admin_token():
    """Force refresh admin token (after account was unlocked)"""
    _token_cache.pop("admin:/admin/employee/login", None)
    return _login_and_get_token("admin", "123456", "/admin/employee/login")


def _get_user_token() -> str:
    """Generate user JWT token directly (bypasses WeChat OAuth)"""
    import jwt
    import time

    cache_key = "_user_jwt_token"
    if cache_key in _token_cache:
        return _token_cache[cache_key]

    try:
        from core.db_client import DBClient
        db = DBClient()
        rows = db.fetchall("SELECT id FROM user LIMIT 1")
        db.close()
        user_id = rows[0]["id"] if rows else 1
    except Exception:
        user_id = 1

    payload = {"userId": user_id, "exp": int(time.time()) + 86400}
    token = jwt.encode(payload, "itheima", algorithm="HS256")
    _token_cache[cache_key] = token
    logger.info(f"[Auth] Generated user JWT token for userId={user_id}")
    return token


def get_default_variables():
    # Ensure admin account is unlocked before getting token
    try:
        from core.db_client import DBClient
        db = DBClient()
        db.execute('UPDATE employee SET status=1 WHERE username="admin"')
        rows = db.fetchall("SELECT id FROM user LIMIT 1")
        db.close()
        user_id = rows[0]["id"] if rows else 1
    except Exception:
        user_id = 1

    admin_token = _login_and_get_token("admin", "123456", "/admin/employee/login")
    user_token = _get_user_token()

    return {
        "base_url": settings.BASE_URL,
        "admin_token": admin_token,
        "user_token": user_token,
        "user_id": user_id,
    }


def run_db_checks(db_checks: list, db: DBClient, case_name: str):
    """执行数据库校验"""
    for check in db_checks:
        sql = check.get("sql", "")
        if not sql:
            continue

        rows = db.fetchall(sql)
        desc = f"{case_name} - {check.get('description', sql[:50])}"

        # 基础断言
        if check.get("expect_not_empty"):
            assert_db_not_empty(rows, desc)
        if check.get("expect_empty"):
            assert_db_empty(rows, desc)

        # 行数断言
        if "expect_row_count" in check:
            assert_db_row_count(rows, check["expect_row_count"], desc)

        # 字段值断言
        if "expect_field" in check:
            field_check = check["expect_field"]
            field_name = field_check.get("name")
            expected_value = field_check.get("value")
            if field_name and expected_value is not None:
                assert_db_field(rows, field_name, expected_value)

        # 字段非空断言
        if "expect_field_not_null" in check:
            for field_name in check["expect_field_not_null"]:
                assert_db_field_not_null(rows, field_name, desc)

        # 字段范围断言
        if "expect_field_range" in check:
            range_check = check["expect_field_range"]
            assert_db_field_in_range(
                rows,
                range_check["name"],
                range_check["min"],
                range_check["max"],
                desc,
            )

        # 字段包含断言
        if "expect_field_contains" in check:
            contains_check = check["expect_field_contains"]
            assert_db_field_contains(
                rows,
                contains_check["name"],
                contains_check["substring"],
                desc,
            )


def run_yaml_test_case(case: dict):
    variables = get_default_variables()

    base_url = case.get("base_url", "")
    if base_url and "{{" not in str(base_url):
        variables["base_url"] = base_url
    elif not base_url:
        base_url = settings.BASE_URL

    resolved_url = replace_variables(str(base_url), variables) if "{{" in str(base_url) else base_url

    client = APIClient(base_url=resolved_url)
    db = DBClient()

    req = replace_variables(case["request"], variables)
    method = req.get("method", "GET").lower()
    path = req.get("path", "")
    headers = req.get("headers", {})
    body = req.get("body", None)
    params = req.get("params", None)

    priority = case.get("priority", "P2")
    name = case.get("name", "unnamed")

    with allure.step(f"[{priority}] {name}"):
        logger.info(f"[Test] {priority} | {name}")

        response = client.request(
            method=method,
            path=path,
            headers=headers,
            json=body if body else None,
            params=params if params else None,
        )

        # If 401 and using admin token, unlock account and retry
        if response.get("_status_code") == 401 and "token" in headers:
            logger.info(f"[Auth] Got 401, refreshing admin token...")
            _unlock_admin()
            new_token = _refresh_admin_token()
            headers["token"] = new_token
            variables["admin_token"] = new_token
            response = client.request(
                method=method,
                path=path,
                headers=headers,
                json=body if body else None,
                params=params if params else None,
            )

        # 响应断言
        expected = case.get("assert", {})
        actual_status = response.pop("_status_code", 0)
        if "status_code" in expected:
            assert_status_code(actual_status, expected["status_code"])
        if "json" in expected:
            assert_json_contains(response, expected["json"])

        # 数据库断言
        db_checks = replace_variables(case.get("db_check", []), variables)
        run_db_checks(db_checks, db, name)

    db.close()
    return response
