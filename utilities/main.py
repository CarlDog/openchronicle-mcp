#!/usr/bin/env python3
"""
OpenChronicle Utilities Main Entry Point

A unified command-line interface for all OpenChronicle utility functions including
maintenance, configuration management, system health checks, and data management.

Usage:
    python utilities/main.py <command> [options]
    python -m utilities.main <command> [options]

Available Commands:
    chatbot-importer    Import chatbot conversation data into OpenChronicle format
    assistant-importer  Import AI assistant conversation data into OpenChronicle format
    
Note: Importer utilities are currently in development phase.
Run 'python utilities/main.py <command> --help' for command-specific options.
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import utility modules (with graceful fallbacks for development)
# Note: Importer utilities are in development
CHATBOT_IMPORTER_AVAILABLE = False
ASSISTANT_IMPORTER_AVAILABLE = False
STORYPACK_IMPORTER_AVAILABLE = False

# TODO: Enable these imports as utilities are implemented
# try:
#     from utilities.chatbot_importer import ChatbotImporter
#     CHATBOT_IMPORTER_AVAILABLE = True
# except ImportError:
#     CHATBOT_IMPORTER_AVAILABLE = False

# try:
#     from utilities.assistant_importer import AssistantImporter
#     ASSISTANT_IMPORTER_AVAILABLE = True
# except ImportError:
#     ASSISTANT_IMPORTER_AVAILABLE = False


class UtilitiesMain:
    """Main utilities command-line interface."""
    
    def __init__(self):
        self.commands = {
            'chatbot-importer': {
                'handler': self.cmd_chatbot_importer,
                'available': CHATBOT_IMPORTER_AVAILABLE,
                'description': 'Import chatbot conversation data into OpenChronicle format'
            },
            'assistant-importer': {
                'handler': self.cmd_assistant_importer,
                'available': ASSISTANT_IMPORTER_AVAILABLE,
                'description': 'Import AI assistant conversation data into OpenChronicle format'
            },
            'storypack-importer': {
                'handler': self.cmd_storypack_importer,
                'available': STORYPACK_IMPORTER_AVAILABLE,
                'description': 'Import storypack files into OpenChronicle format (replaces legacy storypack_import)'
            }
        }
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            prog='utilities',
            description='OpenChronicle Utilities - Maintenance and Management Tools',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_epilog()
        )
        
        # Global options
        parser.add_argument(
            '--version',
            action='version',
            version='OpenChronicle Utilities v1.0.0'
        )
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose output'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing (where supported)'
        )
        
        # Subcommands
        subparsers = parser.add_subparsers(
            dest='command',
            help='Available utility commands',
            metavar='COMMAND'
        )
        
        # Add subcommand parsers
        self._add_chatbot_importer_parser(subparsers)
        self._add_assistant_importer_parser(subparsers)
        self._add_storypack_importer_parser(subparsers)
        
        return parser
    
    def _get_epilog(self) -> str:
        """Generate epilog with available commands."""
        available_commands = []
        unavailable_commands = []
        
        for cmd, info in self.commands.items():
            if info['available']:
                available_commands.append(f"  {cmd:<18} {info['description']}")
            else:
                unavailable_commands.append(f"  {cmd:<18} {info['description']} (not yet implemented)")
        
        epilog = "Available Commands:\n"
        if available_commands:
            epilog += "\n".join(available_commands)
        
        if unavailable_commands:
            epilog += "\n\nUpcoming Commands:\n"
            epilog += "\n".join(unavailable_commands)
        
        epilog += "\n\nFor command-specific help: utilities main.py <command> --help"
        return epilog
    
    # ===========================
    # SUBCOMMAND PARSER CREATION
    # ===========================
    
    def _add_chatbot_importer_parser(self, subparsers):
        """Add chatbot-importer subcommand parser."""
        parser = subparsers.add_parser(
            'chatbot-importer',
            help='Import chatbot conversation data',
            description='Import chatbot conversation data into OpenChronicle format'
        )
        parser.add_argument(
            'source_path',
            help='Path to source file or directory containing chatbot conversation data'
        )
        parser.add_argument(
            'output_path',
            help='Path for output OpenChronicle story directory'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'csv', 'txt', 'auto'],
            default='auto',
            help='Input format (default: auto-detect)'
        )
        parser.add_argument(
            '--name',
            help='Name for the imported story (default: derived from source)'
        )
        parser.add_argument(
            '--description',
            help='Description for the imported story'
        )
        parser.add_argument(
            '--merge-messages',
            action='store_true',
            help='Merge consecutive messages from same speaker'
        )
        parser.add_argument(
            '--preserve-timestamps',
            action='store_true',
            help='Preserve original message timestamps'
        )
    
    def _add_assistant_importer_parser(self, subparsers):
        """Add assistant-importer subcommand parser."""
        parser = subparsers.add_parser(
            'assistant-importer',
            help='Import AI assistant conversation data',
            description='Import AI assistant conversation data into OpenChronicle format'
        )
        parser.add_argument(
            'source_path',
            help='Path to source file or directory containing assistant conversation data'
        )
        parser.add_argument(
            'output_path',
            help='Path for output OpenChronicle story directory'
        )
        parser.add_argument(
            '--assistant-type',
            choices=['chatgpt', 'claude', 'copilot', 'gemini', 'generic'],
            default='generic',
            help='Type of AI assistant (default: generic)'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'markdown', 'html', 'txt', 'auto'],
            default='auto',
            help='Input format (default: auto-detect)'
        )
        parser.add_argument(
            '--name',
            help='Name for the imported story (default: derived from source)'
        )
        parser.add_argument(
            '--description',
            help='Description for the imported story'
        )
        parser.add_argument(
            '--include-system-messages',
            action='store_true',
            help='Include system/instruction messages in import'
        )
        parser.add_argument(
            '--split-by-session',
            action='store_true',
            help='Split conversations into separate sessions/chapters'
        )
    
    def _add_storypack_importer_parser(self, subparsers):
        """Add storypack-importer subcommand parser."""
        parser = subparsers.add_parser(
            'storypack-importer',
            help='Import storypack files into OpenChronicle format',
            description='Import storypack files (.zip, .json, .tar.gz) into OpenChronicle format. Replaces legacy storypack_import functionality.'
        )
        parser.add_argument(
            'source_path',
            help='Path to storypack file or directory containing storypacks'
        )
        parser.add_argument(
            'output_path',
            nargs='?',
            help='Path for imported stories (default: current directory)'
        )
        parser.add_argument(
            '--validate-strict',
            action='store_true',
            help='Enable strict validation mode with comprehensive checks'
        )
        parser.add_argument(
            '--batch',
            action='store_true',
            help='Process all storypacks in source directory'
        )
        parser.add_argument(
            '--preview-only',
            action='store_true',
            help='Show storypack contents without importing'
        )
        parser.add_argument(
            '--stories',
            help='Comma-separated list of specific stories to import'
        )
        parser.add_argument(
            '--characters',
            help='Comma-separated list of specific characters to import'
        )
        parser.add_argument(
            '--output-format',
            choices=['json', 'yaml', 'summary'],
            default='summary',
            help='Format for import reports (default: summary)'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup before import'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Override validation warnings and proceed with import'
        )
    
    # ===========================
    # COMMAND IMPLEMENTATIONS
    # ===========================
    
    async def cmd_chatbot_importer(self, args) -> int:
        """Handle chatbot-importer command."""
        if not CHATBOT_IMPORTER_AVAILABLE:
            print("❌ Chatbot importer functionality not yet implemented")
            print("   This utility will import chatbot conversation data")
            return 1
        
        try:
            print(f"🤖 Starting chatbot import from {args.source_path}")
            print(f"📁 Output destination: {args.output_path}")
            print(f"📄 Format: {args.format}")
            
            # Validate paths
            if not os.path.exists(args.source_path):
                print(f"❌ Source path does not exist: {args.source_path}")
                return 1
            
            # TODO: Implement actual chatbot import logic
            print("✅ Chatbot import completed successfully")
            return 0
            
        except Exception as e:
            print(f"❌ Error during chatbot import: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    async def cmd_assistant_importer(self, args) -> int:
        """Handle assistant-importer command."""
        if not ASSISTANT_IMPORTER_AVAILABLE:
            print("❌ Assistant importer functionality not yet implemented")
            print("   This utility will import AI assistant conversation data")
            return 1
        
        try:
            print(f"🤖 Starting assistant import from {args.source_path}")
            print(f"📁 Output destination: {args.output_path}")
            print(f"🤖 Assistant type: {args.assistant_type}")
            print(f"📄 Format: {args.format}")
            
            # Validate paths
            if not os.path.exists(args.source_path):
                print(f"❌ Source path does not exist: {args.source_path}")
                return 1
            
            # TODO: Implement actual assistant import logic
            print("✅ Assistant import completed successfully")
            return 0
            
        except Exception as e:
            print(f"❌ Error during assistant import: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    async def cmd_storypack_importer(self, args) -> int:
        """Handle storypack-importer command."""
        if not STORYPACK_IMPORTER_AVAILABLE:
            print("❌ Storypack importer functionality not yet implemented")
            print("   This utility will replace the legacy storypack_import functionality")
            print("   with robust import capabilities for .zip, .json, and .tar.gz storypack files")
            return 1
        
        try:
            print(f"📦 Starting storypack import from {args.source_path}")
            if args.output_path:
                print(f"📁 Output destination: {args.output_path}")
            
            # Validate paths
            if not os.path.exists(args.source_path):
                print(f"❌ Source path does not exist: {args.source_path}")
                return 1
            
            # Show what would be done
            if args.preview_only:
                print("👀 Preview mode - showing storypack contents")
            elif args.batch:
                print("📦 Batch mode - processing all storypacks in directory")
            elif args.stories:
                print(f"🎯 Selective import - stories: {args.stories}")
            elif args.characters:
                print(f"👥 Selective import - characters: {args.characters}")
            
            if args.validate_strict:
                print("🔍 Strict validation mode enabled")
            if args.backup:
                print("💾 Backup mode enabled")
            if args.force:
                print("⚠️  Force mode - overriding validation warnings")
            
            # TODO: Implement actual storypack import logic
            print("✅ Storypack import completed successfully")
            return 0
            
        except Exception as e:
            print(f"❌ Error during storypack import: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    # ===========================
    # MAIN EXECUTION
    # ===========================
    
    async def run(self, argv: Optional[list] = None) -> int:
        """Main entry point for utilities."""
        parser = self.create_parser()
        args = parser.parse_args(argv)
        
        # Handle no command
        if not hasattr(args, 'command') or args.command is None:
            parser.print_help()
            return 0
        
        # Check if command is available
        if args.command not in self.commands:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
            return 1
        
        command_info = self.commands[args.command]
        if not command_info['available']:
            print(f"⚠️  Command '{args.command}' is not yet implemented")
            print(f"   {command_info['description']}")
            return 1
        
        # Execute command
        try:
            return await command_info['handler'](args)
        except KeyboardInterrupt:
            print("\n⚠️  Operation cancelled by user")
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            return 1


def main():
    """Entry point for utilities main."""
    utilities_main = UtilitiesMain()
    
    # Run with asyncio support
    try:
        exit_code = asyncio.run(utilities_main.run())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
