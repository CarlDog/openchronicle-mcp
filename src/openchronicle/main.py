#!/usr/bin/env python3
"""
OpenChronicle - Interactive Story Engine

Main entry point for the OpenChronicle narrative AI engine.
This replaces the legacy 817-line main.py with a clean hexagonal architecture.

Usage:
    python main.py                          # Interactive mode with demo story
    python main.py --test                   # Quick system test
    python main.py --story-id my-story      # Load specific story
    python main.py --non-interactive        # Automation mode
    python main.py --api                    # Start API server
    python main.py --web                    # Start web interface
    python main.py --cli                    # Force CLI mode (default)
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional, List

# Ensure we can import from our source
sys.path.insert(0, str(Path(__file__).parent.parent))

from openchronicle.infrastructure.container import InfrastructureContainer
from openchronicle.applications.cli_app import CLIApplication, CLIAppConfig
from openchronicle.applications.services.story_processing_service import StoryProcessingConfig

# Version information
__version__ = "0.1.0"  # Sync with pyproject.toml


def parse_arguments():
    """Parse command line arguments with full legacy compatibility."""
    parser = argparse.ArgumentParser(
        description='OpenChronicle Interactive Story Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Interactive CLI mode
  python main.py --test                   # Quick system test
  python main.py --story-id demo-story    # Load specific story
  python main.py --non-interactive        # Automation mode
  python main.py --input "Look around"    # Single input processing
  python main.py --api                    # Start API server
  python main.py --web                    # Start web interface
        """
    )
    
    # Version argument (standard)
    parser.add_argument('--version', action='version', version=f'OpenChronicle {__version__}')
    
    # Interface selection (new)
    interface_group = parser.add_argument_group('Interface Options')
    interface_group.add_argument('--cli', action='store_true', default=True,
                        help='Use CLI interface (default)')
    interface_group.add_argument('--api', action='store_true',
                        help='Start API server interface')
    interface_group.add_argument('--web', action='store_true', 
                        help='Start web interface')
    interface_group.add_argument('--events', action='store_true',
                        help='Start event/WebSocket interface')
    interface_group.add_argument('--all-interfaces', action='store_true',
                        help='Start all interfaces (API, Web, Events)')
    
    # CLI-specific options (legacy compatibility)
    cli_group = parser.add_argument_group('CLI Options')
    cli_group.add_argument('--test', action='store_true',
                        help='Run quick system test and exit')
    cli_group.add_argument('--non-interactive', action='store_true',
                        help='Run in non-interactive mode (for testing/automation)')
    cli_group.add_argument('--story-id', type=str, default='demo-story', metavar='ID',
                        help='Story ID to load (default: demo-story)')
    cli_group.add_argument('--input', type=str, metavar='TEXT',
                        help='Single input to process in non-interactive mode')
    cli_group.add_argument('--max-iterations', type=int, default=1, metavar='N',
                        help='Maximum iterations in non-interactive mode (default: 1)')
    cli_group.add_argument('--no-emojis', action='store_true',
                        help='Disable emoji output for professional/clean display')
    
    # API Key management (legacy compatibility)
    key_group = parser.add_argument_group('API Key Management')
    key_group.add_argument('--set-key', type=str, metavar='PROVIDER',
                        help='Store API key for provider (openai, anthropic, etc.)')
    key_group.add_argument('--list-keys', action='store_true',
                        help='List stored API keys')
    key_group.add_argument('--remove-key', type=str, metavar='PROVIDER',
                        help='Remove stored API key for provider')
    key_group.add_argument('--keyring-info', action='store_true',
                        help='Show keyring backend information')
    
    return parser.parse_args()


async def handle_key_management_commands(args) -> bool:
    """
    Handle API key management commands (legacy compatibility).
    
    Returns:
        True if a key command was processed (exit after), False to continue
    """
    if not any([args.set_key, args.list_keys, args.remove_key, args.keyring_info]):
        return False
    
    # Import legacy key management with fallback
    sys.path.append(str(Path(__file__).parent / "utilities"))
    try:
        from api_key_manager import (
            prompt_and_store_key, list_stored_keys, remove_api_key, 
            get_keyring_info, is_keyring_available
        )
    except ImportError:
        # Fallback stubs if API key manager is not available
        def prompt_and_store_key(provider):
            print(f"❌ API key management not available - api_key_manager module not found")
            return False
        def list_stored_keys():
            print(f"❌ API key management not available - api_key_manager module not found")
            return []
        def remove_api_key(provider):
            print(f"❌ API key management not available - api_key_manager module not found")
            return False
        def get_keyring_info():
            return {
                'available': False,
                'backend': 'Not available',
                'service_name': 'Not available',
                'supported_providers': [],
                'reason': 'API key manager module not found',
                'recommendation': 'Install or configure api_key_manager module'
            }
        def is_keyring_available():
            return False
    
    def status_icon(success: bool = True) -> str:
        return "✅" if success else "❌"
    
    def emoji(text: str) -> str:
        return text if not args.no_emojis else ""
    
    try:
        if args.keyring_info:
            info = get_keyring_info()
            print(f"\n{emoji('🔐 ')}Keyring Information:")
            print(f"   Available: {info['available']}")
            if info['available']:
                print(f"   Backend: {info['backend']}")
                print(f"   Service: {info['service_name']}")
                print(f"   Supported providers: {', '.join(info['supported_providers'])}")
            else:
                print(f"   Reason: {info['reason']}")
                print(f"   Fix: {info['recommendation']}")
        
        elif args.list_keys:
            if not is_keyring_available():
                print(f"{status_icon(False)} Keyring not available. Install with: pip install keyring")
                return True
            
            stored = list_stored_keys()
            if not stored:
                print(f"\n{emoji('🔑 ')}No API keys stored in secure storage.")
                print("Use --set-key PROVIDER to store API keys securely.")
            else:
                print(f"\n{emoji('🗄️ ')}Stored API Keys ({len(stored)}):")
                for provider in sorted(stored):
                    print(f"   {emoji('✅ ')}{provider}")
                print(f"\nUse --remove-key PROVIDER to remove a key.")
        
        elif args.set_key:
            provider = args.set_key.lower()
            success = prompt_and_store_key(provider)
            if success:
                print(f"\n{status_icon(True)} API key management completed successfully!")
            else:
                print(f"\n{status_icon(False)} API key setup failed.")
        
        elif args.remove_key:
            provider = args.remove_key.lower()
            success = remove_api_key(provider)
            if success:
                print(f"{status_icon(True)} API key removed for {provider}")
            else:
                print(f"{status_icon(False)} Failed to remove API key for {provider}")
        
        return True
        
    except Exception as e:
        print(f"{status_icon(False)} Error in key management: {e}")
        return True


