"""
Web interfaces for OpenChronicle.

This module provides HTML templates and web UI components for browser-based
story management. It serves as the web interface layer in the hexagonal architecture.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

from ...application import ApplicationFacade
from ...infrastructure import InfrastructureContainer, InfrastructureConfig


# ================================
# Template Configuration
# ================================

# Get the template directory path
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# Ensure directories exist
TEMPLATE_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# ================================
# Web Application Container
# ================================


class WebAppContainer:
    """Container for web application dependencies."""

    def __init__(self):
        # Create default infrastructure configuration
        config = InfrastructureConfig(
            storage_backend="filesystem", storage_path="storage", cache_type="memory"
        )
        self.infrastructure = InfrastructureContainer(config)
        self.app_facade = None

    async def initialize(self):
        """Initialize the application facade."""
        await self.infrastructure.initialize()
        self.app_facade = ApplicationFacade(
            story_orchestrator=self.infrastructure.get_story_orchestrator(),
            character_orchestrator=self.infrastructure.get_character_orchestrator(),
            scene_orchestrator=self.infrastructure.get_scene_orchestrator(),
            memory_manager=self.infrastructure.get_memory_manager(),
        )


# Global container instance
_web_container = WebAppContainer()


async def get_app_facade() -> ApplicationFacade:
    """Get the application facade."""
    if _web_container.app_facade is None:
        await _web_container.initialize()
    return _web_container.app_facade


# ================================
# Template Creation Functions
# ================================


def create_base_template():
    """Create the base HTML template."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}OpenChronicle{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .story-card {
            transition: transform 0.2s;
        }
        .story-card:hover {
            transform: translateY(-5px);
        }
        .character-card {
            border-left: 4px solid #007bff;
        }
        .scene-content {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            font-style: italic;
        }
        .navbar-brand {
            font-weight: bold;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-book-open me-2"></i>
                OpenChronicle
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/stories">
                            <i class="fas fa-book me-1"></i>Stories
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/characters">
                            <i class="fas fa-users me-1"></i>Characters
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/scenes">
                            <i class="fas fa-theater-masks me-1"></i>Scenes
                        </a>
                    </li>
                </ul>
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="/status">
                            <i class="fas fa-heartbeat me-1"></i>Status
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer -->
    <footer class="bg-light mt-5 py-4">
        <div class="container text-center text-muted">
            <p>OpenChronicle v0.1.0 - Narrative AI Engine</p>
            <p><small>Hexagonal Architecture • Character Consistency • Memory Management</small></p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>"""


def create_home_template():
    """Create the home page template."""
    return """{% extends "base.html" %}

{% block title %}Home - OpenChronicle{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="jumbotron bg-primary text-white rounded p-5 mb-4">
            <h1 class="display-4">
                <i class="fas fa-magic me-3"></i>
                Welcome to OpenChronicle
            </h1>
            <p class="lead">
                Advanced narrative AI engine with character consistency, 
                memory management, and interactive storytelling.
            </p>
            <hr class="my-4">
            <p>
                Create immersive stories with AI-powered character interactions,
                persistent memory, and intelligent scene generation.
            </p>
            <a class="btn btn-light btn-lg" href="/stories/create" role="button">
                <i class="fas fa-plus me-2"></i>
                Create Your First Story
            </a>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-chart-line me-2"></i>Quick Stats</h5>
            </div>
            <div class="card-body">
                <div class="row text-center">
                    <div class="col">
                        <h3 class="text-primary">{{ stats.stories }}</h3>
                        <small class="text-muted">Stories</small>
                    </div>
                    <div class="col">
                        <h3 class="text-success">{{ stats.characters }}</h3>
                        <small class="text-muted">Characters</small>
                    </div>
                    <div class="col">
                        <h3 class="text-info">{{ stats.scenes }}</h3>
                        <small class="text-muted">Scenes</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="fas fa-clock me-2"></i>Recent Activity</h5>
            </div>
            <div class="card-body">
                {% if recent_stories %}
                    {% for story in recent_stories %}
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <strong>{{ story.title }}</strong><br>
                            <small class="text-muted">{{ story.created_at.strftime("%Y-%m-%d") }}</small>
                        </div>
                        <a href="/stories/{{ story.id }}" class="btn btn-sm btn-outline-primary">
                            View
                        </a>
                    </div>
                    {% endfor %}
                {% else %}
                    <p class="text-muted">No recent activity</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<!-- Feature Cards -->
<div class="row mt-5">
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body text-center">
                <i class="fas fa-brain fa-3x text-primary mb-3"></i>
                <h5>AI-Powered Generation</h5>
                <p class="text-muted">
                    Advanced language models create coherent, engaging narrative content
                    tailored to your story's world and characters.
                </p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body text-center">
                <i class="fas fa-users fa-3x text-success mb-3"></i>
                <h5>Character Consistency</h5>
                <p class="text-muted">
                    Sophisticated character tracking ensures personalities, 
                    relationships, and growth remain consistent throughout your story.
                </p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-body text-center">
                <i class="fas fa-memory fa-3x text-info mb-3"></i>
                <h5>Persistent Memory</h5>
                <p class="text-muted">
                    Advanced memory management tracks events, relationships, 
                    and story state across long narrative sessions.
                </p>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""


def create_stories_list_template():
    """Create the stories list template."""
    return """{% extends "base.html" %}

{% block title %}Stories - OpenChronicle{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1><i class="fas fa-book me-3"></i>Your Stories</h1>
    <a href="/stories/create" class="btn btn-primary">
        <i class="fas fa-plus me-2"></i>New Story
    </a>
</div>

{% if stories %}
<div class="row">
    {% for story in stories %}
    <div class="col-md-6 col-lg-4 mb-4">
        <div class="card story-card h-100">
            <div class="card-body">
                <h5 class="card-title">{{ story.title }}</h5>
                <p class="card-text text-muted">
                    {% if story.description %}
                        {{ story.description[:100] }}{% if story.description|length > 100 %}...{% endif %}
                    {% else %}
                        <em>No description</em>
                    {% endif %}
                </p>
                <div class="mb-2">
                    <span class="badge bg-primary">{{ story.status.value }}</span>
                    {% if story.world_state.genre %}
                        <span class="badge bg-secondary">{{ story.world_state.genre }}</span>
                    {% endif %}
                </div>
                <small class="text-muted">
                    Created: {{ story.created_at.strftime("%Y-%m-%d") }}
                </small>
            </div>
            <div class="card-footer bg-transparent">
                <div class="btn-group w-100" role="group">
                    <a href="/stories/{{ story.id }}" class="btn btn-outline-primary">
                        <i class="fas fa-eye me-1"></i>View
                    </a>
                    <a href="/stories/{{ story.id }}/characters" class="btn btn-outline-success">
                        <i class="fas fa-users me-1"></i>Characters
                    </a>
                    <a href="/stories/{{ story.id }}/scenes" class="btn btn-outline-info">
                        <i class="fas fa-theater-masks me-1"></i>Scenes
                    </a>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% else %}
<div class="text-center py-5">
    <i class="fas fa-book fa-4x text-muted mb-3"></i>
    <h3 class="text-muted">No Stories Yet</h3>
    <p class="text-muted">Create your first story to get started with OpenChronicle.</p>
    <a href="/stories/create" class="btn btn-primary btn-lg">
        <i class="fas fa-plus me-2"></i>Create Story
    </a>
</div>
{% endif %}
{% endblock %}"""


def create_story_create_template():
    """Create the story creation template."""
    return """{% extends "base.html" %}

{% block title %}Create Story - OpenChronicle{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header">
                <h3><i class="fas fa-plus me-2"></i>Create New Story</h3>
            </div>
            <div class="card-body">
                <form method="post">
                    <div class="mb-3">
                        <label for="title" class="form-label">Title *</label>
                        <input type="text" class="form-control" id="title" name="title" required 
                               placeholder="Enter your story title">
                    </div>
                    
                    <div class="mb-3">
                        <label for="description" class="form-label">Description</label>
                        <textarea class="form-control" id="description" name="description" rows="3"
                                  placeholder="Describe your story (optional)"></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="genre" class="form-label">Genre</label>
                        <select class="form-control" id="genre" name="genre">
                            <option value="">Select genre (optional)</option>
                            <option value="fantasy">Fantasy</option>
                            <option value="science_fiction">Science Fiction</option>
                            <option value="mystery">Mystery</option>
                            <option value="romance">Romance</option>
                            <option value="adventure">Adventure</option>
                            <option value="horror">Horror</option>
                            <option value="comedy">Comedy</option>
                            <option value="drama">Drama</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="setting" class="form-label">Setting</label>
                                <input type="text" class="form-control" id="setting" name="setting"
                                       placeholder="Where does your story take place?">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="tech_level" class="form-label">Technology Level</label>
                                <select class="form-control" id="tech_level" name="tech_level">
                                    <option value="">Select technology level</option>
                                    <option value="stone_age">Stone Age</option>
                                    <option value="bronze_age">Bronze Age</option>
                                    <option value="medieval">Medieval</option>
                                    <option value="renaissance">Renaissance</option>
                                    <option value="industrial">Industrial</option>
                                    <option value="modern">Modern</option>
                                    <option value="near_future">Near Future</option>
                                    <option value="far_future">Far Future</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="magic_level" class="form-label">Magic Level</label>
                        <select class="form-control" id="magic_level" name="magic_level">
                            <option value="">Select magic level</option>
                            <option value="none">No Magic</option>
                            <option value="low">Low Magic</option>
                            <option value="medium">Medium Magic</option>
                            <option value="high">High Magic</option>
                            <option value="very_high">Very High Magic</option>
                        </select>
                    </div>
                    
                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <a href="/stories" class="btn btn-secondary">
                            <i class="fas fa-times me-2"></i>Cancel
                        </a>
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-save me-2"></i>Create Story
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""


def create_story_detail_template():
    """Create the story detail template."""
    return """{% extends "base.html" %}

{% block title %}{{ story.title }} - OpenChronicle{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h3><i class="fas fa-book me-2"></i>{{ story.title }}</h3>
                <span class="badge bg-primary fs-6">{{ story.status.value }}</span>
            </div>
            <div class="card-body">
                {% if story.description %}
                <p class="card-text">{{ story.description }}</p>
                {% endif %}
                
                <div class="row">
                    <div class="col-md-6">
                        <h5>World Information</h5>
                        {% if story.world_state %}
                            <ul class="list-unstyled">
                                {% for key, value in story.world_state.items() %}
                                {% if value %}
                                <li><strong>{{ key.replace('_', ' ').title() }}:</strong> {{ value }}</li>
                                {% endif %}
                                {% endfor %}
                            </ul>
                        {% else %}
                            <p class="text-muted">No world information defined</p>
                        {% endif %}
                    </div>
                    <div class="col-md-6">
                        <h5>Story Details</h5>
                        <ul class="list-unstyled">
                            <li><strong>Created:</strong> {{ story.created_at.strftime("%Y-%m-%d %H:%M") }}</li>
                            <li><strong>Updated:</strong> {{ story.updated_at.strftime("%Y-%m-%d %H:%M") }}</li>
                            <li><strong>ID:</strong> <code>{{ story.id }}</code></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        {% if characters %}
        <div class="card mt-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5><i class="fas fa-users me-2"></i>Characters ({{ characters|length }})</h5>
                <a href="/stories/{{ story.id }}/characters/create" class="btn btn-sm btn-success">
                    <i class="fas fa-plus me-1"></i>Add Character
                </a>
            </div>
            <div class="card-body">
                <div class="row">
                    {% for character in characters %}
                    <div class="col-md-6 mb-3">
                        <div class="card character-card">
                            <div class="card-body">
                                <h6 class="card-title">{{ character.name }}</h6>
                                {% if character.personality_traits %}
                                <div class="mb-2">
                                    {% for trait, value in character.personality_traits.items() %}
                                    <span class="badge bg-light text-dark me-1">{{ trait }}: {{ value }}</span>
                                    {% endfor %}
                                </div>
                                {% endif %}
                                {% if character.background %}
                                <p class="card-text small text-muted">
                                    {{ character.background[:100] }}{% if character.background|length > 100 %}...{% endif %}
                                </p>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}

        {% if scenes %}
        <div class="card mt-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5><i class="fas fa-theater-masks me-2"></i>Recent Scenes ({{ scenes|length }})</h5>
                <a href="/stories/{{ story.id }}/scenes/generate" class="btn btn-sm btn-info">
                    <i class="fas fa-magic me-1"></i>Generate Scene
                </a>
            </div>
            <div class="card-body">
                {% for scene in scenes %}
                <div class="mb-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6>{{ scene.setting }}</h6>
                        <small class="text-muted">{{ scene.created_at.strftime("%Y-%m-%d %H:%M") }}</small>
                    </div>
                    <div class="scene-content">
                        {{ scene.ai_response[:300] }}{% if scene.ai_response|length > 300 %}...{% endif %}
                    </div>
                </div>
                {% endfor %}
                
                {% if scenes|length >= 5 %}
                <div class="text-center">
                    <a href="/stories/{{ story.id }}/scenes" class="btn btn-outline-primary">
                        View All Scenes
                    </a>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-tools me-2"></i>Actions</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="/stories/{{ story.id }}/characters/create" class="btn btn-success">
                        <i class="fas fa-user-plus me-2"></i>Add Character
                    </a>
                    <a href="/stories/{{ story.id }}/scenes/generate" class="btn btn-info">
                        <i class="fas fa-magic me-2"></i>Generate Scene
                    </a>
                    <a href="/stories/{{ story.id }}/edit" class="btn btn-warning">
                        <i class="fas fa-edit me-2"></i>Edit Story
                    </a>
                </div>
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="fas fa-chart-bar me-2"></i>Statistics</h5>
            </div>
            <div class="card-body">
                <div class="row text-center">
                    <div class="col">
                        <h4 class="text-success">{{ characters|length if characters else 0 }}</h4>
                        <small class="text-muted">Characters</small>
                    </div>
                    <div class="col">
                        <h4 class="text-info">{{ scenes|length if scenes else 0 }}</h4>
                        <small class="text-muted">Scenes</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""


def create_status_template():
    """Create the system status template."""
    return """{% extends "base.html" %}

{% block title %}System Status - OpenChronicle{% endblock %}

{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h3><i class="fas fa-heartbeat me-2"></i>System Status</h3>
                <span class="badge {% if health.status == 'healthy' %}bg-success{% else %}bg-danger{% endif %} fs-6">
                    {{ health.status.upper() }}
                </span>
            </div>
            <div class="card-body">
                <p><strong>Last Check:</strong> {{ health.timestamp.strftime("%Y-%m-%d %H:%M:%S") }}</p>
                
                <h5 class="mt-4">Component Health</h5>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Component</th>
                                <th>Status</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for component, status in health.components.items() %}
                            <tr>
                                <td>
                                    <i class="fas fa-{% if status == 'healthy' %}check-circle text-success{% else %}times-circle text-danger{% endif %} me-2"></i>
                                    {{ component.replace('_', ' ').title() }}
                                </td>
                                <td>
                                    <span class="badge {% if status == 'healthy' %}bg-success{% else %}bg-danger{% endif %}">
                                        {{ status }}
                                    </span>
                                </td>
                                <td>
                                    {% if status == 'healthy' %}
                                        <span class="text-success">Operational</span>
                                    {% else %}
                                        <span class="text-danger">{{ status }}</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <h5><i class="fas fa-info-circle me-2"></i>System Information</h5>
            </div>
            <div class="card-body">
                <ul class="list-unstyled">
                    <li><strong>Version:</strong> 0.1.0</li>
                    <li><strong>Architecture:</strong> Hexagonal/Clean</li>
                    <li><strong>Pattern:</strong> CQRS + Event Sourcing</li>
                    <li><strong>Infrastructure:</strong> Async Python</li>
                    <li><strong>AI Models:</strong> Multiple Providers</li>
                </ul>
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="fas fa-external-link-alt me-2"></i>External Links</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="/api/v1/health" class="btn btn-outline-primary" target="_blank">
                        <i class="fas fa-code me-2"></i>API Health Check
                    </a>
                    <a href="/api/v1/status" class="btn btn-outline-info" target="_blank">
                        <i class="fas fa-info me-2"></i>API Status
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Auto-refresh status every 30 seconds
setTimeout(function() {
    location.reload();
}, 30000);
</script>
{% endblock %}"""


def setup_templates():
    """Set up all HTML templates."""
    templates_to_create = {
        "base.html": create_base_template(),
        "home.html": create_home_template(),
        "stories_list.html": create_stories_list_template(),
        "story_create.html": create_story_create_template(),
        "story_detail.html": create_story_detail_template(),
        "status.html": create_status_template(),
    }

    for filename, content in templates_to_create.items():
        template_path = TEMPLATE_DIR / filename
        if not template_path.exists():
            template_path.write_text(content, encoding="utf-8")


# Initialize templates on import
setup_templates()


# ================================
# Web Route Handlers
# ================================


def create_web_app() -> FastAPI:
    """Create the web application with all routes."""
    app = FastAPI(title="OpenChronicle Web Interface")

    # Serve static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Home page."""
        app_facade = await get_app_facade()

        # Get quick stats
        stories_result = await app_facade.list_stories(limit=5)
        recent_stories = stories_result.data if stories_result.success else []

        stats = {
            "stories": len(recent_stories) if recent_stories else 0,
            "characters": 0,  # TODO: implement global character count
            "scenes": 0,  # TODO: implement global scene count
        }

        return templates.TemplateResponse(
            "home.html",
            {"request": request, "stats": stats, "recent_stories": recent_stories},
        )

    @app.get("/stories", response_class=HTMLResponse)
    async def stories_list(request: Request):
        """Stories list page."""
        app_facade = await get_app_facade()

        result = await app_facade.list_stories(limit=50)
        stories = result.data if result.success else []

        return templates.TemplateResponse(
            "stories_list.html", {"request": request, "stories": stories}
        )

    @app.get("/stories/create", response_class=HTMLResponse)
    async def story_create_form(request: Request):
        """Story creation form."""
        return templates.TemplateResponse("story_create.html", {"request": request})

    @app.post("/stories/create")
    async def story_create_submit(
        request: Request,
        title: str = Form(...),
        description: str = Form(""),
        genre: str = Form(""),
        setting: str = Form(""),
        tech_level: str = Form(""),
        magic_level: str = Form(""),
    ):
        """Handle story creation form submission."""
        app_facade = await get_app_facade()

        # Build world state
        world_state = {}
        if genre:
            world_state["genre"] = genre
        if setting:
            world_state["setting"] = setting
        if tech_level:
            world_state["tech_level"] = tech_level
        if magic_level:
            world_state["magic_level"] = magic_level

        result = await app_facade.create_story(
            title=title,
            description=description if description else None,
            world_state=world_state,
        )

        if result.success:
            story = result.data
            return RedirectResponse(
                url=f"/stories/{story.id}", status_code=HTTP_303_SEE_OTHER
            )
        else:
            # TODO: Handle validation errors
            return templates.TemplateResponse(
                "story_create.html",
                {
                    "request": request,
                    "errors": result.errors,
                    "title": title,
                    "description": description,
                    "genre": genre,
                    "setting": setting,
                    "tech_level": tech_level,
                    "magic_level": magic_level,
                },
            )

    @app.get("/stories/{story_id}", response_class=HTMLResponse)
    async def story_detail(request: Request, story_id: str):
        """Story detail page."""
        app_facade = await get_app_facade()

        # Get story
        story_result = await app_facade.get_story(story_id)
        if not story_result.success:
            raise HTTPException(status_code=404, detail="Story not found")

        story = story_result.data

        # Get characters
        chars_result = await app_facade.get_story_characters(story_id)
        characters = chars_result.data if chars_result.success else []

        # Get recent scenes
        scenes_result = await app_facade.get_story_scenes(story_id, limit=5)
        scenes = scenes_result.data if scenes_result.success else []

        return templates.TemplateResponse(
            "story_detail.html",
            {
                "request": request,
                "story": story,
                "characters": characters,
                "scenes": scenes,
            },
        )

    @app.get("/status", response_class=HTMLResponse)
    async def status_page(request: Request):
        """System status page."""
        try:
            health_status = await _web_container.infrastructure.health_check()

            health = {
                "status": health_status["status"],
                "timestamp": datetime.now(),
                "components": health_status["components"],
            }
        except Exception as e:
            health = {
                "status": "error",
                "timestamp": datetime.now(),
                "components": {"error": str(e)},
            }

        return templates.TemplateResponse(
            "status.html", {"request": request, "health": health}
        )

    return app


# ================================
# Development Server
# ================================


def run_web_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = True):
    """Run the web development server."""
    import uvicorn

    app = create_web_app()
    print(f"🌐 Starting OpenChronicle Web Interface on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    run_web_server()
