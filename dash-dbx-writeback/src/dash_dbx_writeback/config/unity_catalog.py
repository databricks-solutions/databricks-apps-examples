"""
Unity Catalog configuration constants.

This module contains the configuration for Unity Catalog catalog and schema names.
These values are read from environment variables with fallback values for development.
"""

import os
from typing import Optional

# Unity Catalog catalog name - read from environment variable with fallback
CATALOG_NAME = os.getenv("DATABRICKS_CATALOG", "daveok")

# Unity Catalog schema name - read from environment variable with fallback
SCHEMA_NAME = os.getenv("DATABRICKS_SCHEMA", "dash_dbx_writeback")


def get_full_table_name(table_name: str) -> str:
    """
    Get the full table name in the format catalog.schema.table.

    Args:
        table_name: The name of the table without catalog and schema

    Returns:
        str: The full table name in format catalog.schema.table
    """
    return f"{CATALOG_NAME}.{SCHEMA_NAME}.{table_name}"


def get_catalog_name() -> str:
    """
    Get the current catalog name.

    Returns:
        str: The catalog name from environment variable or fallback
    """
    return CATALOG_NAME


def get_schema_name() -> str:
    """
    Get the current schema name.

    Returns:
        str: The schema name from environment variable or fallback
    """
    return SCHEMA_NAME


def get_volume_path(volume_name: str) -> str:
    """
    Get the volume path in the format /Volumes/catalog/schema/volume_name.

    Args:
        volume_name: The name of the volume without catalog and schema

    Returns:
        str: The volume path in format /Volumes/catalog/schema/volume_name
    """
    return f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{volume_name}"
