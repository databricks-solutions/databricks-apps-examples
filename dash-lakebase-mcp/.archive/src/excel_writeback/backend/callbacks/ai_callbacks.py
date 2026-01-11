"""
Callbacks for the AI Assistant component.

Connects to the MCP Server for insights and chat functionality.
"""

import datetime
import os
import requests
from typing import List, Dict, Tuple

import dash_mantine_components as dmc
from dash import Input, Output, State, callback, ALL, html, no_update, callback_context, dcc

from ..components.ai_assistant import (
    create_message_bubble,
    create_insights_content,
    SUGGESTED_QUESTIONS,
)


# MCP Server URL - can be overridden by environment variable
MCP_SERVER_URL = os.environ.get(
    "MCP_SERVER_URL",
    "http://localhost:9000"  # Default for local development
)


def log(message: str) -> None:
    """Print a log message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [AI] {message}")


def call_mcp_insights(forecast_id: str) -> dict:
    """Call the MCP Server to generate insights."""
    log(f"📡 Calling MCP Server: /api/insights for {forecast_id}")
    
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/api/insights",
            json={"forecast_id": forecast_id},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        log(f"✅ MCP Server response: {len(result.get('insights', ''))} chars")
        return result
    except requests.exceptions.ConnectionError:
        log(f"⚠️ MCP Server not available at {MCP_SERVER_URL}")
        return {
            "forecast_id": forecast_id,
            "insights": "MCP Server is not available. Running in fallback mode.",
            "source": "fallback",
            "error": "connection_error"
        }
    except Exception as e:
        log(f"❌ MCP Server error: {e}")
        return {
            "forecast_id": forecast_id,
            "insights": f"Error connecting to MCP Server: {str(e)}",
            "source": "error",
            "error": str(e)
        }


def call_mcp_chat(forecast_id: str, question: str, context: str = None) -> dict:
    """Call the MCP Server for chat responses."""
    log(f"📡 Calling MCP Server: /api/chat for {forecast_id}")
    log(f"   Question: {question[:50]}...")
    
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/api/chat",
            json={
                "forecast_id": forecast_id,
                "question": question,
                "context": context
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        log(f"✅ MCP Server response: {len(result.get('answer', ''))} chars")
        return result
    except requests.exceptions.ConnectionError:
        log(f"⚠️ MCP Server not available at {MCP_SERVER_URL}")
        return {
            "forecast_id": forecast_id,
            "question": question,
            "answer": "MCP Server is not available. Please ensure the MCP Server is running.",
            "source": "fallback",
            "error": "connection_error"
        }
    except Exception as e:
        log(f"❌ MCP Server error: {e}")
        return {
            "forecast_id": forecast_id,
            "question": question,
            "answer": f"Error connecting to MCP Server: {str(e)}",
            "source": "error",
            "error": str(e)
        }


# =============================================================================
# Callbacks
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
    selected_forecast: str,
) -> Tuple[Dict, List, Dict, html.Div, bool]:
    """Update AI context and generate key insights when forecast is selected."""
    log(f"CALLBACK: update_ai_on_forecast_select - forecast: {selected_forecast}")
    
    hidden_style = {"display": "none", "marginBottom": "20px"}
    visible_style = {"display": "block", "marginBottom": "20px"}
    
    # Default welcome message
    welcome = create_message_bubble(
        "assistant",
        "👋 Hi! Select a forecast to get started."
    )
    
    if not selected_forecast:
        loading_skeleton = html.Div([
            dmc.Text("Select a forecast to see AI-generated insights", size="sm", c="dimmed"),
        ])
        return {}, [welcome], hidden_style, loading_skeleton, False
    
    # Call MCP Server for insights
    log(f"🚀 Requesting insights from MCP Server for {selected_forecast}")
    mcp_response = call_mcp_insights(selected_forecast)
    
    # Build insights content with MCP badge
    if mcp_response.get("error"):
        insights_content = html.Div([
            dmc.Alert(
                mcp_response.get("insights", "Error"),
                title="MCP Server Unavailable",
                color="yellow",
            )
        ])
    else:
        insights_text = mcp_response.get("insights", "")
        tools_used = mcp_response.get("tools_used", [])
        
        insights_content = html.Div([
            create_insights_content(insights_text),
            dmc.Space(h=12),
            dmc.Group([
                dmc.Badge(
                    "via MCP Server",
                    color="green",
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
        f"✅ Connected to MCP Server!\n\nForecast {selected_forecast} loaded.\nAsk me about restocking priorities, profit analysis, or anything else!"
    )
    
    return {
        "forecast_id": selected_forecast,
        "context": mcp_response.get("insights", ""),
    }, [ready_message], visible_style, insights_content, False


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
    """Handle chat messages - calls MCP Server for responses."""
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
    forecast_id = forecast_context.get("forecast_id", "unknown") if forecast_context else "unknown"
    context = forecast_context.get("context", "") if forecast_context else ""
    
    # Call MCP Server (this is the slow part)
    log(f"📡 Sending to MCP Server...")
    mcp_response = call_mcp_chat(forecast_id, question, context)
    
    # Build response
    answer = mcp_response.get("answer", "No response received")
    tools_used = mcp_response.get("tools_used", [])
    source = mcp_response.get("source", "unknown")
    
    # Add MCP badge
    if source == "mcp-server":
        answer_with_badge = f"{answer}\n\n─────\n🔗 via MCP Server | Tools: {', '.join(tools_used)}"
    else:
        answer_with_badge = f"{answer}\n\n─────\n⚠️ Fallback mode"
    
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
