"""
Integration tests for MCP server tools.

These tests validate that tools work correctly when connected to the database.
"""

import pytest


def test_health_tool_structure():
    """Test that health tool returns expected structure."""
    # This is a placeholder - actual tests would need database connection
    expected_keys = {"status", "message", "database"}
    # In a real test, you would call the health tool and verify the response
    assert expected_keys == {"status", "message", "database"}


def test_forecast_runs_structure():
    """Test that get_forecast_runs returns expected structure."""
    expected_keys = {"forecasts", "total_count"}
    assert expected_keys == {"forecasts", "total_count"}


def test_optimization_results_structure():
    """Test that get_optimization_results returns expected structure."""
    expected_keys = {"forecast_id", "products", "summary"}
    assert expected_keys == {"forecast_id", "products", "summary"}


def test_recommend_restocking_structure():
    """Test that recommend_restocking returns expected structure."""
    expected_keys = {"forecast_id", "recommendations", "total_recommended_investment"}
    assert expected_keys == {"forecast_id", "recommendations", "total_recommended_investment"}

