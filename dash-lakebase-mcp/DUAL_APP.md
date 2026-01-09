Here’s a clean pattern to run two separate Databricks Apps — one as your UI and one as your MCP server — and have them talk to each other securely.

Executive summary
Use a dedicated MCP app that hosts your MCP server over the streamable HTTP transport (for example via Starlette/FastAPI), and a separate UI app (Streamlit/Dash/React) that calls the MCP server over HTTPS using Databricks OAuth.  
1
2
App-to-app auth is automatic with the calling app’s service principal; grant the UI app’s service principal CAN USE permission on the MCP app. For per-user governance, pass the user token and honor it in the MCP app’s calls to Databricks APIs.  
3 sources
Architecture and flow
Two apps, two roles

UI App: Frontend (Streamlit/Dash/React) that brokers user interactions and calls the MCP server.  
6

MCP App: Hosts a custom MCP server (Model Context Protocol) behind an app URL, exposing tools to the UI or agents.  
1
7

Communication

HTTPS calls from the UI app to the MCP app. When one Databricks app calls another using the Databricks SDK, the SDK uses the UI app’s assigned service principal automatically (machine-to-machine OAuth).  
3

If you need on‑behalf‑of‑user (OBO) behavior, extract the user’s forwarded token in the UI app and pass it to the MCP app; in the MCP app, use that token for downstream Databricks operations to enforce Unity Catalog policies.  
5

Endpoints

MCP apps should expose a streamable HTTP MCP endpoint. Databricks’ guidance uses a path like “/mcp” on the app host.  
1
2

For non‑MCP REST APIs that your app exposes, use “/api/<endpoint>” and call them with a Bearer token.  
8
3

Security model

UI→MCP app calls require CAN USE on the MCP app for the UI app’s service principal (or org‑wide “Anyone in my organization can use”). No anonymous/public access.  
4
6

Each app has a dedicated service principal identity; credentials are injected and automatically used by the SDK (unified auth).  
5

Step‑by‑step setup
1) Build and deploy the MCP App
Implement an HTTP‑compatible MCP server (streamable HTTP transport), e.g., Starlette/FastAPI + mcp server library.  
1
2

Add minimal app config:

app.yaml: run the server process (uv run custom-server or python mcp_server.py). Apps listen on port 8000 by default; mount your MCP endpoint at “/mcp”.  
2
Deploy:

databricks apps create <name>, databricks sync, databricks apps deploy — then copy the app URL. The MCP endpoint is available at https://<app-url>/mcp.  
2
Optionally validate locally with OAuth via CLI/SDK and DatabricksMCPClient (see code below).  
2
7

2) Grant the UI App access to the MCP App
In the MCP app’s Permissions tab, add the UI app’s service principal with CAN USE. You can select service principals in the app’s permissions UI.  
4

Each Databricks app has an automatically provisioned service principal shown on its Authorization tab; that identity is used for app‑to‑app calls by default.  
5

3) Call the MCP App from the UI App
Default (app‑as‑app): Inside the UI app, use the Databricks SDK to authenticate automatically and call the MCP server with DatabricksMCPClient.  
3
2

On‑behalf‑of‑user (optional): Extract the inbound user token from the UI app request header “x-forwarded-access-token”; send it to the MCP app (e.g., as Authorization: Bearer …). In the MCP app, use that token for data/compute access, enforcing the end user’s UC policies.  
5

4) Networking considerations
If you use network policies, allow egress to the other app’s FQDN (*.databricksapps.com). For private ingress, configure front‑end private connectivity and conditional DNS for databricksapps.com.  
9
10
Code examples
A) UI App (Python) calling the MCP App with DatabricksMCPClient (recommended)
# UI app code (e.g., Streamlit/Dash) — app-as-app authentication
from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient

MCP_SERVER_URL = "https://<mcp-app-host>/mcp"  # from MCP app Overview page

# Uses the UI app's service principal automatically
wc = WorkspaceClient()
mcp = DatabricksMCPClient(server_url=MCP_SERVER_URL, workspace_client=wc)

# List MCP tools
tools = mcp.list_tools()
print("Available tools:", [t.name for t in tools])

# Call a tool by name with JSON args
result = mcp.call_tool("check-system-status", {"region": "ap-southeast-2"})
print("Result:", "".join([c.text for c in result.content]))
python

This leverages unified authentication; when one app calls another, the SDK uses the caller app’s service principal automatically.  
2
3

