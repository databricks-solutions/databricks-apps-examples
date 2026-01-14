"""
MCP Server API Client for UI App.

This module provides a clean interface to the MCP server backend.
All data operations should go through this client - no direct database access!

Architecture:
    ui_app (Dash frontend) --> mcp_client --> MCP Server --> Database

Benefits:
    - Single source of truth for data operations
    - Centralized error handling
    - Easy to mock for testing
    - Clear separation of concerns

Authentication:
    Uses WorkspaceClient for automatic OAuth token management.
    Databricks Apps service principals authenticate automatically via system auth.
"""

import os
import datetime
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError


# =============================================================================
# Configuration
# =============================================================================

REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3  # Number of retries for transient failures
RETRY_DELAY = 1.0  # Initial delay between retries (seconds)

# Cache WorkspaceClient for reuse (singleton pattern)
_workspace_client = None


def _get_mcp_url() -> str:
    """Get MCP server URL from environment"""
    return os.environ.get("MCP_SERVER_URL", "http://localhost:9000")


def _log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [MCP Client] {message}")


def _get_workspace_client():
    """
    Get or create cached WorkspaceClient.
    
    In Databricks Apps, WorkspaceClient() automatically uses the app's
    service principal identity (system auth) - no credentials needed.
    """
    global _workspace_client
    if _workspace_client is None:
        from databricks.sdk import WorkspaceClient
        _workspace_client = WorkspaceClient()
        _log("✓ Initialized WorkspaceClient (system auth)")
    return _workspace_client


def _get_auth_headers() -> Dict[str, str]:
    """
    Get authentication headers for app-to-app communication.
    
    Uses WorkspaceClient.config.authenticate() which is the recommended
    pattern for Databricks app-to-app calls. The SDK handles OAuth
    token acquisition and refresh automatically.
    """
    mcp_url = _get_mcp_url()
    
    # Skip auth for localhost development
    if "localhost" in mcp_url or "127.0.0.1" in mcp_url:
        _log("→ Localhost detected, skipping auth")
        return {}
    
    try:
        ws = _get_workspace_client()
        
        # Use config.authenticate() - the recommended SDK pattern
        # This returns a dict with Authorization header
        auth_headers = ws.config.authenticate()
        
        if auth_headers and isinstance(auth_headers, dict):
            _log("✓ Got auth headers via WorkspaceClient.config.authenticate()")
            return auth_headers
        
        _log("⚠️ WorkspaceClient.config.authenticate() returned empty headers")
        return {}
        
    except Exception as e:
        _log(f"❌ Auth error: {e}")
        return {}


# =============================================================================
# Response Types
# =============================================================================

@dataclass
class APIResponse:
    """Standard API response wrapper"""
    success: bool
    data: Any
    error: Optional[str] = None
    source: str = "mcp-server"


# =============================================================================
# Validation Operations
# =============================================================================

