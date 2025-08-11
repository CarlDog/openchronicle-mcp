"""
Event interfaces for OpenChronicle.

This module provides WebSocket connections, background task processing,
and real-time event handling. It serves as the event interface layer
in the hexagonal architecture.
"""

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Optional

from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from src.openchronicle.application import ApplicationFacade
from src.openchronicle.infrastructure import InfrastructureConfig
from src.openchronicle.infrastructure import InfrastructureContainer


# ================================
# Event System Types
# ================================


class EventType(Enum):
    """Types of events in the system."""

    STORY_CREATED = "story_created"
    STORY_UPDATED = "story_updated"
    CHARACTER_CREATED = "character_created"
    CHARACTER_UPDATED = "character_updated"
    SCENE_GENERATED = "scene_generated"
    SCENE_SAVED = "scene_saved"
    MEMORY_UPDATED = "memory_updated"
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class Event:
    """Base event structure."""

    id: str
    type: EventType
    timestamp: datetime
    data: dict[str, Any]
    source: str = "openchronicle"

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
        }


# ================================
# Connection Management
# ================================


class ConnectionManager:
    """Manages WebSocket connections and event broadcasting."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[EventType]] = {}
        self.connection_metadata: dict[str, dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        subscriptions: list[EventType] | None = None,
    ) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        # Generate unique session ID if not provided
        if not client_id:
            client_id = f"client_{uuid.uuid4().hex[:8]}"

        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set(subscriptions or [EventType.HEARTBEAT])
        self.connection_metadata[client_id] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "events_sent": 0,
        }

        # Send connection confirmation
        await self.send_to_client(
            client_id,
            Event(
                id=str(uuid.uuid4()),
                type=EventType.SYSTEM_STATUS,
                timestamp=datetime.now(),
                data={
                    "status": "connected",
                    "client_id": client_id,
                    "subscriptions": [et.value for et in self.subscriptions[client_id]],
                },
            ),
        )

        return client_id

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]

    async def send_to_client(self, client_id: str, event: Event):
        """Send an event to a specific client."""
        if client_id not in self.active_connections:
            return False

        websocket = self.active_connections[client_id]

        try:
            await websocket.send_text(json.dumps(event.to_dict()))

            # Update metadata
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["last_activity"] = datetime.now()
                self.connection_metadata[client_id]["events_sent"] += 1

            return True
        except Exception as e:
            print(f"Error sending to client {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(
        self, event: Event, event_type_filter: EventType | None = None
    ):
        """Broadcast an event to all subscribed clients."""
        target_type = event_type_filter or event.type

        disconnected_clients = []

        for client_id, subscriptions in self.subscriptions.items():
            if target_type in subscriptions:
                success = await self.send_to_client(client_id, event)
                if not success:
                    disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        return {
            "active_connections": len(self.active_connections),
            "total_subscriptions": sum(
                len(subs) for subs in self.subscriptions.values()
            ),
            "connections": {
                client_id: {
                    "subscriptions": [et.value for et in subs],
                    "metadata": self.connection_metadata.get(client_id, {}),
                }
                for client_id, subs in self.subscriptions.items()
            },
        }


# ================================
# Event Bus
# ================================


class EventBus:
    """Central event bus for publishing and subscribing to events."""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.subscribers: dict[EventType, list[Callable]] = {}
        self.event_history: list[Event] = []
        self.max_history = 1000

    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to an event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event: Event):
        """Publish an event to subscribers and WebSocket clients."""
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        # Call local subscribers
        if event.type in self.subscribers:
            for callback in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error in event subscriber: {e}")

        # Broadcast to WebSocket clients
        await self.connection_manager.broadcast(event)

    def get_recent_events(
        self, event_types: list[EventType] | None = None, limit: int = 50
    ) -> list[Event]:
        """Get recent events, optionally filtered by type."""
        events = self.event_history

        if event_types:
            events = [e for e in events if e.type in event_types]

        return events[-limit:]


# ================================
# Background Task System
# ================================


class BackgroundTaskManager:
    """Manages background tasks and periodic jobs."""

    def __init__(self, event_bus: EventBus, app_facade: ApplicationFacade):
        self.event_bus = event_bus
        self.app_facade = app_facade
        self.tasks: dict[str, asyncio.Task] = {}
        self.periodic_tasks: dict[str, dict[str, Any]] = {}
        self.running = False

    async def start(self):
        """Start the background task manager."""
        self.running = True

        # Start periodic tasks
        self.add_periodic_task("heartbeat", self._heartbeat_task, interval=30)
        self.add_periodic_task(
            "memory_cleanup", self._memory_cleanup_task, interval=300
        )
        self.add_periodic_task("health_check", self._health_check_task, interval=60)

    async def stop(self):
        """Stop all background tasks."""
        self.running = False

        # Cancel all tasks
        for task_id, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.tasks.clear()
        self.periodic_tasks.clear()

    def add_periodic_task(
        self, task_id: str, coro_func: Callable, interval: int, immediate: bool = False
    ):
        """Add a periodic background task."""
        if task_id in self.periodic_tasks:
            return  # Task already exists

        self.periodic_tasks[task_id] = {
            "function": coro_func,
            "interval": interval,
            "immediate": immediate,
            "last_run": None,
            "run_count": 0,
        }

        # Start the task
        task = asyncio.create_task(self._run_periodic_task(task_id))
        self.tasks[task_id] = task

    async def _run_periodic_task(self, task_id: str):
        """Run a periodic task in a loop."""
        task_info = self.periodic_tasks[task_id]

        # Run immediately if requested
        if task_info["immediate"]:
            await self._execute_task(task_id)

        # Main periodic loop
        while self.running:
            try:
                await asyncio.sleep(task_info["interval"])
                if self.running:
                    await self._execute_task(task_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.event_bus.publish(
                    Event(
                        id=str(uuid.uuid4()),
                        type=EventType.ERROR,
                        timestamp=datetime.now(),
                        data={
                            "error": f"Periodic task {task_id} failed: {e!s}",
                            "task_id": task_id,
                        },
                    )
                )
                # Continue running despite errors
                await asyncio.sleep(task_info["interval"])

    async def _execute_task(self, task_id: str):
        """Execute a single task."""
        task_info = self.periodic_tasks[task_id]

        try:
            await task_info["function"]()
            task_info["last_run"] = datetime.now()
            task_info["run_count"] += 1
        except Exception as e:
            await self.event_bus.publish(
                Event(
                    id=str(uuid.uuid4()),
                    type=EventType.ERROR,
                    timestamp=datetime.now(),
                    data={
                        "error": f"Task execution failed: {e!s}",
                        "task_id": task_id,
                    },
                )
            )

    async def _heartbeat_task(self):
        """Send periodic heartbeat events."""
        stats = self.event_bus.connection_manager.get_connection_stats()

        await self.event_bus.publish(
            Event(
                id=str(uuid.uuid4()),
                type=EventType.HEARTBEAT,
                timestamp=datetime.now(),
                data={
                    "status": "alive",
                    "connections": stats["active_connections"],
                    "uptime": "running",  # TODO: calculate actual uptime
                },
            )
        )

    async def _memory_cleanup_task(self):
        """Periodic memory cleanup and optimization."""
        # TODO: Implement memory cleanup logic
        # This could trigger cache cleanup, memory state optimization, etc.
        await self.event_bus.publish(
            Event(
                id=str(uuid.uuid4()),
                type=EventType.SYSTEM_STATUS,
                timestamp=datetime.now(),
                data={"action": "memory_cleanup", "status": "completed"},
            )
        )

    async def _health_check_task(self):
        """Periodic system health check."""
        try:
            # This would use the infrastructure health check
            health_status = {"status": "healthy", "components": {}}  # Simplified

            await self.event_bus.publish(
                Event(
                    id=str(uuid.uuid4()),
                    type=EventType.SYSTEM_STATUS,
                    timestamp=datetime.now(),
                    data={"action": "health_check", "health": health_status},
                )
            )
        except Exception as e:
            await self.event_bus.publish(
                Event(
                    id=str(uuid.uuid4()),
                    type=EventType.ERROR,
                    timestamp=datetime.now(),
                    data={
                        "error": f"Health check failed: {e!s}",
                        "action": "health_check",
                    },
                )
            )


# ================================
# Event Application
# ================================


class EventApplication:
    """Main event application combining all components."""

    def __init__(self):
        # Create default infrastructure configuration
        config = InfrastructureConfig(
            storage_backend="filesystem", storage_path="storage", cache_type="memory"
        )
        self.infrastructure = InfrastructureContainer(config)
        self.app_facade = None
        self.connection_manager = ConnectionManager()
        self.event_bus = EventBus(self.connection_manager)
        self.background_manager = None
        self._initialized = False

    async def initialize(self):
        """Initialize the event application."""
        if self._initialized:
            return

        await self.infrastructure.initialize()
        self.app_facade = ApplicationFacade(
            story_orchestrator=self.infrastructure.get_story_orchestrator(),
            character_orchestrator=self.infrastructure.get_character_orchestrator(),
            scene_orchestrator=self.infrastructure.get_scene_orchestrator(),
            memory_manager=self.infrastructure.get_memory_manager(),
        )

        self.background_manager = BackgroundTaskManager(self.event_bus, self.app_facade)
        await self.background_manager.start()

        # Set up event listeners for application events
        self._setup_application_listeners()

        self._initialized = True

    async def shutdown(self):
        """Shutdown the event application."""
        if self.background_manager:
            await self.background_manager.stop()

        # Disconnect all WebSocket clients
        for client_id in list(self.connection_manager.active_connections.keys()):
            self.connection_manager.disconnect(client_id)

        await self.infrastructure.shutdown()

    def _setup_application_listeners(self):
        """Set up listeners for application events."""
        # TODO: Add listeners for domain events
        # This would connect to the application layer's event system


# Global event application
_event_app = EventApplication()


async def get_event_app() -> EventApplication:
    """Get the initialized event application."""
    if not _event_app._initialized:
        await _event_app.initialize()
    return _event_app


# ================================
# WebSocket Endpoints
# ================================


def create_event_app() -> FastAPI:
    """Create FastAPI application with WebSocket support."""
    app = FastAPI(title="OpenChronicle Events")

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        """WebSocket endpoint for real-time events."""
        event_app = await get_event_app()

        try:
            # Parse subscription preferences from query params
            subscriptions = []
            if hasattr(websocket, "query_params"):
                sub_param = websocket.query_params.get("subscriptions", "")
                if sub_param:
                    for sub in sub_param.split(","):
                        try:
                            subscriptions.append(EventType(sub.strip()))
                        except ValueError:
                            pass

            # Default subscriptions if none specified
            if not subscriptions:
                subscriptions = [
                    EventType.STORY_CREATED,
                    EventType.CHARACTER_CREATED,
                    EventType.SCENE_GENERATED,
                    EventType.SYSTEM_STATUS,
                    EventType.HEARTBEAT,
                ]

            # Connect client
            actual_client_id = await event_app.connection_manager.connect(
                websocket, client_id, subscriptions
            )

            print(
                f"Client {actual_client_id} connected with subscriptions: {[s.value for s in subscriptions]}"
            )

            # Keep connection alive and handle incoming messages
            while True:
                try:
                    # Wait for messages from client
                    message = await websocket.receive_text()
                    data = json.loads(message)

                    # Handle client messages
                    if data.get("type") == "ping":
                        await event_app.connection_manager.send_to_client(
                            actual_client_id,
                            Event(
                                id=str(uuid.uuid4()),
                                type=EventType.HEARTBEAT,
                                timestamp=datetime.now(),
                                data={"type": "pong", "client_id": actual_client_id},
                            ),
                        )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"WebSocket error for client {actual_client_id}: {e}")
                    break

        finally:
            event_app.connection_manager.disconnect(actual_client_id)
            print(f"Client {actual_client_id} disconnected")

    @app.get("/events/stats")
    async def get_event_stats():
        """Get event system statistics."""
        event_app = await get_event_app()

        return {
            "connections": event_app.connection_manager.get_connection_stats(),
            "recent_events": len(event_app.event_bus.get_recent_events()),
            "background_tasks": {
                task_id: {
                    "interval": info["interval"],
                    "last_run": (
                        info["last_run"].isoformat() if info["last_run"] else None
                    ),
                    "run_count": info["run_count"],
                }
                for task_id, info in (
                    event_app.background_manager.periodic_tasks.items()
                    if event_app.background_manager
                    else {}
                ).items()
            },
        }

    @app.get("/events/recent")
    async def get_recent_events(limit: int = 50):
        """Get recent events."""
        event_app = await get_event_app()

        events = event_app.event_bus.get_recent_events(limit=limit)
        return [event.to_dict() for event in events]

    @app.post("/events/test")
    async def send_test_event():
        """Send a test event (for development)."""
        event_app = await get_event_app()

        test_event = Event(
            id=str(uuid.uuid4()),
            type=EventType.SYSTEM_STATUS,
            timestamp=datetime.now(),
            data={
                "test": True,
                "message": "This is a test event",
                "timestamp": datetime.now().isoformat(),
            },
        )

        await event_app.event_bus.publish(test_event)

        return {"status": "Test event sent", "event_id": test_event.id}

    return app


# ================================
# Development Server
# ================================


def run_event_server(host: str = "0.0.0.0", port: int = 8081, reload: bool = True):
    """Run the event server."""
    import uvicorn

    app = create_event_app()
    print(f"⚡ Starting OpenChronicle Event Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    run_event_server()
