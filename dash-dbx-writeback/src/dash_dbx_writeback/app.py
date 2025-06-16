"""
Collapsible navbar on both desktop and mobile
"""

from typing import Dict, Any
import datetime
import inspect
import atexit
import dash

import dash_mantine_components as dmc
from dash import Dash, Input, Output, State, callback, _dash_renderer, html
from dash_iconify import DashIconify

from .config.workspace_client import close_connection


def log(message: str) -> None:
    """Print a log message with timestamp and function name"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    # Get the calling function name
    frame = inspect.currentframe()
    if frame and frame.f_back:
        func_name = frame.f_back.f_code.co_name
    else:
        func_name = "unknown"
    print(f"[{timestamp}] [{func_name}] {message}")


_dash_renderer._set_react_version("18.2.0")

log("=" * 60)
log("INITIALIZING DASH APP")
log("=" * 60)

# Create the app instance FIRST
app = Dash(
    name=__package__,
    external_stylesheets=dmc.styles.ALL,
    suppress_callback_exceptions=True,
    use_pages=True,
)

# Now import pages and callbacks AFTER app is created
from . import pages  # noqa: F401, E402
from .callbacks import input_callbacks, results_callbacks  # noqa: F401, E402

logo = "/assets/dbx.webp"


def get_icon(icon: str) -> DashIconify:
    return DashIconify(icon=icon, height=24)


def create_nav_links():
    """Create navigation links from the page registry"""
    nav_links = []

    # Get all registered pages
    for page in dash.page_registry.values():
        # Create appropriate icons for different pages
        if page["path"] == "/":
            icon = "material-symbols-light:house-outline-rounded"
            label = "Modify Data"
        elif page["path"] == "/about":
            icon = "material-symbols-light:info-outline"
            label = page["name"]
        elif page["path"] == "/results":
            icon = "material-symbols-light:data-thresholding-outline-sharp"
            label = page["name"]
        else:
            icon = "material-symbols-light:page"
            label = page["name"]

        nav_links.append(
            dmc.NavLink(
                label=label,
                leftSection=get_icon(icon=icon),
                href=page["path"],
            )
        )

    return nav_links


layout = dmc.AppShell(
    [
        dmc.AppShellHeader(
            children=[
                dmc.Group(
                    [
                        dmc.Burger(
                            id="mobile-burger",
                            size="sm",
                            hiddenFrom="sm",
                            opened=False,
                        ),
                        dmc.Burger(
                            id="desktop-burger",
                            size="sm",
                            visibleFrom="sm",
                            opened=True,
                        ),
                        dmc.Image(
                            src=logo,
                            h=50,
                            p=7,
                            fit="contain",
                            style={"imageRendering": "crisp-edges"},
                        ),
                        html.Div(
                            [
                                dmc.Text(
                                    "Excel the Dash Way",
                                    size="xl",
                                    fw=1000,
                                    c="#222",
                                    className="header-title",
                                ),
                                dmc.Text(
                                    "Writeback to Databricks like it was Excel",
                                    size="md",
                                    fw=900,
                                    c="#444",
                                    variant="gradient",
                                    gradient={"from": "red", "to": "blue", "deg": 45},
                                    className="header-subtitle",
                                ),
                            ],
                            style={
                                "display": "flex",
                                "flexDirection": "column",
                                "gap": "0px",
                            },
                        ),
                    ],
                    align="left",
                    gap="xs",
                    p=5,
                ),
            ]
        ),
        dmc.AppShellNavbar(
            id="navbar",
            children=create_nav_links(),
            p="md",
        ),
        dmc.AppShellMain(
            # The page content will be displayed here via dash.page_container
            dash.page_container
        ),
    ],
    header={"height": 70},
    navbar={
        "width": 300,
        "breakpoint": "sm",
        "collapsed": {"mobile": True, "desktop": False},
    },
    padding="md",
    id="appshell",
)

app.layout = dmc.MantineProvider(
    theme={
        "fontFamily": "Poppins, sans-serif",
        "components": {
            "Text": {
                "styles": {
                    "header-title": {
                        "root": {
                            "fontSize": "1.5rem",
                            "letterSpacing": "0.5px",
                            "lineHeight": "1.1",
                        }
                    },
                    "header-subtitle": {
                        "root": {
                            "fontSize": "1rem",
                            "letterSpacing": "0.3px",
                            "lineHeight": "1.4",
                            "fontStyle": "italic",
                        }
                    },
                }
            }
        },
    },
    children=layout,
)


@callback(
    Output("appshell", "navbar"),
    Input("mobile-burger", "opened"),
    Input("desktop-burger", "opened"),
    State("appshell", "navbar"),
)
def toggle_navbar(
    mobile_opened: bool, desktop_opened: bool, navbar: Dict[str, Any]
) -> Dict[str, Any]:
    log(f"CALLBACK: toggle_navbar - mobile: {mobile_opened}, desktop: {desktop_opened}")
    navbar["collapsed"] = {
        "mobile": not mobile_opened,
        "desktop": not desktop_opened,
    }
    return navbar


# Register cleanup function to close connection on app shutdown
atexit.register(close_connection)


if __name__ == "__main__":
    log("=" * 60)
    log("STARTING DASH APP SERVER")
    log("=" * 60)
    try:
        app.run(debug=True)
    finally:
        # Ensure connection is closed on shutdown
        close_connection()

