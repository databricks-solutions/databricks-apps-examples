"""
AI Assistant Component for Lakebase Inventory Intelligence.

Provides:
1. Key Insights panel - auto-generated insights at the top of results
2. AI Chat drawer - slide-out chat for questions
"""

from typing import List
import dash_mantine_components as dmc
from dash import html, dcc


# Suggested questions for users
SUGGESTED_QUESTIONS = [
    "🎯 Which SKUs need more facings?",
    "📊 Summarize the range recommendations",
    "💰 Top profit opportunities",
]


def render_key_insights() -> html.Div:
    """Render the Key Insights panel that appears at the top of results."""
    
    return html.Div(
        id="key-insights-container",
        children=[
            html.Div(
                style={"position": "relative"},
                children=[
                    # Loading overlay positioned inside
                    dmc.LoadingOverlay(
                        id="key-insights-loading",
                        visible=False,
                        loaderProps={"type": "bars", "color": "yellow"},
                        overlayProps={"radius": "md", "blur": 1},
                        zIndex=10,
                    ),
                    # Content
                    dmc.Paper(
                        [
                            dmc.Group(
                                [
                                    dmc.Group(
                                        [
                                            dmc.ThemeIcon(
                                                html.Span("💡", style={"fontSize": "16px"}),
                                                size="md",
                                                radius="md",
                                                variant="light",
                                                color="yellow",
                                            ),
                                            dmc.Text("Key Insights", fw=700, size="md"),
                                        ],
                                        gap="xs",
                                    ),
                                    dmc.Group([
                                        dmc.Badge(
                                            "MCP",
                                            color="green",
                                            variant="filled",
                                            size="sm",
                                            leftSection=html.Span("🔗", style={"fontSize": "10px"}),
                                        ),
                                        dmc.Badge("AI Generated", color="red", variant="dot", size="sm"),
                                    ], gap="xs"),
                                ],
                                justify="space-between",
                            ),
                            dmc.Space(h=12),
                            html.Div(
                                id="key-insights-content",
                                children=[
                                    dmc.Group([
                                        dmc.Loader(size="sm", color="green", type="bars"),
                                        dmc.Stack([
                                            dmc.Text("Querying MCP Server...", size="sm", fw=500),
                                            dmc.Text("get_optimization_results → llm_generate", size="xs", c="dimmed", ff="monospace"),
                                        ], gap=2),
                                    ], gap="sm"),
                                ],
                            ),
                        ],
                        p="md",
                        radius="md",
                        withBorder=True,
                        style={
                            "backgroundColor": "#fffef5",
                            "borderColor": "#ffd43b",
                            "borderWidth": "1px",
                        },
                    ),
                ],
            ),
        ],
        style={"display": "none", "marginBottom": "20px"},
    )


def render_ai_chat_button() -> dmc.Button:
    """Render the floating button to open AI chat."""
    return dmc.Button(
        [
            html.Span("🤖", style={"marginRight": "8px"}),
            "Ask AI Assistant",
        ],
        id="open-ai-chat-button",
        variant="gradient",
        gradient={"from": "#E21837", "to": "#ff6b6b", "deg": 135},
        radius="xl",
        size="md",
        style={
            "position": "fixed",
            "bottom": "24px",
            "right": "24px",
            "zIndex": 1000,
            "boxShadow": "0 4px 12px rgba(226, 24, 55, 0.3)",
        },
    )


