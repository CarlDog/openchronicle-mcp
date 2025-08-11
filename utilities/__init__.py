"""
OpenChronicle Utilities Package

A collection of utility tools for OpenChronicle development and maintenance.
"""

__version__ = "1.0.0"

# Availability flags for utilities
CHATBOT_IMPORTER_AVAILABLE = False  # Stub implementation
ASSISTANT_IMPORTER_AVAILABLE = False  # Stub implementation
STORYPACK_IMPORTER_AVAILABLE = False  # Stub implementation

def get_available_utilities():
    """Get list of currently available utilities."""
    available = []

    if CHATBOT_IMPORTER_AVAILABLE:
        available.append('chatbot_importer')

    if ASSISTANT_IMPORTER_AVAILABLE:
        available.append('assistant_importer')

    if STORYPACK_IMPORTER_AVAILABLE:
        available.append('storypack_importer')

    return available

def get_planned_utilities():
    """Get list of planned utilities (including stubs)."""
    return [
        'chatbot_importer',
        'assistant_importer',
        'storypack_importer'
    ]
