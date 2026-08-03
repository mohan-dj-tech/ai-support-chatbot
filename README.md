# Support Chatbot
An AI-powered support chatbot that combines data analysis capabilities with IT Service Management (ServiceNow) workflows. Built using Google ADK and Gemini.

## Architecture

The project currently follows a **Multi-Agent Architecture (Supervisor/Worker pattern)**:

*   **Coordinator Agent**: The primary entry point. Acts as a supervisor that manages interactions and routes user intents to specialized sub-agents.
*   **Data Analyst Agent**: A specialized worker agent for querying local analytical databases (DuckDB) to diagnose API error logs and returning beautiful Mermaid chart visualizations.
*   **ServiceNow Agent**: A specialized worker agent for interacting with ServiceNow's Incident Management API. It fetches existing incident details, searches for similar incidents, updates tickets with comments, and creates new tickets (including file attachments).

## Project Structure

```
support_chatbot/
├── src/
│   └── support_chatbot/
│       ├── __init__.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   └── prompts.py
│       ├── config.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── connection.py
│       │   └── sql/
│       │       ├── api_error_logs.sql
│       │       ├── country_mappings.sql
│       │       └── v_normalized_api_errors.sql
│       └── tools/
│           ├── __init__.py
│           ├── db_tools.py
│           └── servicenow_tools.py
├── .adk/
├── .env
├── .gitignore
├── .idea/
├── data/
├── pyproject.toml
├── README.md
├── requirements.txt
└── agent.py  # Entry point for ADK CLI
```

*   `src/support_chatbot/`: The main Python package containing all application logic.
    *   `agent/`: Contains the core agent definitions and system prompts.
        *   `agent.py`: Agent orchestration (Coordinator, Data Analyst, ServiceNow) and instantiation.
        *   `prompts.py`: Extensive system instructions and formatting rules for the unified agent.
    *   `config.py`: Centralized Pydantic configuration pulling from `.env`, including Google Cloud and ServiceNow API credentials.
    *   `database/`: Connection managers and raw SQL setup.
        *   `connection.py`: DuckDB connection manager enforcing security (read-only vs write) and initializing analytical tables.
        *   `sql/`: Stores SQL files for analytical table/view definitions (e.g., `api_error_logs.sql`).
    *   `tools/`: Contains the Python functions that the LLM is allowed to call.
        *   `db_tools.py`: Read-only queries for data analysis.
        *   `servicenow_tools.py`: Interacts with ServiceNow's Incident Management API for fetching, searching, updating, and creating incidents (using OAuth2 Client Credentials).
*   `agent.py` (root): The primary entry point for the ADK CLI, importing the main agent instance from `src/support_chatbot/agent/agent.py`.
*   `pyproject.toml`: Project metadata and build configuration, enabling `pip install -e .`.
*   `.adk/`: (Generated) ADK's local cache and session data.
*   `.env`: Environment variables for configuration.
*   `.gitignore`: Specifies intentionally untracked files to ignore.
*   `.idea/`: (Generated) IntelliJ/PyCharm IDE configuration files.
*   `data/`: (Generated) Holds the local `.duckdb` data files.
*   `README.md`: Project documentation.
*   `requirements.txt`: Python dependencies.

## Setup & Running

1.  Ensure Python 3.10+ is installed.
2.  Install requirements and the project in editable mode:
    ```bash
    pip install -r requirements.txt
    pip install -e .
    ```
3.  Set up your `.env` file with necessary credentials:
    *   **Google Cloud/Vertex AI**:
        ```
        GOOGLE_GENAI_USE_VERTEXAI=1
        GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
        GOOGLE_CLOUD_LOCATION="us"
        # GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json" # Optional, if not using gcloud auth
        ```
    *   **ServiceNow API (OAuth 2.0 Client Credentials Flow)**:
        ```
        SERVICENOW_INSTANCE_URL="https://yourinstance.service-now.com"
        SERVICENOW_CLIENT_ID="your_oauth_client_id"
        SERVICENOW_CLIENT_SECRET="your_oauth_client_secret"
        # SERVICENOW_USERNAME="optional_system_user_for_caller_id" # If you need to set a specific caller
        # SERVICENOW_PASSWORD="optional_system_user_password"
        ```
        *(Ensure your ServiceNow OAuth application is configured for the **Client Credentials** grant type. The user implicitly linked to the OAuth application must have `itil` and `rest_api_explorer` roles.)*

4.  **Delete the ADK cache** (crucial after structural changes or `pip install -e .`):
    ```bash
    rm -rf .adk
    ```
    *(Or manually delete the `.adk` folder in your project root.)*

5.  Run the ADK development server from the project root, explicitly pointing to the agent module:
    ```bash
    adk run support_chatbot.agent.agent
    ```
    *(Access the UI in your browser, usually at `http://localhost:8000`)*