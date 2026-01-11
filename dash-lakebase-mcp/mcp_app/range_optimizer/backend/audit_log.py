"""
Audit logging for the Range Optimizer MCP server.

Logs application events (forecasts submitted, fetched, insights generated, etc.)
to a Lakebase PostgreSQL table for auditing and compliance purposes.
"""

import datetime
import uuid
from enum import Enum
from typing import Optional, Dict, Any
import json

import pandas as pd

from .config import db_config
from .logger import logger
from .database import bulk_insert, check_table_exists, execute_sql, get_workspace_client


class AuditEventType(str, Enum):
    """Types of auditable events in the application"""
    
    # Optimization events
    FORECAST_SUBMITTED = "forecast_submitted"
    FORECAST_FETCHED = "forecast_fetched"
    OPTIMIZATION_TRIGGERED = "optimization_triggered"
    OPTIMIZATION_COMPLETED = "optimization_completed"
    
    # Data access events
    SKUS_FETCHED = "skus_fetched"
    SKUS_SAVED = "skus_saved"
    CATEGORIES_FETCHED = "categories_fetched"
    
    # AI/Insights events
    INSIGHTS_GENERATED = "insights_generated"
    CHAT_MESSAGE_SENT = "chat_message_sent"
    
    # Validation events
    DATA_VALIDATED = "data_validated"


def _ensure_audit_table_exists() -> bool:
    """
    Ensure the audit log table exists, creating it if necessary.
    
    Table schema:
    - event_id: UUID primary key
    - event_type: Type of event (from AuditEventType enum)
    - event_timestamp: When the event occurred
    - user_id: User who triggered the event (if available)
    - user_email: User's email (if available)
    - run_id: Associated optimization run ID (if applicable)
    - request_path: API endpoint that was called
    - request_method: HTTP method (GET, POST, etc.)
    - sku_count: Number of SKUs involved (if applicable)
    - details: JSON blob with additional event-specific details
    - client_ip: Client IP address (if available)
    - user_agent: Client user agent (if available)
    """
    table_name = db_config.audit_log_table
    
    if check_table_exists(table_name):
        return True
    
    logger.info(f"Creating audit log table: {table_name}")
    
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        event_timestamp TIMESTAMP NOT NULL,
        user_id TEXT,
        user_email TEXT,
        run_id TEXT,
        request_path TEXT,
        request_method TEXT,
        sku_count INTEGER,
        details TEXT,
        client_ip TEXT,
        user_agent TEXT
    )
    """
    
    success = execute_sql(create_sql)
    
    if success:
        # Create indexes for common query patterns
        index_sqls = [
            f'CREATE INDEX IF NOT EXISTS idx_audit_event_type ON {table_name}(event_type)',
            f'CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON {table_name}(event_timestamp)',
            f'CREATE INDEX IF NOT EXISTS idx_audit_user ON {table_name}(user_email)',
            f'CREATE INDEX IF NOT EXISTS idx_audit_run ON {table_name}(run_id)',
        ]
        for idx_sql in index_sqls:
            execute_sql(idx_sql)
        
        logger.info(f"Audit log table created successfully: {table_name}")
    else:
        logger.error(f"Failed to create audit log table: {table_name}")
    
    return success


def _get_current_user() -> tuple[Optional[str], Optional[str]]:
    """
    Get the current user's ID and email from Databricks SDK.
    
    Returns:
        Tuple of (user_id, user_email), either may be None if not available.
    """
    try:
        w = get_workspace_client()
        me = w.current_user.me()
        return me.id, me.user_name
    except Exception as e:
        logger.debug(f"Could not get current user: {e}")
        return None, None


def log_event(
    event_type: AuditEventType,
    run_id: Optional[str] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None,
    sku_count: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """
    Log an audit event to the database.
    
    Args:
        event_type: Type of event from AuditEventType enum
        run_id: Associated optimization run ID (if applicable)
        request_path: API endpoint that was called
        request_method: HTTP method (GET, POST, etc.)
        sku_count: Number of SKUs involved (if applicable)
        details: Additional event-specific details as dict
        client_ip: Client IP address (if available)
        user_agent: Client user agent (if available)
        user_email: Override for user email (if known from request headers)
    
    Returns:
        True if event was logged successfully, False otherwise.
    """
    try:
        # Ensure table exists
        if not _ensure_audit_table_exists():
            logger.warning("Audit table not available, skipping event logging")
            return False
        
        # Get current user if not provided
        user_id, detected_email = _get_current_user()
        if not user_email:
            user_email = detected_email
        
        # Generate event record
        event_id = str(uuid.uuid4())
        event_timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        # Serialize details to JSON
        details_json = json.dumps(details) if details else None
        
        # Create DataFrame for bulk_insert
        df = pd.DataFrame([{
            "event_id": event_id,
            "event_type": event_type.value,
            "event_timestamp": event_timestamp.isoformat(),
            "user_id": user_id,
            "user_email": user_email,
            "run_id": run_id,
            "request_path": request_path,
            "request_method": request_method,
            "sku_count": sku_count,
            "details": details_json,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }])
        
        # Insert the event
        rows = bulk_insert(db_config.audit_log_table, df, overwrite=False)
        
        logger.debug(f"Audit event logged: {event_type.value} for run {run_id}")
        return rows > 0
        
    except Exception as e:
        # Don't let audit logging failures break the main application flow
        logger.warning(f"Failed to log audit event {event_type.value}: {e}")
        return False


def log_forecast_submitted(
    run_id: str,
    sku_count: int,
    request_path: str = "/api/optimization-runs",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log a forecast submission event."""
    return log_event(
        event_type=AuditEventType.FORECAST_SUBMITTED,
        run_id=run_id,
        request_path=request_path,
        request_method="POST",
        sku_count=sku_count,
        details={"action": "submit_optimization_run"},
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )


