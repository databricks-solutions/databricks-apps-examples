"""
Callbacks for the AI Assistant component.

Connects to the MCP Server for insights and chat functionality.
All operations go through the MCP client module.
"""

import datetime
from typing import List, Dict, Tuple

import dash_mantine_components as dmc
from dash import Input, Output, State, callback, ALL, html, callback_context

# Use MCP client for all operations
from ..mcp_client import get_insights, chat

from ..components.ai_assistant import (
    create_message_bubble,
    create_insights_content,
    SUGGESTED_QUESTIONS,
)


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [AI] {message}")


# =============================================================================
# Toggle AI Drawer
# =============================================================================

@callback(
    Output("ai-chat-drawer", "opened"),
    Input("open-ai-chat-button", "n_clicks"),
    State("ai-chat-drawer", "opened"),
    prevent_initial_call=True,
)
def toggle_ai_drawer(n_clicks: int, is_opened: bool) -> bool:
    """Toggle the AI chat drawer open/closed."""
    log(f"CALLBACK: toggle_ai_drawer - clicks: {n_clicks}, currently: {is_opened}")
    return not is_opened


# =============================================================================
# Update AI Context on Run Selection (via MCP)
# =============================================================================

@callback(
    Output("ai-forecast-context", "data"),
    Output("ai-chat-messages", "children", allow_duplicate=True),
    Output("key-insights-container", "style"),
    Output("key-insights-content", "children"),
    Output("key-insights-loading", "visible"),
    Input("optimization-forecast-select", "value"),
    prevent_initial_call=True,
    running=[
        (Output("key-insights-loading", "visible"), True, False),
    ],
)
def update_ai_on_forecast_select(
    selected_run: str,
) -> Tuple[Dict, List, Dict, html.Div, bool]:
    """
    Update AI context and generate key insights when run is selected.
    Uses MCP client for insights generation.
    """
    log(f"CALLBACK: update_ai_on_forecast_select - run: {selected_run}")
    
    hidden_style = {"display": "none", "marginBottom": "20px"}
    visible_style = {"display": "block", "marginBottom": "20px"}
    
    # Default welcome message
    welcome = create_message_bubble(
        "assistant",
        "👋 Hi! Select an optimization run to get started."
    )
    
    if not selected_run:
        loading_skeleton = html.Div([
            dmc.Text("Select an optimization run to see AI-generated insights", size="sm", c="dimmed"),
        ])
        return {}, [welcome], hidden_style, loading_skeleton, False
    
    # Call MCP Server for insights
    log(f"🚀 Requesting insights from MCP for run: {selected_run}")
    response = get_insights(selected_run)
    
    # Build insights content
    if not response.success or response.data.get("error"):
        insights_content = html.Div([
            dmc.Alert(
                response.error or response.data.get("insights", "Error"),
                title="MCP Server Issue",
                color="yellow",
            )
        ])
    else:
        insights_text = response.data.get("insights", "")
        tools_used = response.data.get("tools_used", [])
        source = response.data.get("source", "unknown")
        
        insights_content = html.Div([
            create_insights_content(insights_text),
            dmc.Space(h=12),
            dmc.Group([
                dmc.Badge(
                    "via MCP Server" if source == "mcp-server" else source,
                    color="green" if source == "mcp-server" else "yellow",
                    variant="light",
                    size="sm",
                    leftSection=html.Span("🔗", style={"fontSize": "10px"}),
                ),
                dmc.Text(
                    f"Tools: {' → '.join(tools_used)}" if tools_used else "",
                    size="xs",
                    c="dimmed",
                    ff="monospace",
                ),
            ], gap="xs"),
        ])
    
    # Ready message for chat
    ready_message = create_message_bubble(
        "assistant",
        f"✅ Connected to MCP Server!\n\nOptimization run {selected_run} loaded.\nAsk me about facings changes, range recommendations, or profit analysis!"
    )
    
    return {
        "forecast_id": selected_run,
        "context": response.data.get("insights", ""),
    }, [ready_message], visible_style, insights_content, False


# =============================================================================
# Handle Chat Messages (via MCP)
# =============================================================================

@callback(
    Output("ai-chat-messages", "children"),
    Output("ai-chat-input", "value"),
    Output("ai-chat-history", "data"),
    Output("ai-typing-indicator", "style"),
    Output("ai-chat-send", "loading"),
    Output("ai-chat-loading-overlay", "visible"),
    Input("ai-chat-send", "n_clicks"),
    Input({"type": "suggested-question", "index": ALL}, "checked"),
    Input("ai-chat-input", "n_submit"),
    State("ai-chat-input", "value"),
    State("ai-chat-messages", "children"),
    State("ai-chat-history", "data"),
    State("ai-forecast-context", "data"),
    prevent_initial_call=True,
    running=[
        (Output("ai-typing-indicator", "style"), {"display": "block", "padding": "8px 0"}, {"display": "none"}),
        (Output("ai-chat-send", "loading"), True, False),
        (Output("ai-chat-input", "disabled"), True, False),
        (Output("ai-chat-loading-overlay", "visible"), True, False),
    ],
)
def handle_chat_message(
    send_clicks: int,
    suggested_checked: List[bool],
    n_submit: int,
    input_value: str,
    current_messages: List,
    chat_history: List[Dict],
    forecast_context: Dict,
) -> Tuple[List, str, List[Dict], Dict, bool, bool]:
    """
    Handle chat messages - calls MCP Server via client.
    """
    ctx = callback_context
    log(f"CALLBACK: handle_chat_message - triggered: {ctx.triggered_id}")
    
    hide_typing = {"display": "none"}
    
    # Determine the question
    question = None
    
    if ctx.triggered_id in ["ai-chat-send", "ai-chat-input"] and input_value:
        question = input_value.strip()
    elif isinstance(ctx.triggered_id, dict) and ctx.triggered_id.get("type") == "suggested-question":
        index = ctx.triggered_id.get("index", 0)
        if index < len(SUGGESTED_QUESTIONS):
            raw = SUGGESTED_QUESTIONS[index]
            question = raw.split(" ", 1)[-1] if " " in raw else raw
    
    if not question:
        return current_messages or [], input_value or "", chat_history or [], hide_typing, False, False
    
    log(f"💬 Processing: {question[:50]}...")
    
    # Add user message
    user_bubble = create_message_bubble("user", question)
    messages_with_user = (current_messages or []) + [user_bubble]
    
    # Get forecast context
    run_id = forecast_context.get("forecast_id", "unknown") if forecast_context else "unknown"
    context = forecast_context.get("context", "") if forecast_context else ""
    
    # Call MCP Server via client
    log(f"📡 Sending to MCP Server...")
    response = chat(run_id, question, context)
    
    # Build response
    answer = response.data.get("answer", "No response received")
    tools_used = response.data.get("tools_used", [])
    source = response.data.get("source", "unknown")
    
    # Add MCP badge to response
    if source == "mcp-server":
        answer_with_badge = f"{answer}\n\n─────\n🔗 via MCP Server | Tools: {', '.join(tools_used)}"
    else:
        answer_with_badge = f"{answer}\n\n─────\n⚠️ {source}"
    
    ai_bubble = create_message_bubble("assistant", answer_with_badge)
    
    # Update messages
    new_messages = messages_with_user + [ai_bubble]
    
    # Update history
    new_history = (chat_history or []) + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer, "source": source, "tools": tools_used},
    ]
    
    log(f"✅ Response received - {len(answer)} chars (source: {source})")
    
    return new_messages, "", new_history, hide_typing, False, False