B) UI App performing OBO (user‑authorized) downstream actions
# In a Python UI app framework that exposes request context, extract the user token:
# Streamlit: st.context.headers.get('x-forwarded-access-token')
# Gradio: declare `request: gr.Request` and read request.headers
user_token = request.headers.get("x-forwarded-access-token")

# Forward the user token when calling the MCP app if you want the MCP app to enforce user-level UC policies.
import requests

MCP_SERVER_URL = "https://<mcp-app-host>/mcp"
headers = {"Authorization": f"Bearer {user_token}"}
# Example: your MCP client/server library may manage the streamable HTTP framing;
# the DatabricksMCPClient is preferred for protocol handling.
# For illustration, show a simple GET/POST if your MCP server offers helper endpoints.
resp = requests.get(f"{MCP_SERVER_URL}/health", headers=headers, timeout=30)
resp.raise_for_status()
python

Apps receive the user token in “x-forwarded-access-token”; pass it to the MCP app and use it server-side for DBSQL/model calls, applying the user’s UC permissions.  
5

C) Generic app‑to‑app REST call (non‑MCP endpoints)
# If your MCP app also exposes classic REST endpoints under /api/<endpoint>:
from databricks.sdk import WorkspaceClient
import requests

wc = WorkspaceClient()
headers = wc.config.authenticate()  # Bearer <token> for the UI app's service principal

resp = requests.get(
    "https://<mcp-app-host>/api/health",
    headers=headers,
    timeout=30
)
resp.raise_for_status()
print(resp.json())
python

API endpoints exposed under /api/... should be called with a Bearer token; the SDK provides headers via wc.config.authenticate().  
8
3

Configuration details you’ll likely need
MCP server requirements:

Implement streamable HTTP transport and expose an HTTP endpoint (recommended path “/mcp”).  
1
2

Databricks Apps default app port is 8000; configure app.yaml to run your server (for example with uv run).  
2

App URLs:

Each app has a fixed URL like https://<app-name>-<workspace-id>.<region>.databricksapps.com; you can’t change it after creation.  
11
Permissions:

Assign CAN USE to the UI app’s service principal on the MCP app; no public/anonymous access is supported.  
4
6
Auth models in your MCP app:

App authorization (service principal) and User authorization (OBO) are both supported; choose based on whether results must reflect per-user UC policies.  
5
Networking:

If egress restrictions are enabled, allow the MCP app’s FQDN and any external APIs it calls; consider private ingress (Front‑end Private Connectivity) for users.  
9
10
Gotchas and limitations
Apps aren’t public; only authenticated users in your Databricks account can access them. There’s no anonymous access.  
6

If you rely on OBO, your app must request the necessary OAuth scopes; otherwise you’ll see 401/403 errors despite valid tokens.  
3
5

MCP endpoints are not simple REST resources; use an MCP client (like DatabricksMCPClient) to handle the streamable HTTP protocol correctly.  
12
2

App URLs are immutable; to change, create a new app.  
13
11

Troubleshooting
401 Unauthorized: Verify your token is valid/not expired and includes required scopes; ensure you’re using OAuth (not raw Entra ID token without exchange), and that the endpoint path is correct.  
3

403 Forbidden: Ensure the UI app’s service principal has CAN USE permission on the MCP app, and any needed scopes are granted if using user authorization.  
4
3

404 Not Found: Confirm the correct app URL and that the app is running; check that the MCP path is “/mcp” (or the path you configured).  
2
3

Network errors: If you use network policies, allow *.databricksapps.com; verify private connectivity/DNS if you route ingress privately.  
9

References and further reading
Model Context Protocol on Databricks: managed vs external vs custom MCP servers, and where Databricks Apps fit.  
7
14

Host a custom MCP server as a Databricks App (steps, endpoint, code):  
1
2

Connect from one Databricks app to another using OAuth (token auth, troubleshooting):  
3

Apps key concepts, URLs, access model, limitations:  
6
11

Apps permissions (CAN USE/CAN MANAGE) and service principals:  
4
5

Apps networking (egress controls, private ingress, DNS):  
9
10

Databricks Apps product overview:  
15
16

Next step
If you share which cloud (AWS/Azure/GCP) and your UI framework (Streamlit/Dash/React), I can give you a copy‑paste starter that includes the right auth model (app‑as‑app vs on‑behalf‑of‑user), scopes, and a minimal MCP tool invocation. Would you like me to turn this into a well‑structured guide you can share with a customer or partner?