def log_forecast_fetched(
    run_id: str,
    sku_count: int,
    request_path: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log a forecast fetch event."""
    return log_event(
        event_type=AuditEventType.FORECAST_FETCHED,
        run_id=run_id,
        request_path=request_path or f"/api/optimization-runs/{run_id}",
        request_method="GET",
        sku_count=sku_count,
        details={"action": "fetch_optimization_results"},
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )


def log_insights_generated(
    run_id: str,
    source: str,
    request_path: str = "/api/insights",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log an insights generation event."""
    return log_event(
        event_type=AuditEventType.INSIGHTS_GENERATED,
        run_id=run_id,
        request_path=request_path,
        request_method="POST",
        details={"source": source, "action": "generate_insights"},
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )


def log_chat_message(
    run_id: str,
    question: str,
    source: str,
    request_path: str = "/api/chat",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log a chat message event."""
    # Truncate question for storage (keep first 500 chars)
    truncated_question = question[:500] if len(question) > 500 else question
    
    return log_event(
        event_type=AuditEventType.CHAT_MESSAGE_SENT,
        run_id=run_id,
        request_path=request_path,
        request_method="POST",
        details={
            "question_preview": truncated_question,
            "question_length": len(question),
            "source": source,
            "action": "chat",
        },
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )


def log_skus_fetched(
    sku_count: int,
    category: Optional[str] = None,
    source: str = "database",
    request_path: str = "/api/skus",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log SKU fetch events."""
    return log_event(
        event_type=AuditEventType.SKUS_FETCHED,
        request_path=request_path,
        request_method="GET",
        sku_count=sku_count,
        details={
            "category_filter": category,
            "source": source,
            "action": "fetch_skus",
        },
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )


def log_skus_saved(
    sku_count: int,
    overwrite: bool = False,
    request_path: str = "/api/skus",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Convenience function to log SKU save events."""
    return log_event(
        event_type=AuditEventType.SKUS_SAVED,
        request_path=request_path,
        request_method="POST",
        sku_count=sku_count,
        details={
            "overwrite": overwrite,
            "action": "save_skus",
        },
        client_ip=client_ip,
        user_agent=user_agent,
        user_email=user_email,
    )
