import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

from excel_like_dash.config.workspace_client import get_connection
from excel_like_dash.data.sample_product_data import (
    generate_product_data,
)


def pytest_configure(config):
    """Load environment variables from .env file before any tests run."""
    # Get the project root directory (where pyproject.toml is located)
    project_root = Path(__file__).parent.parent

    # Try to load .env file from project root
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
    else:
        print(
            "No .env file found. Make sure to set required environment variables manually."
        )


@pytest.fixture(scope="session")
def conn():
    """Get a Databricks connection."""
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    return get_connection(http_path)


@pytest.fixture(scope="session")
def test_table_name():
    return "daveok.dash_dbx_writeback.pytest_read"


@pytest.fixture(scope="session")
def write_table(conn, test_table_name):
    with conn.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {test_table_name} (x int, x_squared int)"
        )

        squares = [(i, i * i) for i in range(100)]
        values = ",".join([f"({x}, {y})" for (x, y) in squares])

        cursor.execute(f"INSERT INTO {test_table_name} VALUES {values}")
        yield values
        cursor.execute(f"DROP TABLE {test_table_name}")


@pytest.fixture(scope="session")
def custom_data():
    yield generate_product_data(num_products=3)
