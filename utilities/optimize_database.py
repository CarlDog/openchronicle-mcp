#!/usr/bin/env python3
"""
OpenChronicle Database Optimizer Utility
Optimizes SQLite databases, analyzes storage, and maintains database health.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the parent directory to the path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

class DatabaseOptimizer:
    """Handles optimization of OpenChronicle SQLite databases."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.root_dir = Path(__file__).parent.parent
        self.storage_dir = self.root_dir / "storage"
        self.optimized_dbs = []
        self.total_space_saved = 0
        
    def find_databases(self) -> List[Path]:
        """Find all SQLite databases in the storage directory."""
        databases = []
        
        if not self.storage_dir.exists():
            return databases
        
        # Look for .db files
        for db_file in self.storage_dir.rglob("*.db"):
            if db_file.is_file():
                databases.append(db_file)
        
        # Look for files that might be SQLite databases without .db extension
        for file_path in self.storage_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix != ".db":
                try:
                    with sqlite3.connect(str(file_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = cursor.fetchall()
                        if tables:  # If it has tables, it's likely a SQLite database
                            databases.append(file_path)
                except (sqlite3.Error, sqlite3.DatabaseError):
                    # Not a SQLite database, skip
                    pass
        
        return databases
    
    def analyze_database(self, db_path: Path) -> Dict[str, Any]:
        """Analyze a SQLite database and return statistics."""
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                
                # Get database file size
                file_size = db_path.stat().st_size
                
                # Get page size and page count
                cursor.execute("PRAGMA page_size;")
                page_size = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA page_count;")
                page_count = cursor.fetchone()[0]
                
                # Get free page count
                cursor.execute("PRAGMA freelist_count;")
                free_pages = cursor.fetchone()[0]
                
                # Get table information
                cursor.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name;
                """)
                tables = cursor.fetchall()
                
                # Get table statistics
                table_stats = []
                for table_name, table_sql in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    row_count = cursor.fetchone()[0]
                    
                    # Get approximate table size
                    cursor.execute(f"SELECT SUM(pgsize) FROM dbstat WHERE name='{table_name}';")
                    table_size_result = cursor.fetchone()
                    table_size = table_size_result[0] if table_size_result[0] else 0
                    
                    table_stats.append({
                        "name": table_name,
                        "rows": row_count,
                        "size": table_size,
                        "sql": table_sql
                    })
                
                # Get index information
                cursor.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name;
                """)
                indexes = cursor.fetchall()
                
                # Calculate fragmentation
                used_pages = page_count - free_pages
                fragmentation_ratio = free_pages / page_count if page_count > 0 else 0
                
                return {
                    "file_size": file_size,
                    "page_size": page_size,
                    "page_count": page_count,
                    "free_pages": free_pages,
                    "used_pages": used_pages,
                    "fragmentation_ratio": fragmentation_ratio,
                    "tables": table_stats,
                    "indexes": indexes,
                    "needs_vacuum": fragmentation_ratio > 0.1,  # More than 10% fragmentation
                    "last_modified": datetime.fromtimestamp(db_path.stat().st_mtime)
                }
                
        except sqlite3.Error as e:
            return {
                "error": str(e),
                "file_size": db_path.stat().st_size if db_path.exists() else 0
            }
    
    def vacuum_database(self, db_path: Path) -> Dict[str, Any]:
        """Vacuum a SQLite database to reclaim space and reduce fragmentation."""
        try:
            # Get size before vacuum
            size_before = db_path.stat().st_size
            
            if not self.dry_run:
                with sqlite3.connect(str(db_path)) as conn:
                    print(f"  🔄 Vacuuming database...")
                    conn.execute("VACUUM;")
                    conn.commit()
            
            # Get size after vacuum
            size_after = db_path.stat().st_size if not self.dry_run else size_before
            space_saved = size_before - size_after
            
            return {
                "success": True,
                "size_before": size_before,
                "size_after": size_after,
                "space_saved": space_saved,
                "reduction_percent": (space_saved / size_before * 100) if size_before > 0 else 0
            }
            
        except sqlite3.Error as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def reindex_database(self, db_path: Path) -> Dict[str, Any]:
        """Rebuild all indexes in a SQLite database."""
        try:
            if not self.dry_run:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()
                    
                    # Get all indexes
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='index' AND name NOT LIKE 'sqlite_%'
                    """)
                    indexes = cursor.fetchall()
                    
                    if indexes:
                        print(f"  🔄 Rebuilding {len(indexes)} indexes...")
                        conn.execute("REINDEX;")
                        conn.commit()
                    
                    return {
                        "success": True,
                        "indexes_rebuilt": len(indexes)
                    }
            else:
                return {
                    "success": True,
                    "indexes_rebuilt": 0,
                    "dry_run": True
                }
                
        except sqlite3.Error as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def analyze_queries(self, db_path: Path) -> Dict[str, Any]:
        """Analyze query performance and suggest optimizations."""
        suggestions = []
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                
                # Check for tables without primary keys
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                
                for (table_name,) in tables:
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    has_primary_key = any(col[5] for col in columns)  # col[5] is the pk flag
                    if not has_primary_key:
                        suggestions.append({
                            "type": "missing_primary_key",
                            "table": table_name,
                            "suggestion": f"Consider adding a primary key to table '{table_name}' for better performance"
                        })
                
                # Check for tables with many rows but no indexes
                for (table_name,) in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    row_count = cursor.fetchone()[0]
                    
                    if row_count > 1000:  # Arbitrary threshold
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM sqlite_master 
                            WHERE type='index' AND tbl_name='{table_name}'
                        """)
                        index_count = cursor.fetchone()[0]
                        
                        if index_count == 0:
                            suggestions.append({
                                "type": "missing_indexes",
                                "table": table_name,
                                "rows": row_count,
                                "suggestion": f"Table '{table_name}' has {row_count} rows but no indexes. Consider adding indexes on frequently queried columns."
                            })
                
                return {
                    "suggestions": suggestions,
                    "total_suggestions": len(suggestions)
                }
                
        except sqlite3.Error as e:
            return {
                "error": str(e),
                "suggestions": []
            }
    
    def optimize_database(self, db_path: Path) -> Dict[str, Any]:
        """Perform full optimization on a database."""
        print(f"\n🔧 Optimizing: {db_path.relative_to(self.root_dir)}")
        
        # Analyze database first
        analysis = self.analyze_database(db_path)
        if "error" in analysis:
            print(f"  ❌ Error analyzing database: {analysis['error']}")
            return {"success": False, "error": analysis["error"]}
        
        # Display analysis
        print(f"  📊 Size: {self._format_size(analysis['file_size'])}")
        print(f"  📄 Pages: {analysis['page_count']} ({analysis['free_pages']} free)")
        print(f"  🗂️  Tables: {len(analysis['tables'])}")
        print(f"  🔍 Indexes: {len(analysis['indexes'])}")
        print(f"  📈 Fragmentation: {analysis['fragmentation_ratio']:.1%}")
        
        results = {
            "analysis": analysis,
            "vacuum_result": None,
            "reindex_result": None,
            "query_analysis": None
        }
        
        # Vacuum if needed
        if analysis["needs_vacuum"]:
            print(f"  🧹 Database needs vacuuming (fragmentation: {analysis['fragmentation_ratio']:.1%})")
            vacuum_result = self.vacuum_database(db_path)
            results["vacuum_result"] = vacuum_result
            
            if vacuum_result["success"]:
                space_saved = vacuum_result["space_saved"]
                self.total_space_saved += space_saved
                print(f"  ✅ Vacuum completed: {self._format_size(space_saved)} saved ({vacuum_result['reduction_percent']:.1f}% reduction)")
            else:
                print(f"  ❌ Vacuum failed: {vacuum_result['error']}")
        else:
            print(f"  ✅ Database is well-optimized (fragmentation: {analysis['fragmentation_ratio']:.1%})")
        
        # Reindex
        reindex_result = self.reindex_database(db_path)
        results["reindex_result"] = reindex_result
        
        if reindex_result["success"]:
            if not self.dry_run:
                print(f"  ✅ Reindex completed: {reindex_result['indexes_rebuilt']} indexes rebuilt")
            else:
                print(f"  🔍 Would rebuild indexes (dry run)")
        else:
            print(f"  ❌ Reindex failed: {reindex_result['error']}")
        
        # Analyze queries
        query_analysis = self.analyze_queries(db_path)
        results["query_analysis"] = query_analysis
        
        if query_analysis["suggestions"]:
            print(f"  💡 Performance suggestions:")
            for suggestion in query_analysis["suggestions"]:
                print(f"    - {suggestion['suggestion']}")
        
        self.optimized_dbs.append(db_path)
        return results
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.1f} {units[i]}"
    
    def run_optimization(self) -> None:
        """Run optimization on all databases."""
        print("🔧 Starting OpenChronicle Database Optimization")
        print("=" * 50)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print()
        
        databases = self.find_databases()
        
        if not databases:
            print("📝 No databases found in storage directory")
            return
        
        print(f"🔍 Found {len(databases)} database(s) to optimize")
        
        for db_path in databases:
            try:
                self.optimize_database(db_path)
            except Exception as e:
                print(f"❌ Error optimizing {db_path}: {e}")
        
        # Summary
        print("\n📊 Optimization Summary:")
        print(f"  🗃️  Databases optimized: {len(self.optimized_dbs)}")
        print(f"  💾 Total space saved: {self._format_size(self.total_space_saved)}")
        
        if self.dry_run:
            print("\n💡 Run without --dry-run to actually optimize databases")


