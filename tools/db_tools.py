import json
import logging
from database.connection import DuckDBManager

# Configure logging to see tool executions in the terminal
logger = logging.getLogger(__name__)
# Set logging level to DEBUG to see detailed request/response logs from servicenow_tools.py
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the shared db manager
db_manager = DuckDBManager()

def execute_analytics_sql(query: str) -> str:
    """
    Executes a read-only SQL query against DuckDB and returns the response as JSON.

    Args:
        query: Standard DuckDB SQL query string (SELECT queries only).
    """
    logger.info(f"🟢 AGENT TOOL CALLED: Executing SQL ->\n{query}\n")
    
    result = db_manager.execute_read_query(query)
    
    # Optional: Log the row count to confirm data was fetched
    row_count = result.get('row_count', 0) if isinstance(result, dict) else 'Error'
    logger.info(f"🔵 DB RESPONSE: Fetched {row_count} rows.")

    return json.dumps(result, default=str)