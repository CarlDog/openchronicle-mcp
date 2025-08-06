#!/usr/bin/env python3
"""
OpenChronicle Database Health Validator

Comprehensive database integrity validation for OpenChronicle systems.
Implements Phase 1 Week 4 database health check requirements:
- Run PRAGMA integrity_check on startup
- Early detection of database corruption
- System health validation before normal operation

This validator should be run on system startup or before main application execution.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.database_systems.database_orchestrator import startup_health_check, get_all_databases
from utilities.logging_system import log_system_event, log_error, log_info, log_warning


async def main():
    """
    Main startup health check function.
    
    Implementation matches Development Master Plan specification:
    ```python
    async def startup_health_check():
        for db_path in self.get_all_databases():
            async with aiosqlite.connect(db_path) as conn:
                result = await conn.execute("PRAGMA integrity_check")
                if result != "ok":
                    log_error(f"Database corruption detected: {db_path}")
    ```
    """
    print("🏥 OpenChronicle Database Health Validator")
    print("=" * 50)
    
    try:
        log_info("Starting OpenChronicle startup health check")
        
        # Run comprehensive health check
        health_report = await startup_health_check()
        
        # Display results
        print(f"⏰ Health Check Completed: {health_report['timestamp']}")
        print(f"📊 Databases Checked: {health_report['databases_checked']}")
        print(f"🔍 Issues Found: {health_report['issues_found']}")
        print(f"📈 Overall Status: {health_report['overall_status'].upper()}")
        
        if health_report['overall_status'] == 'healthy':
            print("✅ All systems healthy - startup can proceed")
            log_info("Startup health check passed - all systems healthy")
            return 0
        
        elif health_report['overall_status'] == 'warning':
            print("⚠️  System warnings detected but startup can proceed")
            print("\n🔧 Recommendations:")
            for rec in health_report.get('recommendations', []):
                print(f"  • {rec}")
            
            log_warning(f"Startup health check completed with warnings: {health_report['issues_found']} issues")
            return 0
        
        else:  # critical or error
            print("🚨 CRITICAL ISSUES DETECTED - Startup should not proceed")
            print("\n💥 Critical Issues:")
            
            for db_id, db_info in health_report.get('databases', {}).items():
                if db_info.get('status') in ['corrupt', 'error']:
                    print(f"  • Database '{db_id}': {db_info['status']}")
                    for issue in db_info.get('issues', []):
                        print(f"    - {issue}")
            
            print("\n🔧 Immediate Actions Required:")
            for rec in health_report.get('recommendations', []):
                print(f"  • {rec}")
            
            log_error(f"Startup health check failed: {health_report['issues_found']} critical issues detected")
            return 1
    
    except Exception as e:
        print(f"🚨 Health check failed with error: {str(e)}")
        log_error(f"Startup health check failed with exception: {str(e)}")
        return 1


def display_detailed_report(health_report):
    """Display detailed health report."""
    print("\n📋 Detailed Health Report")
    print("-" * 30)
    
    for db_id, db_info in health_report.get('databases', {}).items():
        print(f"\n🗄️  Database: {db_id}")
        print(f"   Status: {db_info['status']}")
        print(f"   Size: {db_info.get('size_bytes', 0):,} bytes")
        
        if db_info.get('issues'):
            print("   Issues:")
            for issue in db_info['issues']:
                print(f"     - {issue}")
        
        # Display check results
        checks = db_info.get('checks', {})
        print("   Checks:")
        for check_name, result in checks.items():
            status = "✅" if result == True or result == "ok" else "❌" if result == False or result == "failed" else "⚠️"
            print(f"     {status} {check_name}: {result}")
        
        # Display details if available
        details = db_info.get('details', {})
        if details:
            if 'fragmentation_ratio' in details:
                frag_pct = details['fragmentation_ratio'] * 100
                print(f"   Fragmentation: {frag_pct:.1f}%")
            
            if 'table_counts' in details:
                print("   Table Counts:")
                for table, count in details['table_counts'].items():
                    print(f"     {table}: {count:,} rows")


if __name__ == "__main__":
    # Add command line arguments support
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenChronicle Database Health Validator")
    parser.add_argument("--detailed", action="store_true", help="Show detailed health report")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    
    # Run health check
    exit_code = asyncio.run(main())
    
    if args.detailed or args.json:
        # Re-run to get detailed report
        async def get_detailed_report():
            return await startup_health_check()
        
        health_report = asyncio.run(get_detailed_report())
        
        if args.json:
            print("\n" + json.dumps(health_report, indent=2))
        elif args.detailed:
            display_detailed_report(health_report)
    
    sys.exit(exit_code)
