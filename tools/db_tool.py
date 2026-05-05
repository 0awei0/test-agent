import json
from agents import function_tool
from core.db_client import DBClient


@function_tool
def query_database(sql: str) -> str:
    """执行 SQL 查询语句，返回查询结果。用于数据校验。

    Args:
        sql: SQL 查询语句 (SELECT)
    """
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for safety"

    db = DBClient()
    try:
        rows = db.fetchall(sql)
        return json.dumps(rows, ensure_ascii=False, default=str, indent=2)
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
    finally:
        db.close()
