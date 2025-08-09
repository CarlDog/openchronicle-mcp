"""
Database health checker for startup integrity validation.

Implements startup health checks including database integrity validation,
connection testing, and corruption detection as specified in Development Master Plan Phase 1 Week 4.
"""

import aiosqlite
import sqlite3
import asyncio
import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from .connection import ConnectionManager
from .shared import DatabaseConfig
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.shared.logging_system import log_system_event, log_error, log_info, log_warning


class DatabaseHealthChecker:
    """
    Database health and integrity checker.
    
    Implements startup health checks as specified in Development Master Plan:
    - PRAGMA integrity_check on all databases
    - Early detection of database corruption
    - Connection validation
    - Schema validation
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        
    async def startup_health_check(self) -> Dict[str, Any]:
        """
        Run comprehensive startup health check on all databases.
        
        Returns:
            Dict containing health check results with status, issues, and recommendations
        """
        log_info("Starting database health check...")
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "databases_checked": 0,
            "issues_found": 0,
            "databases": {},
            "recommendations": []
        }
        
        try:
            # Get all database paths
            db_paths = await self._discover_databases()
            health_report["databases_checked"] = len(db_paths)
            
            if not db_paths:
                log_warning("No databases found for health check")
                health_report["overall_status"] = "warning"
                health_report["recommendations"].append("No databases found - consider initializing the system")
                return health_report
            
            # Check each database
            for db_path in db_paths:
                log_info(f"Checking database: {db_path}")
                db_result = await self._check_single_database(db_path)
                
                # Extract database identifier from path
                db_id = self._get_database_identifier(db_path)
                health_report["databases"][db_id] = db_result
                
                if db_result["status"] != "healthy":
                    health_report["issues_found"] += 1
                    if db_result["status"] == "corrupt":
                        health_report["overall_status"] = "critical"
                    elif health_report["overall_status"] == "healthy":
                        health_report["overall_status"] = "warning"
            
            # Generate recommendations
            health_report["recommendations"] = self._generate_recommendations(health_report)
            
            # Log overall result
            if health_report["overall_status"] == "healthy":
                log_info(f"Database health check completed: {health_report['databases_checked']} databases healthy")
            elif health_report["overall_status"] == "warning":
                log_warning(f"Database health check completed with warnings: {health_report['issues_found']} issues found")
            else:
                log_error(f"Database health check failed: Critical issues found in {health_report['issues_found']} databases")
            
            return health_report
            
        except Exception as e:
            log_error(f"Database health check failed: {str(e)}")
            health_report["overall_status"] = "error"
            health_report["error"] = str(e)
            return health_report
    
    async def _discover_databases(self) -> List[Path]:
        """Discover all SQLite databases in the system."""
        db_paths = []
        
        # Check storage directory structure
        storage_dir = Path("storage")
        if storage_dir.exists():
            # Look for .db files
            db_paths.extend(storage_dir.rglob("*.db"))
            
            # Look for story databases in storypacks
            storypacks_dir = storage_dir / "storypacks"
            if storypacks_dir.exists():
                for story_dir in storypacks_dir.iterdir():
                    if story_dir.is_dir():
                        story_db = story_dir / "story.db"
                        if story_db.exists():
                            db_paths.append(story_db)
        
        # Check for memory system databases
        memory_db_paths = [
            Path("storage/data/memory.db"),
            Path("storage/memory.db")
        ]
        
        for path in memory_db_paths:
            if path.exists():
                db_paths.append(path)
        
        return list(set(db_paths))  # Remove duplicates
    
    async def _check_single_database(self, db_path: Path) -> Dict[str, Any]:
        """
        Check health of a single database.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Dict containing database health status and details
        """
        result = {
            "path": str(db_path),
            "status": "healthy",
            "size_bytes": 0,
            "issues": [],
            "checks": {
                "file_exists": False,
                "file_readable": False,
                "integrity_check": "unknown",
                "connection_test": False,
                "schema_valid": False
            },
            "details": {}
        }
        
        try:
            # File existence check
            if not db_path.exists():
                result["status"] = "missing"
                result["issues"].append("Database file does not exist")
                return result
            
            result["checks"]["file_exists"] = True
            result["size_bytes"] = db_path.stat().st_size
            
            # File readability check
            try:
                with open(db_path, 'rb') as f:
                    f.read(16)  # Read SQLite header
                result["checks"]["file_readable"] = True
            except (IOError, OSError) as e:
                result["status"] = "error"
                result["issues"].append(f"File not readable: {str(e)}")
                return result
            
            # Database connection test
            try:
                async with aiosqlite.connect(str(db_path)) as conn:
                    result["checks"]["connection_test"] = True
                    
                    # Integrity check using PRAGMA
                    cursor = await conn.execute("PRAGMA integrity_check")
                    integrity_result = await cursor.fetchone()
                    await cursor.close()
                    
                    if integrity_result and integrity_result[0] == "ok":
                        result["checks"]["integrity_check"] = "ok"
                    else:
                        result["checks"]["integrity_check"] = "failed"
                        result["status"] = "corrupt"
                        result["issues"].append(f"Integrity check failed: {integrity_result[0] if integrity_result else 'Unknown error'}")
                    
                    # Schema validation
                    schema_result = await self._validate_schema(conn, db_path)
                    result["checks"]["schema_valid"] = schema_result["valid"]
                    if not schema_result["valid"]:
                        result["status"] = "warning" if result["status"] == "healthy" else result["status"]
                        result["issues"].extend(schema_result["issues"])
                    
                    # Additional statistics
                    result["details"] = await self._get_database_details(conn)
                    
            except sqlite3.OperationalError as e:
                result["status"] = "corrupt"
                result["issues"].append(f"Database corruption detected: {str(e)}")
            except Exception as e:
                result["status"] = "error"
                result["issues"].append(f"Connection failed: {str(e)}")
        
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"Health check failed: {str(e)}")
        
        return result
    
    async def _validate_schema(self, conn: aiosqlite.Connection, db_path: Path) -> Dict[str, Any]:
        """Validate database schema structure."""
        schema_result = {
            "valid": True,
            "issues": [],
            "tables_found": [],
            "expected_tables": []
        }
        
        try:
            # Get all tables
            cursor = await conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = await cursor.fetchall()
            await cursor.close()
            
            schema_result["tables_found"] = [table[0] for table in tables]
            
            # Determine expected tables based on database location
            if "memory" in str(db_path).lower():
                expected_tables = ["memory_entries", "character_states", "world_states"]
            else:
                expected_tables = ["scenes", "characters", "memory", "bookmarks"]
            
            schema_result["expected_tables"] = expected_tables
            
            # Check for missing critical tables
            missing_tables = set(expected_tables) - set(schema_result["tables_found"])
            if missing_tables:
                schema_result["valid"] = False
                schema_result["issues"].append(f"Missing tables: {', '.join(missing_tables)}")
            
            # Check for orphaned FTS tables
            fts_tables = [table for table in schema_result["tables_found"] if table.endswith("_fts")]
            for fts_table in fts_tables:
                base_table = fts_table.replace("_fts", "")
                if base_table not in schema_result["tables_found"]:
                    schema_result["valid"] = False
                    schema_result["issues"].append(f"Orphaned FTS table: {fts_table} (missing base table {base_table})")
        
        except Exception as e:
            schema_result["valid"] = False
            schema_result["issues"].append(f"Schema validation failed: {str(e)}")
        
        return schema_result
    
    async def _get_database_details(self, conn: aiosqlite.Connection) -> Dict[str, Any]:
        """Get additional database details and statistics."""
        details = {}
        
        try:
            # Page size and count
            cursor = await conn.execute("PRAGMA page_size")
            page_size_result = await cursor.fetchone()
            details["page_size"] = page_size_result[0] if page_size_result else 0
            await cursor.close()
            
            cursor = await conn.execute("PRAGMA page_count")
            page_count_result = await cursor.fetchone()
            details["page_count"] = page_count_result[0] if page_count_result else 0
            await cursor.close()
            
            # Free pages (fragmentation indicator)
            cursor = await conn.execute("PRAGMA freelist_count")
            free_pages_result = await cursor.fetchone()
            details["free_pages"] = free_pages_result[0] if free_pages_result else 0
            await cursor.close()
            
            # Calculate fragmentation ratio
            if details["page_count"] > 0:
                details["fragmentation_ratio"] = details["free_pages"] / details["page_count"]
            else:
                details["fragmentation_ratio"] = 0.0
            
            # Table counts
            cursor = await conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = await cursor.fetchall()
            await cursor.close()
            
            table_counts = {}
            for table in tables:
                table_name = table[0]
                try:
                    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count_result = await cursor.fetchone()
                    table_counts[table_name] = count_result[0] if count_result else 0
                    await cursor.close()
                except:
                    table_counts[table_name] = -1  # Error counting
            
            details["table_counts"] = table_counts
            
        except Exception as e:
            details["error"] = str(e)
        
        return details
    
    def _get_database_identifier(self, db_path: Path) -> str:
        """Generate a readable identifier for a database."""
        path_str = str(db_path)
        
        if "storypacks" in path_str:
            # Extract story ID from path like storage/storypacks/story_id/story.db
            parts = Path(path_str).parts
            if "storypacks" in parts:
                idx = parts.index("storypacks")
                if idx + 1 < len(parts):
                    return f"story_{parts[idx + 1]}"
        
        if "memory" in path_str.lower():
            return "memory_system"
        
        # Default to filename
        return db_path.stem or "unknown"
    
    def _generate_recommendations(self, health_report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []
        
        if health_report["overall_status"] == "critical":
            recommendations.append("⚠️  CRITICAL: Backup and restore corrupt databases immediately")
            recommendations.append("🔧 Run database repair utilities")
            
        if health_report["issues_found"] > 0:
            recommendations.append("📊 Review individual database issues in the detailed report")
            
        # Check for high fragmentation
        for db_id, db_info in health_report["databases"].items():
            if "details" in db_info and "fragmentation_ratio" in db_info["details"]:
                if db_info["details"]["fragmentation_ratio"] > 0.2:  # More than 20% fragmentation
                    recommendations.append(f"🗜️  Database '{db_id}' has high fragmentation ({db_info['details']['fragmentation_ratio']:.1%}) - consider running VACUUM")
        
        if health_report["databases_checked"] == 0:
            recommendations.append("🚀 Initialize the system by creating your first story")
        
        if not recommendations:
            recommendations.append("✅ All databases are healthy - no action required")
        
        return recommendations
    
    def get_all_databases(self) -> List[str]:
        """
        Get paths to all databases for external health checks.
        
        This method is called by the startup_health_check function specified
        in the Development Master Plan.
        """
        # Run the async discovery in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            db_paths = loop.run_until_complete(self._discover_databases())
            return [str(path) for path in db_paths]
        finally:
            loop.close()
