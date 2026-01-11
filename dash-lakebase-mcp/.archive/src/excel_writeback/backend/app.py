"""
FastAPI application for Excel Writeback with Dash UI.

Serves:
- Dash UI at root / 
- REST API at /api

Note: MCP server runs as a separate application for security isolation.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from .config import conf
from .router import api
from .logger import logger
from .database import initialize_connection_pool, close_all_connections
from contextlib import asynccontextmanager

# Get the backend directory for Dash pages/assets
BACKEND_DIR = Path(__file__).parent

# Global reference to Dash app
_dash_app = None


def create_dash_app():
    """Create and configure the Dash application"""
    import dash_mantine_components as dmc
    from dash import Dash, _dash_renderer, html, dcc, page_container, page_registry, DiskcacheManager
    from dash_iconify import DashIconify
    import diskcache
    
    # Set React version for Mantine compatibility
    _dash_renderer._set_react_version("18.2.0")
    
    # Create cache for background callbacks
    cache_dir = BACKEND_DIR / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache = diskcache.Cache(str(cache_dir))
    background_callback_manager = DiskcacheManager(cache)
    
    logger.info(f"Creating Dash app with pages_folder: {BACKEND_DIR / 'pages'}")
    logger.info(f"Assets folder: {BACKEND_DIR / 'assets'}")
    
    # Create Dash app - serve at root
    dash_app = Dash(
        name="range_optimizer_dash",
        external_stylesheets=dmc.styles.ALL,
        suppress_callback_exceptions=True,
        use_pages=True,
        pages_folder=str(BACKEND_DIR / "pages"),
        assets_folder=str(BACKEND_DIR / "assets"),
        background_callback_manager=background_callback_manager,
        requests_pathname_prefix="/",
    )
    
    # Import callbacks AFTER app is created (they register themselves)
    from . import callbacks  # noqa: F401
    
    def get_icon(icon: str) -> DashIconify:
        return DashIconify(icon=icon, height=24)
    
    # Create navigation links from page registry
    nav_links = []
    page_order = ["Home", "Stock Optimization", "About"]
    ordered_pages = sorted(
        page_registry.values(),
        key=lambda x: page_order.index(x["name"]) if x["name"] in page_order else 999
    )
    
    for page in ordered_pages:
        nav_links.append(
            dmc.NavLink(
                label=page["name"],
                leftSection=get_icon(icon=page.get("icon", "lucide:home")),
                href=page["relative_path"],
                active="partial",
            )
        )
    
    # App layout with Mantine shell
    dash_app.layout = dmc.MantineProvider(
        theme=dmc.DEFAULT_THEME,
        children=[
            dmc.AppShell(
                [
                    dmc.AppShellNavbar(
                        id="navbar",
                        children=[
                            html.Div(
                                html.Img(
                                    src=dash_app.get_asset_url("dbx.webp"),
                                    style={"height": 40},
                                ),
                                style={
                                    "display": "flex",
                                    "justifyContent": "center",
                                    "width": "100%",
                                    "marginTop": "1.5rem",
                                    "marginBottom": "1.5rem",
                                },
                            ),
                            *nav_links,
                        ],
                        p="lg",
                    ),
                    dmc.AppShellMain(
                        id="main",
                        children=[
                            dcc.Location(id="url", refresh=False),
                            page_container,
                        ],
                    ),
                ],
                header={"collapsed": True},
                padding="lg",
                navbar={
                    "width": 280,
                    "breakpoint": "sm",
                    "collapsed": {"mobile": True},
                },
                id="appshell",
            ),
        ],
    )
    
    return dash_app


# Create FastAPI app (without lifespan first)
app = FastAPI(title=conf.app_name)

# Include API router FIRST (so /api/* routes take precedence)
app.include_router(api)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global _dash_app
    
    logger.info(f"Starting {conf.app_name}")
    logger.info(f"Configuration:\n{conf.model_dump_json(indent=2)}")
    
    # Initialize database connection pool
    if not initialize_connection_pool():
        logger.warning("Database connection pool not initialized - some features may not work")
    
    # Create Dash app
    try:
        _dash_app = create_dash_app()
        logger.info("Dash app created successfully")
        
        # Mount Dash at root AFTER API router (so /api takes precedence)
        app_instance.mount("/", WSGIMiddleware(_dash_app.server))
        logger.info("Dash app mounted at / (root)")
    except Exception as e:
        logger.error(f"Could not create/mount Dash app: {e}")
        import traceback
        traceback.print_exc()
    
    yield  # Application runs here
    
    # Shutdown
    close_all_connections()
    logger.info("Application shutdown complete")


# Attach lifespan to app
app.router.lifespan_context = lifespan
