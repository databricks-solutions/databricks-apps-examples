"""LangChain SQL agent demo that can answer natural-language questions about
forecast results stored in Databricks.

Usage (interactive):
$ python -m dash_dbx_writeback.ml.forecast_agent "Which Loyalty_Group items are forecast above 400 units?"

The script builds a LangChain *SQL Database Toolkit* pointing at the Databricks
warehouse URL from ``workspace_client`` and feeds it to an OpenAI-powered agent
by default.  You can swap the LLM to `AzureChatOpenAI`, `Databricks` etc. as
long as the environment variables for authentication are present.

NOTE  This file is **demo-only**; for production you would embed the agent as a
Dash callback or FastAPI endpoint.
"""

from __future__ import annotations

import argparse
import os

from langchain.chat_models import ChatOpenAI
from langchain.sql_database import SQLDatabase
from langchain.chains import SQLDatabaseChain
from langchain.agents import create_sql_agent
from langchain.agents.agent_types import AgentType

from ..config.workspace_client import get_connection, get_workspace_client
from ..config.unity_catalog import get_catalog_name, get_schema_name


def build_db() -> SQLDatabase:
    """Return an SQLDatabase wrapper over the Databricks connection."""
    conn = get_connection()
    # `langchain` SQLDatabase takes sqlalchemy URL; we'll use the HTTP path DSN
    catalog = get_catalog_name()
    schema = get_schema_name()
    uri = f"databricks://:@/{catalog}/{schema}?http_path={os.getenv('DATABRICKS_HTTP_PATH')}"
    return SQLDatabase.from_uri(uri)


def build_agent() -> SQLDatabaseChain:
    db = build_db()
    llm = ChatOpenAI(temperature=0.0)
    return create_sql_agent(
        llm=llm,
        db=db,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )


def main(question: str):
    agent = build_agent()
    answer = agent.run(question)
    print("\n====== ANSWER ======")
    print(answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask a question about forecast results via LangChain SQL agent")
    parser.add_argument("question", nargs="?", default="Show top 5 products by predicted units", help="Natural language question")
    args = parser.parse_args()
    main(args.question) 