def main():
    """Main function with command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenChronicle Database Optimizer")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--database", type=str, help="Optimize specific database file")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze databases without optimizing")
    parser.add_argument("--vacuum-threshold", type=float, default=0.1, help="Fragmentation threshold for vacuum (default: 0.1)")
    
    args = parser.parse_args()
    
    optimizer = DatabaseOptimizer(dry_run=args.dry_run)
    
    if args.database:
        # Optimize specific database
        db_path = Path(args.database)
        if not db_path.exists():
            print(f"❌ Database file not found: {db_path}")
            return
        
        if args.analyze_only:
            analysis = optimizer.analyze_database(db_path)
            print(f"📊 Analysis of {db_path}:")
            print(json.dumps(analysis, indent=2, default=str))
        else:
            optimizer.optimize_database(db_path)
    else:
        # Optimize all databases
        if args.analyze_only:
            databases = optimizer.find_databases()
            print(f"📊 Analysis of {len(databases)} database(s):")
            for db_path in databases:
                analysis = optimizer.analyze_database(db_path)
                print(f"\n🗃️  {db_path.relative_to(optimizer.root_dir)}:")
                print(f"  Size: {optimizer._format_size(analysis['file_size'])}")
                print(f"  Fragmentation: {analysis.get('fragmentation_ratio', 0):.1%}")
                print(f"  Tables: {len(analysis.get('tables', []))}")
                print(f"  Needs vacuum: {analysis.get('needs_vacuum', False)}")
        else:
            optimizer.run_optimization()


if __name__ == "__main__":
    main()
