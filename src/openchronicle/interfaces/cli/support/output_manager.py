"""
Professional output management for OpenChronicle CLI.

Provides consistent, beautiful output formatting with multiple format options.
Uses Rich for enhanced terminal output with colors, tables, and progress bars.
"""

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.table import Table
from rich.tree import Tree


class OutputManager:
    """Manages consistent output formatting across all CLI commands."""

    def __init__(self, format_type: str = "rich", quiet: bool = False):
        """
        Initialize the output manager.
        
        Args:
            format_type: Output format ("rich", "json", "plain", "table")
            quiet: If True, suppress non-essential output
        """
        self.format_type = format_type.lower()
        self.quiet = quiet
        self.console = Console(stderr=False) if not quiet else Console(file=sys.stderr)

    def success(self, message: str, data: dict[str, Any] | None = None):
        """Display a success message."""
        if self.format_type == "json":
            output = {"status": "success", "message": message}
            if data:
                output["data"] = data
            print(json.dumps(output, indent=2))
        elif self.format_type == "plain":
            print(f"✅ {message}")
        else:  # rich
            self.console.print(f"✅ [green]{message}[/green]")

    def error(self, message: str, error: Exception | None = None, exit_code: int = 1):
        """Display an error message and optionally exit."""
        if self.format_type == "json":
            output = {"status": "error", "message": message}
            if error:
                output["error"] = str(error)
            print(json.dumps(output, indent=2))
        elif self.format_type == "plain":
            print(f"❌ {message}")
        else:  # rich
            self.console.print(f"❌ [red]{message}[/red]")

        if exit_code > 0:
            sys.exit(exit_code)

    def warning(self, message: str):
        """Display a warning message."""
        if self.format_type == "json":
            print(json.dumps({"status": "warning", "message": message}, indent=2))
        elif self.format_type == "plain":
            print(f"⚠️  {message}")
        else:  # rich
            self.console.print(f"⚠️  [yellow]{message}[/yellow]")

    def info(self, message: str):
        """Display an informational message."""
        if self.quiet:
            return

        if self.format_type == "json":
            print(json.dumps({"status": "info", "message": message}, indent=2))
        elif self.format_type == "plain":
            print(f"ℹ️  {message}")
        else:  # rich
            self.console.print(f"ℹ️  [blue]{message}[/blue]")

    def table(self, data: list[dict[str, Any]], title: str = "", headers: list[str] | None = None):
        """Display data in table format."""
        if not data:
            self.warning("No data to display")
            return

        if self.format_type == "json":
            output = {"title": title, "data": data}
            print(json.dumps(output, indent=2))
        elif self.format_type == "plain":
            # Simple table formatting for plain text
            if title:
                print(f"\n{title}")
                print("-" * len(title))

            if headers is None and data:
                headers = list(data[0].keys())

            # Print headers
            if headers:
                print(" | ".join(str(h).ljust(15) for h in headers))
                print("-" * (len(headers) * 17))

            # Print rows
            for row in data:
                values = [str(row.get(h, "")).ljust(15) for h in headers] if headers else [str(v).ljust(15) for v in row.values()]
                print(" | ".join(values))
        else:  # rich
            table = Table(title=title if title else None)

            # Auto-generate columns from first row if headers not provided
            if headers is None and data:
                headers = list(data[0].keys())

            if headers:
                for header in headers:
                    table.add_column(header.replace("_", " ").title())

                for row in data:
                    values = [str(row.get(h, "")) for h in headers]
                    table.add_row(*values)
            else:
                # Fallback if no consistent structure
                for key in data[0].keys() if data else []:
                    table.add_column(key.replace("_", " ").title())
                for row in data:
                    table.add_row(*[str(v) for v in row.values()])

            self.console.print(table)

    def panel(self, content: str, title: str = "", style: str = ""):
        """Display content in a panel (Rich format only)."""
        if self.format_type == "rich":
            panel = Panel(content, title=title, border_style=style if style else "blue")
            self.console.print(panel)
        elif title:
            self.info(f"{title}: {content}")
        else:
            self.info(content)

    def tree(self, data: dict[str, Any], title: str = ""):
        """Display hierarchical data as a tree (Rich format only)."""
        if self.format_type == "rich":
            tree = Tree(title if title else "Data")
            self._build_tree(tree, data)
            self.console.print(tree)
        # Fallback to JSON for other formats
        elif self.format_type == "json":
            output = {"title": title, "data": data}
            print(json.dumps(output, indent=2))
        else:
            print(f"\n{title}:" if title else "Data:")
            self._print_dict_plain(data)

    def _build_tree(self, tree: Tree, data: dict | list | Any, max_depth: int = 3, current_depth: int = 0):
        """Recursively build a Rich tree from data."""
        if current_depth >= max_depth:
            tree.add("[dim]...(truncated)[/dim]")
            return

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)) and value:
                    branch = tree.add(f"[bold]{key}[/bold]")
                    self._build_tree(branch, value, max_depth, current_depth + 1)
                else:
                    tree.add(f"{key}: [cyan]{value}[/cyan]")
        elif isinstance(data, list):
            for i, item in enumerate(data[:10]):  # Limit to first 10 items
                if isinstance(item, (dict, list)):
                    branch = tree.add(f"[bold][{i}][/bold]")
                    self._build_tree(branch, item, max_depth, current_depth + 1)
                else:
                    tree.add(f"[{i}]: [cyan]{item}[/cyan]")
            if len(data) > 10:
                tree.add("[dim]...(showing first 10 items)[/dim]")
        else:
            tree.add(f"[cyan]{data}[/cyan]")

    def _print_dict_plain(self, data: dict[str, Any], indent: int = 0):
        """Print dictionary in plain text format with indentation."""
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                self._print_dict_plain(value, indent + 1)
            elif isinstance(value, list):
                print(f"{prefix}{key}: [{len(value)} items]")
                for i, item in enumerate(value[:5]):  # Show first 5 items
                    print(f"{prefix}  [{i}]: {item}")
                if len(value) > 5:
                    print(f"{prefix}  ...(showing first 5 of {len(value)} items)")
            else:
                print(f"{prefix}{key}: {value}")

    def progress_context(self, description: str = "Processing..."):
        """Return a Rich progress context manager."""
        if self.format_type == "rich":
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            )
        # Simple progress for non-rich formats
        return _PlainProgress(description)

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for user confirmation."""
        if self.format_type == "rich":
            self.console.print(f"[yellow]{message}[/yellow] [dim]({'Y/n' if default else 'y/N'})[/dim]: ", end="")
        else:
            print(f"{message} ({'Y/n' if default else 'y/N'}): ", end="")

        try:
            response = input().strip().lower()
            if not response:
                return default
            return response in ['y', 'yes', 'true', '1']
        except (EOFError, KeyboardInterrupt):
            print()  # New line after interrupt
            return False


class _PlainProgress:
    """Simple progress indicator for non-rich output formats."""

    def __init__(self, description: str):
        self.description = description

    def __enter__(self):
        print(f"{self.description}...", end="", flush=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            print(" ✅")
        else:
            print(" ❌")

    def add_task(self, description: str, total: int | None = None):
        """Add a task (simplified for plain progress)."""
        return description

    def update(self, task_id: Any, advance: int = 1, description: str = None):
        """Update progress (simplified for plain progress)."""
        print(".", end="", flush=True)