async def run_cli_interface(args, container: InfrastructureContainer) -> int:
    """Run the CLI interface."""
    
    # Create CLI application
    cli_config = CLIAppConfig(
        use_emojis=not args.no_emojis,
        default_story_id=args.story_id,
        enable_health_check=True,
        enable_interactive_mode=not args.non_interactive,
        max_iterations_non_interactive=args.max_iterations
    )
    
    story_processing_config = StoryProcessingConfig()
    
    from openchronicle.applications.cli_app import CLIApplicationFactory
    
    cli_app = CLIApplicationFactory.create(
        story_service=container.story_service(),
        character_service=container.character_service(), 
        scene_service=container.scene_service(),
        memory_service=container.memory_service(),
        logging_service=container.logging_service(),
        cache_service=container.cache_service(),
        config=cli_config,
        story_processing_config=story_processing_config
    )
    
    # Run startup sequence
    startup_ok = await cli_app.run_startup_sequence()
    if not startup_ok:
        return 1
    
    try:
        # Handle different CLI modes
        if args.test:
            success = await cli_app.run_quick_test()
            return 0 if success else 1
        
        elif args.non_interactive:
            test_inputs = [args.input] if args.input else None
            await cli_app.run_non_interactive_mode(
                args.story_id,
                test_inputs=test_inputs,
                max_iterations=args.max_iterations
            )
            return 0
        
        else:
            # Interactive mode
            await cli_app.run_interactive_mode(args.story_id)
            return 0
            
    except KeyboardInterrupt:
        print(f"\n{cli_app._emoji('👋')} Interrupted by user")
        return 0
    except Exception as e:
        print(f"CLI application error: {e}")
        await container.logging_service().log_error(f"CLI application error: {e}")
        return 1


async def run_api_interface(args) -> int:
    """Run the API interface."""
    try:
        from openchronicle.interfaces.api import APIContainer
        
        api_container = APIContainer()
        app = api_container.app()
        
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return 0
        
    except Exception as e:
        print(f"API interface error: {e}")
        return 1


async def run_web_interface(args) -> int:
    """Run the web interface."""
    try:
        from openchronicle.interfaces.web import WebAppContainer
        
        web_container = WebAppContainer()
        app = web_container.app()
        
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8080)
        return 0
        
    except Exception as e:
        print(f"Web interface error: {e}")
        return 1


async def run_events_interface(args) -> int:
    """Run the events/WebSocket interface."""
    try:
        from openchronicle.interfaces.events import EventApplication
        
        event_app = EventApplication()
        await event_app.run()
        return 0
        
    except Exception as e:
        print(f"Events interface error: {e}")
        return 1


async def run_all_interfaces(args) -> int:
    """Run all interfaces concurrently."""
    try:
        from openchronicle.interfaces import run_all_servers
        
        await run_all_servers()
        return 0
        
    except Exception as e:
        print(f"Multi-interface error: {e}")
        return 1


async def main() -> int:
    """Main entry point for OpenChronicle."""
    
    # Parse arguments
    args = parse_arguments()
    
    # Handle API key management commands first (before heavy imports)
    if await handle_key_management_commands(args):
        return 0
    
    # Determine which interface to run
    if args.all_interfaces:
        return await run_all_interfaces(args)
    elif args.api:
        return await run_api_interface(args)
    elif args.web:
        return await run_web_interface(args)
    elif args.events:
        return await run_events_interface(args)
    else:
        # CLI is default, and also handles test and non-interactive modes
        
        # Create infrastructure container
        try:
            from openchronicle.infrastructure.config import InfrastructureConfig
            
            config = InfrastructureConfig()
            container = InfrastructureContainer(config)
            
            return await run_cli_interface(args, container)
            
        except Exception as e:
            print(f"Failed to initialize infrastructure: {e}")
            return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
