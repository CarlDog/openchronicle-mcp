#!/usr/bin/env python3
"""
OpenChronicle Performance Monitoring CLI

Command-line interface for the modular performance monitoring system.
Provides access to metrics, analysis, and reporting functionality.
"""

import asyncio
import json
import click
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .orchestrator import PerformanceOrchestrator
from .interfaces.performance_interfaces import OperationContext, MetricsQuery
from utilities.logging_system import get_logger, log_system_event


class PerformanceCLI:
    """Command-line interface for performance monitoring."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.logger = get_logger()
        self.orchestrator = PerformanceOrchestrator()
    
    async def get_status(self) -> dict:
        """Get current performance monitoring status."""
        try:
            # Get real-time metrics
            real_time_metrics = await self.orchestrator.get_real_time_metrics()
            
            # Get monitoring status
            monitoring_status = self.orchestrator.get_monitoring_status()
            
            return {
                'status': 'operational',
                'monitoring': monitoring_status,
                'real_time': real_time_metrics
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def analyze_performance(self, hours: int = 24, adapter: Optional[str] = None) -> dict:
        """Analyze performance for a specified time period."""
        try:
            # Calculate time period
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            time_period = (start_time, end_time)
            
            # Perform analysis
            analysis = await self.orchestrator.analyze_performance(time_period, adapter)
            
            return {
                'status': 'success',
                'analysis': analysis
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze performance: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_data(self, retention_days: int = 30) -> dict:
        """Clean up old performance data."""
        try:
            cleanup_stats = await self.orchestrator.cleanup_old_data(retention_days)
            
            return {
                'status': 'success',
                'cleanup': cleanup_stats
            }
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup data: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def generate_report(self, hours: int = 24, output_file: Optional[str] = None) -> dict:
        """Generate a performance report."""
        try:
            # Calculate time period
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            time_period = (start_time, end_time)
            
            # Generate report
            report = await self.orchestrator.generate_performance_report(time_period)
            
            # Save to file if specified
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w') as f:
                    json.dump(report, f, indent=2)
                
                return {
                    'status': 'success',
                    'message': f'Report saved to {output_file}',
                    'report_summary': {
                        'generated_at': report.get('generated_at'),
                        'time_period': report.get('data', {}).get('time_period')
                    }
                }
            else:
                return {
                    'status': 'success',
                    'report': report
                }
            
        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def enable_monitoring(self) -> dict:
        """Enable performance monitoring."""
        try:
            self.orchestrator.enable_monitoring()
            
            log_system_event("performance_cli", "Monitoring enabled via CLI", {})
            
            return {
                'status': 'success',
                'message': 'Performance monitoring enabled'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to enable monitoring: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def disable_monitoring(self) -> dict:
        """Disable performance monitoring."""
        try:
            self.orchestrator.disable_monitoring()
            
            log_system_event("performance_cli", "Monitoring disabled via CLI", {})
            
            return {
                'status': 'success',
                'message': 'Performance monitoring disabled'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to disable monitoring: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# Click CLI commands
@click.group(name='performance')
@click.pass_context
def performance_cli(ctx):
    """OpenChronicle Performance Monitoring CLI"""
    ctx.ensure_object(dict)
    ctx.obj['cli'] = PerformanceCLI()


@performance_cli.command()
@click.pass_context
def status(ctx):
    """Get current performance monitoring status"""
    cli = ctx.obj['cli']
    
    async def _status():
        result = await cli.get_status()
        click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_status())


@performance_cli.command()
@click.option('--hours', default=24, help='Number of hours to analyze (default: 24)')
@click.option('--adapter', help='Filter by specific adapter name')
@click.pass_context
def analyze(ctx, hours, adapter):
    """Analyze performance for a specified time period"""
    cli = ctx.obj['cli']
    
    async def _analyze():
        result = await cli.analyze_performance(hours, adapter)
        click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_analyze())


@performance_cli.command()
@click.option('--retention-days', default=30, help='Retention period in days (default: 30)')
@click.pass_context
def cleanup(ctx, retention_days):
    """Clean up old performance data"""
    cli = ctx.obj['cli']
    
    async def _cleanup():
        result = await cli.cleanup_data(retention_days)
        click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_cleanup())


@performance_cli.command()
@click.option('--hours', default=24, help='Number of hours for report (default: 24)')
@click.option('--output', help='Output file path (optional)')
@click.pass_context
def report(ctx, hours, output):
    """Generate a performance report"""
    cli = ctx.obj['cli']
    
    async def _report():
        result = await cli.generate_report(hours, output)
        click.echo(json.dumps(result, indent=2))
    
    asyncio.run(_report())


@performance_cli.command()
@click.pass_context
def enable(ctx):
    """Enable performance monitoring"""
    cli = ctx.obj['cli']
    result = cli.enable_monitoring()
    click.echo(json.dumps(result, indent=2))


@performance_cli.command()
@click.pass_context
def disable(ctx):
    """Disable performance monitoring"""
    cli = ctx.obj['cli']
    result = cli.disable_monitoring()
    click.echo(json.dumps(result, indent=2))


# Helper function for programmatic usage
async def run_performance_command(command: str, **kwargs) -> dict:
    """Run a performance monitoring command programmatically."""
    cli = PerformanceCLI()
    
    if command == 'status':
        return await cli.get_status()
    elif command == 'analyze':
        return await cli.analyze_performance(
            kwargs.get('hours', 24),
            kwargs.get('adapter')
        )
    elif command == 'cleanup':
        return await cli.cleanup_data(kwargs.get('retention_days', 30))
    elif command == 'report':
        return await cli.generate_report(
            kwargs.get('hours', 24),
            kwargs.get('output_file')
        )
    elif command == 'enable':
        return cli.enable_monitoring()
    elif command == 'disable':
        return cli.disable_monitoring()
    else:
        return {
            'status': 'error',
            'error': f'Unknown command: {command}'
        }


if __name__ == '__main__':
    performance_cli()
