import json
from jsonpath_ng import parse as jsonpath_parse
from loguru import logger


def assert_status_code(actual: int, expected: int):
    assert actual == expected, f"Status code mismatch: expected {expected}, got {actual}"
    logger.info(f"[Assert] Status code {actual} == {expected} ✓")


def assert_json_field(response: dict, field: str, expected):
    if field.startswith("$."):
        matches = [m.value for m in jsonpath_parse(field).find(response)]
        assert len(matches) > 0, f"JSONPath {field} not found in response"
        actual = matches[0]
    else:
        actual = response.get(field)

    assert actual == expected, f"JSON field {field} mismatch: expected {expected}, got {actual}"
    logger.info(f"[Assert] {field}: {actual} == {expected} ✓")


def assert_json_contains(response: dict, expected: dict):
    for key, value in expected.items():
        assert_json_field(response, key, value)


def assert_db_not_empty(rows: list, description: str = ""):
    assert len(rows) > 0, f"DB query returned empty result: {description}"
    logger.info(f"[Assert] DB result not empty ({len(rows)} rows) ✓")


def assert_db_empty(rows: list, description: str = ""):
    assert len(rows) == 0, f"DB query returned {len(rows)} rows, expected empty: {description}"
    logger.info(f"[Assert] DB result empty ✓")


def assert_db_field(rows: list, field: str, expected):
    assert len(rows) > 0, "DB query returned empty result"
    actual = rows[0].get(field)
    assert actual == expected, f"DB field {field} mismatch: expected {expected}, got {actual}"
    logger.info(f"[Assert] DB {field}: {actual} == {expected} ✓")


def assert_db_field_not_null(rows: list, field: str, description: str = ""):
    assert len(rows) > 0, f"DB query returned empty result: {description}"
    actual = rows[0].get(field)
    assert actual is not None, f"DB field {field} is NULL: {description}"
    logger.info(f"[Assert] DB {field} not NULL ✓")


def assert_db_row_count(rows: list, expected: int, description: str = ""):
    actual = len(rows)
    assert actual == expected, f"DB row count mismatch: expected {expected}, got {actual}: {description}"
    logger.info(f"[Assert] DB row count {actual} == {expected} ✓")


def assert_db_field_in_range(rows: list, field: str, min_val, max_val, description: str = ""):
    assert len(rows) > 0, f"DB query returned empty result: {description}"
    actual = rows[0].get(field)
    assert min_val <= actual <= max_val, f"DB field {field}={actual} not in range [{min_val}, {max_val}]: {description}"
    logger.info(f"[Assert] DB {field}={actual} in [{min_val}, {max_val}] ✓")


def assert_db_field_contains(rows: list, field: str, expected_substring: str, description: str = ""):
    assert len(rows) > 0, f"DB query returned empty result: {description}"
    actual = str(rows[0].get(field, ""))
    assert expected_substring in actual, f"DB field {field}='{actual}' does not contain '{expected_substring}': {description}"
    logger.info(f"[Assert] DB {field} contains '{expected_substring}' ✓")


def assert_db_related_exists(rows: list, related_field: str, db_client, related_table: str, related_field_name: str = "id"):
    """校验关联数据是否存在"""
    assert len(rows) > 0, "DB query returned empty result"
    related_id = rows[0].get(related_field)
    assert related_id is not None, f"Related field {related_field} is NULL"

    check_sql = f"SELECT {related_field_name} FROM {related_table} WHERE {related_field_name} = %s"
    related_rows = db_client.fetchall(check_sql, (related_id,))
    assert len(related_rows) > 0, f"Related record not found: {related_table}.{related_field_name}={related_id}"
    logger.info(f"[Assert] Related record exists: {related_table}.{related_field_name}={related_id} ✓")
