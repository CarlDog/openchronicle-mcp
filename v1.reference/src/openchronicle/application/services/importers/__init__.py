"""
OpenChronicle Application Services - Importers Module

Import services for various content types including storypacks, chatbots, and assistants.
These services orchestrate between domain models and infrastructure adapters.
"""

# Import availability tracking
STORYPACK_IMPORT_AVAILABLE = True
CHATBOT_IMPORT_AVAILABLE = False  # To be implemented
ASSISTANT_IMPORT_AVAILABLE = False  # To be implemented

__all__ = [
    "STORYPACK_IMPORT_AVAILABLE",
    "CHATBOT_IMPORT_AVAILABLE",
    "ASSISTANT_IMPORT_AVAILABLE",
]
