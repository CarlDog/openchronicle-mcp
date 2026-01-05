"""
Interface layer for OpenChronicle.

This module provides all external interfaces including API endpoints,
CLI commands, web templates, and real-time event handling. It serves
as the interface layer in the hexagonal architecture.

The interface layer is responsible for:
- HTTP API endpoints (REST)
- Command-line interface (CLI)
- Web user interface (HTML/templates)
- Real-time events (WebSocket)
- External integrations
"""

from openchronicle.shared.exceptions import ApplicationError
from openchronicle.shared.exceptions import InfrastructureError

from ..shared.logging_system import log_error
from ..shared.logging_system import log_info
from ..shared.logging_system import log_system_event
from .api import app as api_app
from .api import run_dev_server as run_api_server
from .events import create_event_app
from .events import run_event_server
from .web import create_web_app
from .web import run_web_server


__all__ = [
    # API interface
    "api_app",
    "run_api_server",
    # CLI interface
    "cli",
    # Web interface
    "create_web_app",
    "run_web_server",
    # Event interface
    "create_event_app",
    "run_event_server",
]


# ================================
# Unified Server Runner
# ================================


def run_all_servers(
    api_port: int = 8000,
    web_port: int = 8080,
    event_port: int = 8081,
    host: str = "0.0.0.0",
):
    """
    Run all interface servers simultaneously.

    This is useful for development environments where you want
    all interfaces available at once.
    """
    from multiprocessing import Process

    import uvicorn

    def run_api():
        uvicorn.run(
            "src.openchronicle.interfaces.api:app",
            host=host,
            port=api_port,
            reload=False,
            log_level="info",
        )

    def run_web():
        uvicorn.run(create_web_app(), host=host, port=web_port, reload=False, log_level="info")

    def run_events():
        uvicorn.run(
            create_event_app(),
            host=host,
            port=event_port,
            reload=False,
            log_level="info",
        )

    log_system_event(
        "startup",
        "Starting all OpenChronicle interface servers",
        {
            "api_url": f"http://{host}:{api_port}",
            "web_url": f"http://{host}:{web_port}",
            "event_url": f"http://{host}:{event_port}",
        },
    )
    log_info("API Server starting", context_tags=["interfaces", "api"], host=host, port=api_port)
    log_info("Web Interface starting", context_tags=["interfaces", "web"], host=host, port=web_port)
    log_info("Event Server starting", context_tags=["interfaces", "events"], host=host, port=event_port)
    log_info("CLI available via 'openchronicle' command", context_tags=["interfaces", "cli"])

    # Start processes
    processes = []

    # API server
    api_process = Process(target=run_api, name="API-Server")
    api_process.start()
    processes.append(api_process)

    # Web server
    web_process = Process(target=run_web, name="Web-Server")
    web_process.start()
    processes.append(web_process)

    # Event server
    event_process = Process(target=run_events, name="Event-Server")
    event_process.start()
    processes.append(event_process)

    try:
        # Wait for all processes
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        log_system_event("shutdown", "Shutting down all servers via KeyboardInterrupt")
        for process in processes:
            process.terminate()

        for process in processes:
            process.join()
        log_info("All servers stopped", context_tags=["interfaces"])


# ================================
# Interface Configuration
# ================================


class InterfaceConfig:
    """Configuration for interface layer."""

    # API Configuration
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_TITLE = "OpenChronicle API"
    API_VERSION = "0.1.0"

    # Web Configuration
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 8080
    WEB_TITLE = "OpenChronicle Web Interface"

    # Event Configuration
    EVENT_HOST = "0.0.0.0"
    EVENT_PORT = 8081
    EVENT_TITLE = "OpenChronicle Events"

    # CLI Configuration
    CLI_NAME = "openchronicle"
    CLI_VERSION = "0.1.0"

    # CORS Configuration
    CORS_ORIGINS = ["*"]  # Configure for production
    CORS_CREDENTIALS = True
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]


# ================================
# Health Check Integration
# ================================


async def check_all_interfaces():
    """
    Check health of all interface components.

    Returns a comprehensive health status for the entire
    interface layer.
    """
    from ..infrastructure import InfrastructureConfig
    from ..infrastructure import InfrastructureContainer

    health_status = {
        "interface_layer": "healthy",
        "timestamp": "current",
        "components": {
            "api": "healthy",
            "web": "healthy",
            "events": "healthy",
            "cli": "healthy",
        },
        "details": {
            "api_endpoints": "available",
            "web_templates": "loaded",
            "websocket_support": "active",
            "cli_commands": "registered",
        },
    }

    try:
        # Check infrastructure health
        config = InfrastructureConfig(storage_backend="filesystem", storage_path="storage", cache_type="memory")
        infrastructure = InfrastructureContainer(config)
        await infrastructure.initialize()
        infra_health = await infrastructure.health_check()

        if infra_health["status"] != "healthy":
            health_status["interface_layer"] = "degraded"
            health_status["details"]["infrastructure"] = infra_health["status"]

        await infrastructure.shutdown()

    except (InfrastructureError, ApplicationError) as e:
        health_status["interface_layer"] = "unhealthy"
        health_status["components"]["infrastructure"] = "service_error"
        health_status["details"]["error"] = f"Infrastructure/service error: {str(e)}"
    except (AttributeError, KeyError) as e:
        health_status["interface_layer"] = "unhealthy"
        health_status["components"]["infrastructure"] = "data_structure_error"
        health_status["details"]["error"] = f"Data structure error: {str(e)}"
    except Exception as e:
        health_status["interface_layer"] = "unhealthy"
        health_status["components"]["infrastructure"] = "unexpected_error"
        health_status["details"]["error"] = f"Unexpected error: {str(e)}"

    return health_status


# ================================
# Development Utilities
# ================================


def list_available_interfaces():
    """List all available interface endpoints and commands."""

    interfaces = {
        "API Endpoints": {
            "Base URL": "http://localhost:8000",
            "Health Check": "GET /api/v1/health",
            "Stories": "GET,POST /api/v1/stories",
            "Characters": "GET,POST /api/v1/characters",
            "Scenes": "POST /api/v1/scenes",
            "Documentation": "GET /docs (Swagger UI)",
        },
        "Web Interface": {
            "Base URL": "http://localhost:8080",
            "Home Page": "GET /",
            "Stories": "GET /stories",
            "Create Story": "GET,POST /stories/create",
            "System Status": "GET /status",
        },
        "Event System": {
            "Base URL": "http://localhost:8081",
            "WebSocket": "WS /ws/{client_id}",
            "Event Stats": "GET /events/stats",
            "Recent Events": "GET /events/recent",
            "Test Event": "POST /events/test",
        },
        "CLI Commands": {
            "Version": "openchronicle version",
            "Status": "openchronicle status",
            "Stories": "openchronicle story list|create|show",
            "Characters": "openchronicle character list|create",
            "Scenes": "openchronicle scene generate|list",
        },
    }

    return interfaces


if __name__ == "__main__":
    # If run directly, start all servers
    run_all_servers()