def validate_data(data: List[Dict[str, Any]]) -> APIResponse:
    """
    Validate grid data via MCP server.
    
    Args:
        data: List of SKU records to validate
        
    Returns:
        APIResponse with validation results
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 POST /api/validate - {len(data)} records")
    
    try:
        headers = _get_auth_headers() or {}
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{mcp_url}/api/validate",
            json={"data": data},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        
        result = response.json()
        _log(f"✓ Validation result: valid={result.get('valid')}, errors={result.get('has_errors')}, warnings={result.get('has_warnings')}")
        
        return APIResponse(
            success=True,
            data=result,
            source="mcp-server"
        )
        
    except Timeout:
        _log(f"⏱️ Validation request timed out after {REQUEST_TIMEOUT}s")
        return APIResponse(
            success=False,
            data=None,
            error=f"Validation request timed out after {REQUEST_TIMEOUT}s",
            source="timeout"
        )
    except ConnectionError as e:
        _log(f"🔌 Connection error: {e}")
        return APIResponse(
            success=False,
            data=None,
            error=f"Could not connect to MCP server at {mcp_url}",
            source="connection-error"
        )
    except RequestException as e:
        _log(f"❌ Validation failed: {e}")
        return APIResponse(
            success=False,
            data=None,
            error=str(e),
            source="error"
        )


# =============================================================================
# SKU Data Operations
# =============================================================================

def get_skus(category: Optional[str] = None, limit: Optional[int] = None) -> APIResponse:
    """
    Fetch SKU data from MCP server.
    
    Args:
        category: Filter by category (None or "All" for all)
        limit: Maximum records to return
        
    Returns:
        APIResponse with list of SKU records
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 GET /api/skus - category: {category}, limit: {limit}")
    
    try:
        headers = _get_auth_headers() or {}
        params = {}
        if category and category != "All":
            params["category"] = category
        if limit:
            params["limit"] = limit
        
        response = requests.get(
            f"{mcp_url}/api/skus",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        _log(f"✓ Got {result.get('count', 0)} SKUs from {result.get('source', 'unknown')}")
        return APIResponse(
            success=True,
            data=result.get("skus", []),
            source=result.get("source", "mcp-server")
        )
        
    except ConnectionError:
        _log(f"⚠️ MCP server not available at {mcp_url}")
        return APIResponse(success=False, data=[], error="MCP server unavailable")
    except Timeout:
        _log(f"⚠️ Request timeout to MCP server")
        return APIResponse(success=False, data=[], error="Request timeout")
    except RequestException as e:
        _log(f"❌ API error: {e}")
        return APIResponse(success=False, data=[], error=str(e))


def save_skus(records: List[Dict[str, Any]], overwrite: bool = False) -> APIResponse:
    """
    Save SKU data to MCP server.
    
    Args:
        records: List of SKU records to save
        overwrite: If True, replaces all existing data
        
    Returns:
        APIResponse with save result
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 POST /api/skus - {len(records)} records, overwrite: {overwrite}")
    
    try:
        headers = _get_auth_headers() or {}
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{mcp_url}/api/skus",
            json={"records": records, "overwrite": overwrite},
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        _log(f"✓ Saved {result.get('rows_affected', 0)} records")
        return APIResponse(success=True, data=result)
        
    except RequestException as e:
        _log(f"❌ Save error: {e}")
        return APIResponse(success=False, data={}, error=str(e))


def get_categories() -> APIResponse:
    """
    Fetch category list from MCP server.
    
    Returns:
        APIResponse with list of categories
    """
    mcp_url = _get_mcp_url()
    _log("📡 GET /api/categories")
    
    try:
        headers = _get_auth_headers() or {}
        
        response = requests.get(
            f"{mcp_url}/api/categories",
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        categories = result.get("categories", [])
        _log(f"✓ Got {len(categories)} categories")
        return APIResponse(success=True, data=categories)
        
    except RequestException as e:
        _log(f"❌ Error: {e}")
        return APIResponse(success=False, data=[{"name": "All", "count": 0}], error=str(e))


# =============================================================================
# Optimization Run Operations
# =============================================================================

def get_optimization_runs(limit: int = 20) -> APIResponse:
    """
    Fetch list of optimization runs from MCP server.
    
    Includes retry logic for transient failures (e.g., server starting up).
    
    Args:
        limit: Maximum runs to return
        
    Returns:
        APIResponse with list of run IDs
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 GET /api/optimization-runs - limit: {limit}")
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            headers = _get_auth_headers() or {}
            
            response = requests.get(
                f"{mcp_url}/api/optimization-runs",
                params={"limit": limit},
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()
            
            runs = result.get("runs", [])
            _log(f"✓ Got {len(runs)} optimization runs")
            return APIResponse(success=True, data=runs)
            
        except requests.exceptions.HTTPError as e:
            # Retry on 500 errors (server may be starting up)
            if e.response.status_code == 500 and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                _log(f"⚠️ Got 500 error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
                last_error = e
                continue
            _log(f"❌ Error: {e}")
            return APIResponse(success=False, data=[], error=str(e))
        except ConnectionError as e:
            # Retry on connection errors (server may not be ready yet)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                _log(f"⚠️ Connection error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
                last_error = e
                continue
            _log(f"❌ Connection error: {e}")
            return APIResponse(success=False, data=[], error=str(e))
        except RequestException as e:
            _log(f"❌ Error: {e}")
            return APIResponse(success=False, data=[], error=str(e))
    
    # Exhausted all retries
    _log(f"❌ All {MAX_RETRIES} retries exhausted")
    return APIResponse(success=False, data=[], error=str(last_error) if last_error else "Max retries exceeded")


def get_optimization_results(run_id: str) -> APIResponse:
    """
    Fetch optimization results for a specific run.
    
    Args:
        run_id: The optimization run ID
        
    Returns:
        APIResponse with results and summary
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 GET /api/optimization-runs/{run_id}")
    
    try:
        headers = _get_auth_headers() or {}
        
        response = requests.get(
            f"{mcp_url}/api/optimization-runs/{run_id}",
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        count = result.get("count", 0)
        _log(f"✓ Got {count} results for run {run_id}")
        return APIResponse(success=True, data=result)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            _log(f"⚠️ No results found for run {run_id}")
            return APIResponse(success=False, data={}, error=f"No results for {run_id}")
        raise
    except RequestException as e:
        _log(f"❌ Error: {e}")
        return APIResponse(success=False, data={}, error=str(e))


def submit_optimization_run(records: List[Dict[str, Any]]) -> APIResponse:
    """
    Submit a new optimization run to MCP server.
    
    This saves the SKU data and triggers the optimization.
    
    Args:
        records: List of SKU records to optimize
        
    Returns:
        APIResponse with run_id and optimization status
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 POST /api/optimization-runs - {len(records)} SKUs")
    
    try:
        headers = _get_auth_headers() or {}
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{mcp_url}/api/optimization-runs",
            json={"records": records},
            headers=headers,
            timeout=60  # Longer timeout for optimization
        )
        response.raise_for_status()
        result = response.json()
        
        run_id = result.get("run_id", "unknown")
        status = result.get("optimization_status", "unknown")
        _log(f"✓ Submitted run {run_id}, status: {status}")
        return APIResponse(success=True, data=result)
        
    except RequestException as e:
        _log(f"❌ Error: {e}")
        return APIResponse(success=False, data={}, error=str(e))


# =============================================================================
# AI/Insights Operations (already use MCP, kept for consistency)
# =============================================================================

def get_insights(run_id: str) -> APIResponse:
    """
    Get AI-generated insights for an optimization run.
    
    Args:
        run_id: The optimization run ID
        
    Returns:
        APIResponse with insights text
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 POST /api/insights - run: {run_id}")
    
    try:
        headers = _get_auth_headers() or {}
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{mcp_url}/api/insights",
            json={"forecast_id": run_id},
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        _log(f"✓ Got insights: {len(result.get('insights', ''))} chars")
        return APIResponse(success=True, data=result)
        
    except RequestException as e:
        _log(f"❌ Error: {e}")
        return APIResponse(success=False, data={"insights": f"Error: {e}"}, error=str(e))


def chat(run_id: str, question: str, context: Optional[str] = None) -> APIResponse:
    """
    Send a chat message to the AI assistant.
    
    Args:
        run_id: The optimization run ID for context
        question: The user's question
        context: Optional previous context
        
    Returns:
        APIResponse with answer
    """
    mcp_url = _get_mcp_url()
    _log(f"📡 POST /api/chat - run: {run_id}")
    
    try:
        headers = _get_auth_headers() or {}
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{mcp_url}/api/chat",
            json={
                "forecast_id": run_id,
                "question": question,
                "context": context
            },
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        _log(f"✓ Got answer: {len(result.get('answer', ''))} chars")
        return APIResponse(success=True, data=result)
        
    except RequestException as e:
        _log(f"❌ Error: {e}")
        return APIResponse(
            success=False,
            data={"answer": f"Error connecting to AI: {e}"},
            error=str(e)
        )
