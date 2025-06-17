"""Utility helpers for Databricks Database Instances API.

This module wraps :py:meth:`databricks.sdk.WorkspaceClient.database.generate_database_credential` with a simple
function so other parts of the codebase (or notebooks) can obtain a temporary
credential token in one line.

API reference:
https://databricks-sdk-py.readthedocs.io/en/latest/workspace/database/database.html#databricks.sdk.service.database.DatabaseAPI.generate_database_credential
"""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from databricks.sdk.service.database import DatabaseCredential

from ..config.workspace_client import get_workspace_client


def generate_database_credential(
    *,
    instance_names: Optional[List[str]] = None,
    request_id: Optional[str] = None,
) -> DatabaseCredential:
    """Request a scoped temporary credential for Databricks *Database Instances*.

    Parameters
    ----------
    instance_names
        Optional list of database instance names the credential should be scoped
        to.  If ``None`` the credential will be usable for *all* instances the
        caller has access to.
    request_id
        Optional client-side idempotency token.  If omitted a UUID4 string is
        generated automatically.

    Returns
    -------
    databricks.sdk.service.database.DatabaseCredential
        The credential object returned by the Workspace API.  The actual secret
        token is in ``credential`` (string).
    """

    client = get_workspace_client()
    if request_id is None:
        request_id = f"cred-{uuid.uuid4()}"

    db_api = client.database  # pylint: disable=maybe-no-member (SDK attribute)

    credential = db_api.generate_database_credential(
        instance_names=instance_names,
        request_id=request_id,
    )

    expires_at = getattr(credential, "expiration_time", None)
    if expires_at:
        expires_human = datetime.datetime.fromtimestamp(expires_at / 1000).isoformat()
        print(f"Generated credential token valid until {expires_human}")
    else:
        print("Generated credential token (no expiry info returned)")

    return credential 