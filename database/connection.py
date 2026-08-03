import duckdb
import re
import os
from typing import Any, Dict, Union
from config import settings


def _execute_sql_file(conn: duckdb.DuckDBPyConnection, filename: str) -> None:
    """Helper utility to safely read and execute an external SQL file."""
    sql_file_path = os.path.join(os.path.dirname(__file__), 'sql', filename)
    if os.path.exists(sql_file_path):
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read().strip()
            if sql_script:
                conn.execute(sql_script)


def _init_database_views(db_path: str) -> None:
    """Creates or updates analytical views and tables once on database manager initialization."""
    try:
        # Connect with write permissions briefly to define/update views and tables
        with duckdb.connect(db_path, read_only=False) as conn:
            _execute_sql_file(conn, 'api_error_logs.sql')
            _execute_sql_file(conn, 'country_mappings.sql')
            _execute_sql_file(conn, 'v_normalized_api_errors.sql')
    except Exception as e:
        print(f"Warning: Could not initialize/update DuckDB views or tables: {e}")


class DuckDBManager:
    def __init__(self):
        self.db_path = settings.resolved_duckdb_path
        self.read_only = settings.duckdb_read_only

        # Build or refresh the view/table definitions once at startup
        _init_database_views(self.db_path)

    def execute_read_query(self, query: str) -> Union[Dict[str, Any], str]:
        """Executes a read-only SELECT query against DuckDB."""
        # Clean markdown code fences if the LLM wraps them
        query = query.strip()
        if query.startswith("```sql"):
            query = query[6:]
        if query.startswith("```"):
            query = query[3:]
        if query.endswith("```"):
            query = query[:-3]
        query = query.strip()

        upper_query = query.upper()

        # Enforce read-only execution guardrails
        if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b', upper_query):
            return {"error": "Security violation: Only SELECT queries are permitted. Destructive keywords found."}

        try:
            # Query in read_only mode for maximum performance and isolation
            with duckdb.connect(self.db_path, read_only=self.read_only) as conn:
                cursor = conn.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()

                return {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
        except Exception as e:
            if "does not exist" in str(e).lower() and "v_normalized_api_errors" in str(e).lower():
                return {
                    "error": f"View v_normalized_api_errors missing. Please query raw api_error_logs table directly. Error: {str(e)}"
                }
            return {"error": f"DuckDB Execution Error: {str(e)}"}

    def execute_write_query(self, query: str, parameters: tuple = ()) -> Dict[str, Any]:
        """Executes a write query (INSERT/UPDATE/DELETE) against DuckDB."""
        try:
            # Need to connect with read_only=False to allow writes
            with duckdb.connect(self.db_path, read_only=False) as conn:
                cursor = conn.execute(query, parameters)
                # Ensure compatibility with duckdb Python API for rowcount
                return {"success": True, "row_count": getattr(cursor, 'rowcount', 0)}
        except Exception as e:
            return {"error": f"DuckDB Write Execution Error: {str(e)}"}