def render_ai_chat_drawer() -> dmc.Drawer:
    """Render the AI chat as a slide-out drawer."""
    
    # Header with MCP branding
    header = dmc.Group(
        [
            dmc.Group(
                [
                    dmc.ThemeIcon(
                        html.Span("🤖", style={"fontSize": "18px"}),
                        size="lg",
                        radius="md",
                        variant="gradient",
                        gradient={"from": "#E21837", "to": "#ff6b6b", "deg": 135},
                    ),
                    dmc.Stack(
                        [
                            dmc.Text("AI Assistant", fw=700, size="md"),
                            dmc.Group([
                                dmc.Badge(
                                    "MCP",
                                    color="green",
                                    variant="filled",
                                    size="xs",
                                ),
                                dmc.Text("Powered by MCP Server", size="xs", c="dimmed"),
                            ], gap=4),
                        ],
                        gap=2,
                    ),
                ],
                gap="sm",
            ),
        ],
    )
    
    # Chat messages area with LoadingOverlay
    chat_area = html.Div(
        style={"position": "relative"},
        children=[
            dmc.LoadingOverlay(
                id="ai-chat-loading-overlay",
                visible=False,
                loaderProps={"type": "bars", "color": "red"},
                overlayProps={"radius": "sm", "blur": 2},
                zIndex=10,
            ),
            dmc.ScrollArea(
                id="ai-chat-scroll",
                h=380,
                type="hover",
                offsetScrollbars=True,
                children=html.Div(
                    id="ai-chat-messages",
                    children=[_welcome_message()],
                    style={"padding": "12px"},
                ),
            ),
        ],
    )
    
    # Quick action chips
    quick_actions = dmc.Group(
        [
            dmc.Chip(
                q,
                id={"type": "suggested-question", "index": i},
                size="xs",
                variant="outline",
                color="red",
            )
            for i, q in enumerate(SUGGESTED_QUESTIONS)
        ],
        gap="xs",
        style={"padding": "8px 0"},
    )
    
    # Input area with loading button
    input_area = dmc.Group(
        [
            dmc.TextInput(
                id="ai-chat-input",
                placeholder="Ask a question...",
                radius="xl",
                size="md",
                style={"flex": 1},
            ),
            dmc.Button(
                html.Span("➤", style={"fontSize": "16px"}),
                id="ai-chat-send",
                variant="gradient",
                gradient={"from": "#E21837", "to": "#ff6b6b"},
                radius="xl",
                size="md",
                loading=False,
                loaderProps={"type": "dots", "size": "sm"},
            ),
        ],
        gap="xs",
        style={"marginTop": "12px"},
    )
    
    # Typing indicator with MCP status - animated
    typing_indicator = html.Div(
        id="ai-typing-indicator",
        children=[
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Loader(size="sm", color="green", type="bars"),
                            dmc.Stack([
                                dmc.Text("Querying MCP Server...", size="sm", fw=600, c="green"),
                                dmc.Text("get_optimization_results → llm_chat", size="xs", c="dimmed", ff="monospace"),
                            ], gap=2),
                        ],
                        gap="md",
                    ),
                ],
                p="md",
                radius="md",
                withBorder=True,
                style={"backgroundColor": "#f0fdf4", "borderColor": "#86efac"},
            ),
        ],
        style={"display": "none", "padding": "8px 0"},
    )
    
    return dmc.Drawer(
        id="ai-chat-drawer",
        title=header,
        position="right",
        size="md",
        padding="md",
        zIndex=10000,
        children=[
            chat_area,
            typing_indicator,
            dmc.Text("Quick questions:", size="xs", c="dimmed", mt="sm"),
            quick_actions,
            input_area,
        ],
    )


def render_ai_assistant() -> html.Div:
    """Render the complete AI assistant (insights + drawer + button)."""
    
    # Stores
    forecast_store = dcc.Store(id="ai-forecast-context", storage_type="memory")
    chat_store = dcc.Store(id="ai-chat-history", storage_type="memory", data=[])
    
    # Hidden loading output for compatibility
    loading_output = html.Div(id="ai-loading-output", style={"display": "none"})
    
    return html.Div(
        id="ai-assistant-container",
        children=[
            forecast_store,
            chat_store,
            loading_output,
            render_key_insights(),
            render_ai_chat_button(),
            render_ai_chat_drawer(),
        ],
    )


def _welcome_message() -> html.Div:
    """Create the welcome message."""
    return html.Div(
        [
            dmc.Paper(
                [
                    dmc.Text(
                        "👋 Hi! Select an optimization run to get started.",
                        size="sm",
                        style={"lineHeight": 1.5},
                    ),
                ],
                p="md",
                radius="lg",
                style={"backgroundColor": "#f8f9fa", "maxWidth": "85%"},
            ),
        ],
        style={"marginBottom": "12px"},
    )


def create_message_bubble(role: str, content: str, timestamp: str = None) -> html.Div:
    """Create a modern chat message bubble."""
    is_user = role == "user"
    
    bubble_style = {
        "backgroundColor": "#E21837" if is_user else "#f8f9fa",
        "color": "#fff" if is_user else "#333",
        "maxWidth": "85%",
        "marginLeft": "auto" if is_user else "0",
    }
    
    return html.Div(
        [
            dmc.Paper(
                [
                    dmc.Text(
                        content,
                        size="sm",
                        style={"lineHeight": 1.6, "whiteSpace": "pre-wrap"},
                    ),
                ],
                p="md",
                radius="lg",
                style=bubble_style,
            ),
        ],
        style={
            "marginBottom": "12px",
            "display": "flex",
            "justifyContent": "flex-end" if is_user else "flex-start",
        },
    )


def create_insights_content(insights: str) -> html.Div:
    """Create the insights content from AI response."""
    # Split insights into bullet points if they contain them
    lines = insights.strip().split('\n')
    
    content = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('•') or line.startswith('-') or line.startswith('*'):
            # It's a bullet point
            text = line.lstrip('•-* ')
            content.append(
                dmc.Group(
                    [
                        dmc.ThemeIcon(
                            html.Span("→", style={"fontSize": "12px"}),
                            size="xs",
                            radius="xl",
                            variant="light",
                            color="red",
                        ),
                        dmc.Text(text, size="sm", style={"flex": 1}),
                    ],
                    gap="xs",
                    align="flex-start",
                    style={"marginBottom": "8px"},
                )
            )
        else:
            content.append(
                dmc.Text(line, size="sm", style={"marginBottom": "8px", "lineHeight": 1.5})
            )
    
    return html.Div(content)
